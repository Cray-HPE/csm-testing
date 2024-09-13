#!/usr/bin/env python3
"""
CAST-36602 script to scrub misloaded data in SLS.

1. Read in SLS data and convert the first 8 Paradise compute nodes to UAN.
2. Renumber all remaining compute starting with 1.
"""

import argparse
import json
import sys

if __name__ == "__main__":
    # attempt to provide a quick help to anyone attempting to use the script
    parser = argparse.ArgumentParser(description="Modifies an SLS dumpstate to remove misloaded data")
    parser.add_argument("input_file", help="Dumpstate file with all computes (after hardware topology tool)")
    parser.add_argument("lookup_file", help="Original dumpstate file with uan and incorrectly loaded paradise nodes")
    parser.add_argument("output_file", help="Final fixed dumpstate file")
    args = parser.parse_args()

    with open(args.input_file, "r") as file:
        sls = json.load(file)
    sls_hardware = sls.get("Hardware")
    sls_networks = sls.get("Networks")

    with open(args.lookup_file, "r") as file:
        lookup = json.load(file)
    lookup_hardware = lookup.get("Hardware")
    lookup_networks = lookup.get("Networks")

    # Find the bad nodes to be deleted and their parents
    for xname in list(sls_hardware.keys()):
        node_type = sls_hardware[xname].get("Type")
        node_class = sls_hardware[xname].get("Class")

        if node_type == "comptype_node" and node_class == "River":
            node_properties = sls_hardware[xname].get("ExtraProperties")
            node_role = node_properties.get("Role")
            node_number = node_properties.get("NID")
            if node_number is None:
                continue
            node_number = int(node_number)

            # Convert UANs
            # NID <= 8 need to be converted to UAN
            if node_role == "Compute" and node_number <= 8:
                print(f"{xname} is compute {node_number} needing UAN retrofit")
                if xname not in lookup_hardware.keys():
                    print(f"UAN {xname} not found in running/original sls data")
                    sys.exit(1)
                uan_properties = lookup_hardware[xname].get("ExtraProperties")
                # CN to UAN is only in the ExtraProperties
                uan_properties.pop("NID")
                sls_hardware[xname]["ExtraProperties"] = uan_properties

            # Renumbering
            # NID > 8 are Compute and need to be renumbered to begin at 1
            if node_role == "Compute" and node_number > 8:
                old_number = node_number
                new_number = node_number - 8
                print(f"{xname} renumbering Compute {old_number} to {new_number}")
                cn_properties = sls_hardware[xname].get("ExtraProperties")
                if "NID" in cn_properties.keys():
                    cn_properties["NID"] = new_number
                if "Aliases" in cn_properties.keys():
                    if f"nid{old_number:06}" in cn_properties["Aliases"]:
                        cn_properties["Aliases"].remove(f"nid{old_number:06}")
                        cn_properties["Aliases"].append(f"nid{new_number:06}")


    data = {"Hardware": sls_hardware, "Networks": sls_networks}
    with open(args.output_file, "w") as file:
        json.dump(data, file, indent=4)
