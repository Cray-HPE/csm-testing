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
Usage: goss_suite_urls <suite name> <node> [<node>] ...

Outputs a space-separated list of URLs to the endpoint on the nodes (on the .hmn network)
for the given suite.

Exits 0 on success, non-0 otherwise.
"""

from lib.common import argparse_yaml_file_name,     \
                       argparse_valid_ncn_name,     \
                       get_ncn_type,                \
                       NCN_TYPES,                   \
                       ScriptException
from lib.endpoints  import load_goss_endpoints

import argparse
import sys

port_endpoint = dict()

def get_port_endpoint(node: str, suite: str) -> tuple[int, str]:
    node_type = get_ncn_type(node)
    try:
        return port_endpoint[node_type]
    except KeyError:
        goss_endpoints_by_ncn_type = load_goss_endpoints()
        for (suite_name, endpoint_name, port) in goss_endpoints_by_ncn_type[node_type]:
            if suite_name == suite:
                port_endpoint[node_type] = port, endpoint_name
                return port, endpoint_name
        raise ScriptException(f"No port/endpoint found for suite {suite} for NCN {node_type} nodes")

def parse_args() -> tuple[str, list]:
    parser = argparse.ArgumentParser(description="Print list of Goss endpoints.")
    parser.add_argument("suite", type=argparse_yaml_file_name, help="Goss suite name.")
    parser.add_argument("nodes", nargs="+", type=argparse_valid_ncn_name, help="Target nodes.")
    args = parser.parse_args()
    return args.suite, args.nodes

def get_suite_urls_nodelist(suite: str, *nodes) -> list:
    urls = list()
    for node in nodes:
        port, endpoint = get_port_endpoint(node, suite)
        urls.append(f"http://{node}.hmn:{port}/{endpoint}")
    return urls

if __name__ == "__main__":
    suite, nodes = parse_args()
    urls = get_suite_urls_nodelist(suite, *nodes)
    print(' '.join(urls))
    sys.exit(0)
