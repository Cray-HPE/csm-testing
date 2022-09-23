#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

"""
Usage: check_for_unused_drives.sh <number of storage nodes>

Validates that the system has:
* Exactly 8 OSDs per storage node, if HPE hardware
* Exactly 12 OSDs per storage node, if Gigabyte hardware
* At least 1 OSD per storage node, if Intel hardware
* Or that (#_osds / #_storage_nodes) has no remainder
 
The test fails if the above validation fails.
If the system has a different hardware type or the test is unable
to determine it, the test fails.
Otherwise, the test passes.

On failures,  the test exits with unusual exit codes, to help make it clearer
in the Goss summarized output where the test failed.
"""

import argparse
import json
import logging
import rados
import sys

CEPH_CONFIG_FILE = "/etc/ceph/ceph.conf"

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")

# Log debug and info messages to stdout, warnings and above to stderr

# Create handler for stdout
stdout_handler = logging.StreamHandler(sys.stdout)
# Log everything DEBUG and above...
stdout_handler.setLevel(logging.DEBUG)
# ...but filter out any logger messages above INFO level (i.e. warnings, errors)
stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

# Create handler for stderr
stderr_handler = logging.StreamHandler(sys.stderr)
# Log everything WARNING and above...
stderr_handler.setLevel(logging.WARNING)
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

# Mapping from ipmitool mc info Manufacturer Name string to a friendlier name
hw_type_map = {
    "GIGA-BYTE TECHNOLOGY CO., LTD": "gigabyte",
    "Hewlett Packard Enterprise": "hpe",
    "Intel Corporation": "intel" }

min_osds_per_storage_node = {
    "gigabyte": 12,
    "hpe": 8,
    "intel": 1 }

max_osds_per_storage_node = {
    "gigabyte": 12,
    "hpe": 8,
    "intel": 0 }

def num_storage_nodes(string):
    num = int(string)
    if num >= 3:
        return num
    raise argparse.ArgumentTypeError("System should have at least 3 storage nodes. Invalid number of storage nodes: {}".format(num))

def parse_args():
    parser = argparse.ArgumentParser(description="Validate OSD count in Ceph cluster based on hardware type")
    parser.add_argument("num_storage_nodes", metavar="number_of_storage_nodes", type=num_storage_nodes, help="Number of storage NCNs in the system")
    parser.add_argument("hw_type", metavar="hardware_manufacturer", choices=hw_type_map, help="Manufacturer name (as shown in output of 'ipmitool mc info')")
    logger.debug("Parsing command line arguments: {}".format(sys.argv))
    args = parser.parse_args()

    hw_type = hw_type_map[args.hw_type]
    min_expected_osds = min_osds_per_storage_node[hw_type] * args.num_storage_nodes
    max_expected_osds = max_osds_per_storage_node[hw_type] * args.num_storage_nodes
    logger.info("Based on hardware type ({}) and number of storage nodes ({}): min_expected_osds = {}, max_expected_osds = {}".format(hw_type, args.num_storage_nodes, min_expected_osds, max_expected_osds))
    return min_expected_osds, max_expected_osds, args.num_storage_nodes

def get_num_osds():
    logger.debug("Loading Ceph")
    ceph = rados.Rados(conffile=CEPH_CONFIG_FILE)
    logger.debug("Connecting to Ceph")
    # connect to cluster
    ceph.connect()
    logger.info("Running ceph osd stat command")
    cmd_rc, cmd_out_bytes, cmd_opt_str = ceph.mon_command('{"prefix": "osd stat", "format": "json-pretty"}', b'')
    #disconnect from cluster
    ceph.shutdown()
    logger.info("Command return code = {}".format(cmd_rc))
    if cmd_opt_str:
        logger.info("Optional output string: {}".format(cmd_opt_str))
    if cmd_rc != 0:
        logger.error("ceph osd stat call failed")
        sys.exit(2)
    logger.debug("Decoding command output to string:")
    print(cmd_out_bytes.decode())
    logger.debug("Decoding command output from JSON into object")
    cmd_response = json.loads(cmd_out_bytes)
    logger.debug("Extracting number of OSDs from object")
    num_osds = cmd_response["num_osds"]
    logger.info("num_osds = {}".format(num_osds))
    if not isinstance(num_osds, int):
        logger.error("num_osds field expected to be an integer, but it is type {}".format(type(num_osds).__name__))
        sys.exit(3)
    elif num_osds < 0:
        logger.error("num_osds should not be negative")
        sys.exit(4)
    elif num_osds == 0:
        logger.error("No OSDs reported")
        sys.exit(5)
    return num_osds

def main():
    min_expected_osds, max_expected_osds, n_storage_nodes = parse_args()
    num_osds = get_num_osds()
    if num_osds < min_expected_osds:
        if num_osds%n_storage_nodes != 0:
            logger.error("Fewer OSDs than expected and osds are not spread evenly across storage nodes.")
            sys.exit(6)
    elif max_expected_osds > 0 and num_osds > max_expected_osds:
        if num_osds%n_storage_nodes != 0:
            logger.error("More OSDs than expected and osds are not spread evenly across storage nodes.")
            sys.exit(9)
    logger.info("SUCCESS -- number of OSDs found matches expectations based on hardware type or are spread evely across storage nodes.")
    sys.exit(0)

if __name__ == "__main__":
    main()
