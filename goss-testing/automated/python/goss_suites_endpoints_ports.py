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
Usage: goss_suites_endpoints_ports

Scans the Goss server configuration file and prints out a list of suites/endpoint/port combinations
that should be started for the current node.

Each line of output is of the format:
<full suite path> <endpoint name> <port>

Exits 0 on success, non-0 otherwise.
"""

from lib.common import goss_suites_dir,             \
                       load_goss_endpoints,         \
                       my_ncn_type

import sys

if __name__ == "__main__":
    suite_dir = goss_suites_dir()
    node_type = my_ncn_type()
    goss_endpoints_by_ncn_type = load_goss_endpoints()
    for (suite_name, endpoint_name, port) in goss_endpoints_by_ncn_type[node_type]:
        print(f"{suite_dir}/{suite_name} {endpoint_name} {port}")
    sys.exit(0)
