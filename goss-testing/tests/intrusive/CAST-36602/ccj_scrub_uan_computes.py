#!/usr/bin/env python3
"""
CAST-36602 script to scrub CCJ where computes are used as UAN.

We persuade cn1-8 to be UANs to fall into this hole:
https://github.com/Cray-HPE/hardware-topology-assistant/blob/8171f0b0e4e128cea29aae6e4bddf919930a01ce/pkg/ccj/sls_state_generator.go#L313
"""

import json

input_file = "venado-full-ccj.prescrub.json"
output_file = "venado-full-ccj.scrubbed.json"


with open(input_file, "r") as file:
    ccj = json.load(file)

for node in ccj["topology"]:
    old_name = node["common_name"]
    node_prefix = old_name[:2]
    if node_prefix != "cn":
        continue
    node_number = int(old_name[2:])
    if node_number < 9:
        new_name = "uan" + old_name[2:]
        print(f"Renaming {old_name} to {new_name}")
        node["common_name"] = new_name


with open(output_file, "w") as file:
    json.dump(ccj, file, indent=4)
