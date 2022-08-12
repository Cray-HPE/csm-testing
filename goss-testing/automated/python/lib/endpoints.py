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
Helper functions for Goss Python automated scripts

These functions relate to the Goss server endpoints.
"""

from .common import argparse_yaml_file_name,     \
                    goss_servers_config,         \
                    NCN_TYPES,                   \
                    ScriptException

from typing import Dict, List, Tuple

import argparse
import re

StringList = List[str]
EndpointTuple = Tuple[str, str, int]

# We assume our Goss server ports will be between 1000 and 65535 (the maximum TCP port number)

# Pattern for 1000-9999     = [1-9][0-9]{3}
# Pattern for 10000-59999   = [1-5][0-9]{4}
# Pattern for 60000-64999   = 6[0-4][0-9]{3}
# Pattern for 65000-65499   = 65[0-4][0-9]{2}
# Pattern for 65500-65529   = 655[0-2][0-9]
# Pattern for 65530-65535   = 6553[0-5]
port_patterns = [ 
    "[1-9][0-9]{3}", 
    "[1-5][0-9]{4}",
    "6[0-4][0-9]{3}",
    "65[0-4][0-9]{2}",
    "655[0-2][0-9]",
    "6553[0-5]" ]
port_pattern = "^(" + "|".join(port_patterns) + ")$"
port_re_prog = re.compile(port_pattern)

goss_endpoints_by_ncn_type = None

def parse_config_file_line(line: str) -> Tuple[int, str, StringList]:
    """
    Returns port, suite file, and list of NCN types
    Raises ScriptException in case of error
    """
    fields = line.split()
    # All valid non-blank, non-commented lines have 3 or more fields
    # 1. Port number
    # 2. YAML suite file
    # 3. List of NCN types

    if len(fields) < 3:
        raise ScriptException(f"Line must have at least three fields.")

    port_string=fields[0]
    if not port_re_prog.match(port_string):
        raise ScriptException(f"Line has invalid port format.")
    port = int(port_string)

    try:
        suite = argparse_yaml_file_name(fields[1])
    except argparse.ArgumentTypeError as e:
        raise ScriptException(f"{e}. Invalid YAML suite file name.")

    type_list = fields[2:]
    if not all(t in NCN_TYPES for t in type_list):
        raise ScriptException(f"Line includes invalid NCN type.")
    elif len(type_list) != len(set(type_list)):
        raise ScriptException(f"Line includes duplicate NCN types.")
    return port, suite, type_list

def load_goss_endpoints() -> Dict[str, List[EndpointTuple]]:
    """
    Reads Goss server configuration file (goss-servers.json) and for each NCN type, generates a mapping from
    port number to endpoint name + suite name.
    These mappings are returned.
    """
    global goss_endpoints_by_ncn_type
    if goss_endpoints_by_ncn_type != None:
        return goss_endpoints_by_ncn_type
    config_file = goss_servers_config(validate=True)
    
    endpoints_by_type = { ntype: list() for ntype in NCN_TYPES }
    with open(config_file, "rt") as f:
        for line in f.readlines():
            line = line.strip()
            if len(line) == 0 or line[0] == "#":
                continue
            try:
                port, suite, type_list = parse_config_file_line(line)
            except ScriptException as e:
                raise ScriptException(f"Configuration file ({config_file}) error: {e}. Invalid line: {line}")
            # Endpoint name is the suite name, minus the .yaml extension
            endpoint_name = suite[:-5]

            for ntype in type_list:
                for (s, e, p) in endpoints_by_type[ntype]:
                    if s == suite:
                        raise ScriptException(f"Configuration file ({config_file}) error: Multiple lines for suite {s} on NCN type {ntype}. Invalid line: {line}")
                    elif p == port:
                        raise ScriptException(f"Configuration file ({config_file}) error: Multiple lines for port {p} on NCN type {ntype}. Invalid line: {line}")

                # Add it to the list of endpoints for this NCN type
                endpoints_by_type[ntype].append( (suite, endpoint_name, port) )

    if sum(len(eplist) for eplist in endpoints_by_type.values()) == 0:
        raise ScriptException(f"Server configuration ({config_file}) error: No endpoints specified")

    goss_endpoints_by_ncn_type = endpoints_by_type
    return goss_endpoints_by_ncn_type
