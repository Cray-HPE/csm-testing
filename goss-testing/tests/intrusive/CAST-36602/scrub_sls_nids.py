#!/usr/bin/env python3
"""
CAST-36602 script to scrub misloaded data in SLS.

1. Remove River compute nodes that are quad node chassis and categorized as 2 dual node chassis.
2. Remove those node's bmc connection to the mgmt switches.
3. Remove the mgmt switch bmc connections to the node bmc's.
4. Remove NID numbers from UAN nodes.
5. Remove HSN reservations for the removed nodes.
"""

import json
import argparse

if __name__ == "__main__":
    # attempt to provide a quick help to anyone attempting to use the script
    parser = argparse.ArgumentParser(description="Modifies an SLS dumpstate to remove misloaded data")
    parser.add_argument("input_file", help="Path to broken dumpstate file")
    parser.add_argument("output_file", help="Desired path for fixed dumpstate file")
    args = parser.parse_args()


    with open(args.input_file, "r") as file:
        sls = json.load(file)

    sls_hardware = sls.get("Hardware")
    sls_networks = sls.get("Networks")

    # Find the bad nodes to be deleted and their parents
    bad_node_list = []
    bad_node_parent_list = []
    for xname in list(sls_hardware.keys()):
        node_type = sls_hardware[xname].get("Type")
        node_class = sls_hardware[xname].get("Class")
        if node_class == "River" and node_type == "comptype_node":
            node_properties = sls_hardware[xname].get("ExtraProperties")
            node_role = node_properties.get("Role")
            node_number = node_properties.get("NID")
            if node_number is None:
                continue
            if node_role == "Compute" or node_role == "Application":
                if node_role == "Compute":
                    print(f"{xname} is compute {node_number} for removal")
                else:
                    print(f"{xname} is application {node_number} for removal")
                bad_node_list.append(xname)
                bad_node_parent_list.append(sls_hardware[xname].get("Parent"))

    # Find mgmt network connectors for the bad nodes
    bad_connector_list = []
    bad_connector_parent_list = []
    for xname in list(sls_hardware.keys()):
        node_type = sls_hardware[xname].get("Type")
        node_class = sls_hardware[xname].get("Class")

        if node_class == "River" and node_type == "comptype_mgmt_switch_connector":
            node_properties = sls_hardware[xname].get("ExtraProperties")
            node_nics = node_properties.get("NodeNics")
            for nic_xname in node_nics:
                if nic_xname in bad_node_parent_list:
                    print(f"{xname} is a connector to {nic_xname} for removal")
                    bad_connector_list.append(xname)
                    bad_connector_parent_list.append(sls_hardware[xname].get("Parent"))

    # Remove dupes
    bad_connector_parent_list = list(dict.fromkeys(bad_connector_parent_list))

    print(f"BAD NODE COUNT {len(bad_node_list)}")
    print(f"BAD CONNECTOR COUNT {len(bad_connector_list)}")
    print(f"BAD CONNECTOR PARENTS COUNT {len(bad_connector_parent_list)}")

    # Remove bad nodes
    for node in bad_node_list:
        sls_hardware.pop(node)

    # Remove the connectors (bmc connection) to bad nodes
    for node in bad_connector_list:
        sls_hardware.pop(node)

    # Remove the bad node connection to mgmt switch
    for node in bad_connector_parent_list:
        children = sls_hardware[node]["Children"]
        for connector in bad_connector_list:
            if connector in children:
                children.remove(connector)

    # Remove bad nodes from the HSN Networks
    old_hsn_reservations = sls_networks["HSN"]["ExtraProperties"]["Subnets"][0]["IPReservations"]
    new_hsn_reservations = [x for x in old_hsn_reservations if x["Name"][:-2] not in bad_node_list]
    print(f"HSN RESERVATIONS - OLD {len(old_hsn_reservations)}")
    print(f"                   NEW {len(new_hsn_reservations)}")
    print(f"                   REMOVED {len(old_hsn_reservations) - len(new_hsn_reservations)}")

    sls_networks["HSN"]["ExtraProperties"]["Subnets"][0]["IPReservations"] = new_hsn_reservations

    data = {"Hardware": sls_hardware, "Networks": sls_networks}
    with open(args.output_file, "w") as file:
        json.dump(data, file, indent=4)
