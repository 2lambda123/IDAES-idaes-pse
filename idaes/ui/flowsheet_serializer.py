##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2019, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################
from collections import defaultdict
import json
import os

from idaes.core import UnitModelBlockData
from idaes.core.util.tables import stream_states_dict
from idaes.ui.link_position_mapping import link_position_mapping
from idaes.ui.icon_mapping import icon_mapping

from pyomo.environ import Block
from pyomo.network.port import SimplePort
from pyomo.network import Arc


class FileBaseNameExistsError(Exception):
    pass


class FlowsheetSerializer:
    def __init__(self):
        self.unit_models = {}
        self.arcs = {}
        self.ports = {}
        self.edges = defaultdict(list)
        self.orphaned_ports = {}
        self.labels = {}
        self.out_json = {"model": {}}
        self.name = ""

    def serialize(self, flowsheet, name):
        """
        Serializes the flowsheet into one dict with two sections.

        The "model" section contains the id of the flowsheet and the
        unit models and arcs. This will be used to compare the model and convert
        to jointjs

        The "cells" section is the jointjs readable code.

        .. code-block:: json

        {
            "model": {
                "id": "id", 
                "unit_models": {
                    "M101": {
                        "image": "mixer.svg", 
                        "type": "mixer"
                    }
                },
                "arcs": {
                    "s03": {
                        "source": "M101", 
                        "dest": "H101", 
                        "label": "molar flow ('Vap', 'hydrogen') 0.5"
                    }
                }
            },
            "cells": [{ "--jointjs code--": "--jointjs code--" }]
        }

        :param flowsheet: The flowsheet to save. Usually fetched from the model.
        :param name: The name of the flowsheet. This will be used as the model id
        :return: None

        Usage example:
            m = ConcreteModel()
            m.fs = FlowsheetBlock(...)
            ...
            serializer = FlowsheetSerializer()
            serializer.save(m.fs, "output_file")
        """
        self.name = name
        self.serialize_flowsheet(flowsheet)
        self._construct_output_json()

        return self.out_json

    def serialize_flowsheet(self, flowsheet):
        for component in flowsheet.component_objects(Block, descend_into=False):
            # TODO try using component_objects(ctype=X)
            if isinstance(component, UnitModelBlockData):
                self.unit_models[component] = {
                    "name": component.getname(), 
                    "type": component._orig_module.split(".")[-1]
                }

                for subcomponent in component.component_objects(descend_into=True):
                    if isinstance(subcomponent, SimplePort):
                        self.ports[subcomponent] = component
  
        for component in flowsheet.component_objects(Arc, descend_into=False):
            self.arcs[component.getname()] = component

        for stream_name, value in stream_states_dict(self.arcs).items():
            label = ""

            for var, var_value in value.define_display_vars().items():
                for stream_type, stream_value in var_value.get_values().items():
                    if stream_type:
                        if var == "flow_mol_phase_comp":
                            var = "Molar Flow"
                        label += f"{var} {stream_type} {stream_value}\n"
                    else:
                        var = var.capitalize()
                        label += f"{var} {stream_value}\n"

            self.labels[stream_name] = label[:-2]

        self.edges = {}
        for name, arc in self.arcs.items():
            self.edges[name] = {"source": self.ports[arc.source], 
                                "dest": self.ports[arc.dest]}

    def create_image_jointjs_json(self, out_json, x_pos, y_pos, name, image, title, port_groups):
        entry = {}
        entry["type"] = "standard.Image"
        # for now, just tile the positions diagonally
        # TODO Make the default positioning better
        entry["position"] = {"x": x_pos, "y": y_pos}
        # TODO Set the width and height depending on the icon rather than default
        entry["size"] = {"width": 50, "height": 50}
        entry["angle"] = 0
        entry["id"] = name
        entry["z"] = (1,)
        entry["ports"] = port_groups
        entry["attrs"] = {
            "image": {"xlinkHref": "/images/icons/" + image},
            "label": {
                "text": name
            },
            "root": {"title": title},
        }
        out_json["cells"].append(entry)

    def create_link_jointjs_json(self, out_json, source_port, dest_port, 
                                 source_id, dest_id, name, label):      
        entry = {
            "type": "standard.Link",
            "source": {"id": source_id, "port": source_port},
            "target": {"id": dest_id, "port": dest_port},
            "router": {"name": "orthogonal", "padding": 10},
            "connector": {"name": "normal", 
                          "attrs": {"line": {"stroke": "#5c9adb"}}},
            "id": name,
            "labels": [{
                "attrs": {
                    "rect": {"fill": "#d7dce0", "stroke": "#FFFFFF", 'stroke-width': 1},
                    "text": {
                        "text": label,
                        "fill": 'black',
                        'text-anchor': 'left',
                    },
                },
                "position": {
                    "distance": 0.66,
                    "offset": -40
                },
            }],
            "z": 2
        }
        out_json["cells"].append(entry)

    def get_unit_models(self):
        return self.unit_models

    def get_ports(self):
        return self.ports

    def get_edges(self):
        return self.edges

    def _construct_output_json(self):
        self._construct_model_json()
        self._construct_jointjs_json()

    def _construct_model_json(self):
        self.out_json["model"]["id"] = self.name
        self.out_json["model"]["unit_models"] = {}
        self.out_json["model"]["arcs"] = {}

        for unit_model in self.unit_models.values():
            self.out_json["model"]["unit_models"][unit_model["name"]] = {
                "type": unit_model["type"],
                "image": "/images/icons/" + icon_mapping(unit_model["type"])
            }

        for edge in self.edges:
            self.out_json["model"]["arcs"][edge] = \
                {"source": self.edges[edge]["source"].getname(),
                 "dest": self.edges[edge]["dest"].getname(),
                 "label": self.labels[edge]}

    def _construct_jointjs_json(self):
        self.out_json["cells"] = []
        x_pos = 100
        y_pos = 100

        for component, unit_attrs in self.unit_models.items():
            print(link_position_mapping[unit_attrs["type"]])
            try:
                self.create_image_jointjs_json(
                    self.out_json,
                    x_pos,
                    y_pos,
                    unit_attrs["name"],
                    icon_mapping(unit_attrs["type"]),
                    unit_attrs["type"],
                    link_position_mapping[unit_attrs["type"]]
                )
            except KeyError:
                self.create_image_jointjs_json(self.out_json, 
                                               x_pos, 
                                               y_pos, 
                                               unit_attrs["name"], 
                                               "default", unit_attrs["type"],
                                               link_position_mapping[unit_attrs["type"]])

            x_pos += 100
            y_pos += 100

        id_counter = 0
        for name, ports_dict in self.edges.items():
            umst = self.unit_models[ports_dict["source"]]["type"]  # alias
            dest = ports_dict["dest"]

            self.create_link_jointjs_json(
                self.out_json, 
                "in", 
                "out", 
                ports_dict["source"].getname(), 
                dest.getname(), 
                name,
                self.labels[name]
            )
