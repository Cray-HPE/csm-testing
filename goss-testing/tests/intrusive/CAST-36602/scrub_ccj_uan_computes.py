#!/usr/bin/env python3
"""
CAST-36602 script to scrub CCJ where computes are used as UAN.

1. Persuade cn1-8 to be UANs to fall into this hole: https://github.com/Cray-HPE/hardware-topology-assistant/blob/8171f0b0e4e128cea29aae6e4bddf919930a01ce/pkg/ccj/sls_state_generator.go#L313
2. Overcome CANU bug CASMNET-2246 "common_name": "SubRack001-cmc" to "SubRack-001-CMC"
3. Set location of node to be SubRack/chassis location, not node location to appease HTA
4. Reset River Compute numbering to 1 (1-8 were moved to UAN)
"""

import argparse
import json

# Usage
if __name__ == "__main__":
    # attempt to provide a quick help to anyone attempting to use the script
    parser = argparse.ArgumentParser(description="Modifies the CCJ to repurpose UANS as storage nodes")
    parser.add_argument("input_file", help="Path to broken CCJ file")
    parser.add_argument("output_file", help="Desired path for fixed CCJ file")
    args = parser.parse_args()

    with open(args.input_file, "r") as file:
        ccj = json.load(file)

    # Rename computes 1-8 to uan 1-8
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

    # Correct SubRack###-cmc to SubRack-###-CMC to match Parent
    for node in ccj["topology"]:
        old_name = node["common_name"]
        node_prefix = old_name[:7]
        if node_prefix != "SubRack":
            continue
        node_number = old_name[7:10]
        new_name = f"{node_prefix}-{node_number}{old_name[10:].upper()}"
        print(f"Renaming {old_name} to {new_name}")
        node["common_name"] = new_name

    # Set Paradise compute locations to be the SubRack/Chassis location
    # rather than the individual node location.  HTA requires this.
    subrack_location_lookup = {
        x["common_name"]: x["location"]["elevation"]
        for x in ccj["topology"] if "SubRack" in x["common_name"]
    }
    for node in ccj["topology"]:
        if "parent" in node["location"]:
            print(f'Resetting {node["common_name"]} from {node["location"]["elevation"]} to SubRack elevation {subrack_location_lookup[node["location"]["parent"]]}')
            node["location"]["elevation"] = subrack_location_lookup[node["location"]["parent"]]

    # Reset cn/nid numbers to begin at 1
    for node in ccj["topology"]:
        old_name = node["common_name"]
        node_prefix = old_name[:2]
        if node_prefix != "cn":
            continue
        node_number = int(old_name[2:]) - 8
        new_name = f"{node_prefix}{node_number:04}"
        print(f"Renaming {old_name} to {new_name}")
        node["common_name"] = new_name

    with open(args.output_file, "w") as file:
        json.dump(ccj, file, indent=4)
