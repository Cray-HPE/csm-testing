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
Global script log file is in directory /opt/cray/tests/install/logs/run_remote_goss_tests.log
This log file is fairly terse in terms of test results, and is more focused on the script execution.

A per-execution log file is also created in /opt/cray/tests/install/logs/run_remote_goss_tests/<timestamp>-<pid>-<randomstring>.log
This log file contains the full test results for any given execution.
"""

import argparse
import colorama
from datetime import datetime
import json
import logging
import os
import random
import re
import socket
import string
import sys
import traceback

NCN_TYPES = [ "master", "storage", "worker" ]

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GOSS_INSTALL_BASE_DIR = "/opt/cray/tests/install"
PIT_NODE_RELEASE_FILE = "/etc/pit-release"

def goss_base_dirs(validate=False):
    """
    Returns GOSS_INSTALL_BASE_DIR, GOSS_BASE
    """
    try:
        base_dir = os.environ["GOSS_BASE"]
        # GOSS_BASE is set

        if validate and not os.path.isdir(base_dir):
            raise ScriptException(f"GOSS_BASE directory does not exist or is not a directory: {base_dir}")

        # Get the value of GOSS_INSTALL_BASE_DIR. In this case, if it is unset, it defaults to being the
        # parent directory of GOSS_BASE.
        install_base_dir = os.environ.get("GOSS_INSTALL_BASE_DIR", os.path.realpath(f"{base_dir}/.."))

        if validate and not os.path.isdir(install_base_dir):
            raise ScriptException(f"GOSS_INSTALL_BASE_DIR directory does not exist or is not a directory: {install_base_dir}")
    except KeyError:
        # GOSS_BASE is not set

        # Get the value of GOSS_INSTALL_BASE_DIR, or its default value if it is also unset
        install_base_dir = os.environ.get("GOSS_INSTALL_BASE_DIR", DEFAULT_GOSS_INSTALL_BASE_DIR)

        if validate and not os.path.isdir(install_base_dir):
            raise ScriptException(f"GOSS_INSTALL_BASE_DIR directory does not exist or is not a directory: {install_base_dir}")

        # GOSS_BASE will be the ncn or livecd subdirectory of GOSS_INSTALL_BASE_DIR, depending on our node type
        if is_pit_node():
            base_dir f"{install_base_dir}/livecd"
        else:
            base_dir f"{install_base_dir}/ncn"

        if validate and not os.path.isdir(base_dir):
            raise ScriptException(f"GOSS_BASE directory does not exist or is not a directory: {base_dir}")

    return install_base_dir, base_dir

def goss_install_base_dir(*args, **kwargs):
    return goss_base_dirs(*args, **kwargs)[0]

def goss_base(*args, **kwargs):
    return goss_base_dirs(*args, **kwargs)[1]

def goss_script_log_level():
    # Make it uppercase, just so that people who accidentally set a lowercase
    # log level are not tripped up
    requested_log_level = os.environ.get("GOSS_SCRIPT_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return logging.getLevelName(requested_log_level)

def goss_servers_config(validate=False):
    gibd = goss_install_base_dir()
    config_file = os.environ.get("GOSS_SERVERS_CONFIG", f"{gibd}/dat/goss-servers.cfg")
    if validate and not os.path.isfile(config_file):
        raise ScriptException(f"GOSS_SERVERS_CONFIG file does not exist or is not a file: {config_file}")
    return config_file

def goss_log_base_dir(validate=False):
    gibd = goss_install_base_dir()
    log_dir = os.environ.get("GOSS_LOG_BASE_DIR", f"{gibd}/logs")
    if validate and not os.path.isdir(log_dir):
        raise ScriptException(f"GOSS_LOG_BASE_DIR directory does not exist or is not a directory: {log_dir}")
    return log_dir

ERR_TEXT_CODE = colorama.Fore.LIGHTRED_EX
WARN_TEXT_CODE = colorama.Fore.LIGHTYELLOW_EX
OK_TEXT_CODE = colorama.Fore.LIGHTGREEN_EX
RESET_TEXT_CODE = colorama.Style.RESET_ALL

class ScriptException(Exception):
    pass

class ScriptUsageException(ScriptException):
    pass

def err_text(s):
    return f"{ERR_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def warn_text(s):
    return f"{WARN_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def ok_text(s):
    return f"{OK_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def is_pit_node():
    return os.path.isfile(PIT_NODE_RELEASE_FILE)

def goss_suites_dir():
    return f"{goss_base()}/suites"

def goss_env_variables():
    return { 
        "GOSS_INSTALL_BASE_DIR": goss_install_base_dir(),
        "GOSS_SCRIPT_LOG_LEVEL": goss_script_log_level(),
        "GOSS_SERVERS_CONFIG": goss_servers_config(),
        "GOSS_LOG_BASE_DIR": goss_log_base_dir(),
        "GOSS_BASE": goss_base() }

def log_dir(script_name):
    # Strip off path and .py, if present, in script name
    script_name = script_name.split('/')[-1]
    if script_name[-3:] == ".py":
        script_name = script_name[:-3]

    mypid = os.getpid()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S.%f')
    randstring = ''.join(random.choices(string.ascii_lowercase + string.digits + string.ascii_uppercase, k=8))

    glbd = goss_log_base_dir()
    return f"{glbd}/{script_name}/{timestamp}-{mypid}-{randstring}"

def log_values(logmethod, **kwargs):
    for k, v in kwargs.items():
        # For dictionary values, format them nicely
        if isinstance(v, dict):
            logmethod(f"{k}=\n" + json.dumps(v, indent=2))
        else:
            logmethod(f"{k}={v}")

def log_goss_env_variables(logmethod):
    log_values(logmethod=logmethod, **goss_env_variables())

def stderr_print(s):
    sys.stderr.write(f"{s}\n")
    sys.stderr.flush()

def stdout_print(s):
    sys.stdout.write(f"{s}\n")
    sys.stdout.flush()

def multi_print(s, *methods):
    for m in methods:
        m(s)

def get_hostname():
    return socket.gethostname()

ncn_num_pattern="([1-9][0-9][0-9]|0[1-9][0-9]|00[1-9])"
ncn_pattern = f"^ncn-[msw]{ncn_num_pattern}$"
ncn_master_pattern = f"^ncn-m{ncn_num_pattern}$"
ncn_storage_pattern = f"^ncn-s{ncn_num_pattern}$"
ncn_worker_pattern = f"^ncn-w{ncn_num_pattern}$"

ncn_re_prog = re.compile(ncn_pattern)
ncn_master_re_prog = re.compile(ncn_master_pattern)
ncn_storage_re_prog = re.compile(ncn_storage_pattern)
ncn_worker_re_prog = re.compile(ncn_worker_pattern)

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

def is_ncn_name(n):
    if ncn_re_prog.match(n):
        return True
    return False

def is_master_ncn_name(n):
    if ncn_master_re_prog.match(n):
        return True
    return False

def is_storage_ncn_name(n):
    if ncn_storage_re_prog.match(n):
        return True
    return False

def is_worker_ncn_name(n):
    if ncn_worker_re_prog.match(n):
        return True
    return False

def get_ncn_type(ncn_name):
    if is_master_ncn_name(ncn_name):
        return "master"
    elif is_storage_ncn_name(ncn_name):
        return "storage"
    elif is_worker_ncn_name(ncn_name):
        return "worker"
    raise ScriptException(f"Unexpected NCN name format: {ncn_name}")

def my_ncn_type():
    return get_ncn_type(get_hostname())

def argparse_nonempty_string(s):
    if len(s) > 0:
        return s
    raise argparse.ArgumentTypeError("Arguments may not be blank")

def argparse_yaml_file_name(s):
    try:
        argparse_nonempty_string(s)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError("YAML file names may not be blank")
    if s[-5:] == ".yaml":
        return s
    raise argparse.ArgumentTypeError(f"YAML file names are expected to have .yaml extension. Invalid: {s}")

def argparse_valid_ncn_name(n):
    if is_ncn_name(n):
        return n
    raise argparse.ArgumentTypeError(f"Invalid NCN name: {n}")

def fmt_exc(e):
    return f"{type(e).__name__}: {e}"

goss_endpoints_by_ncn_type = None

def load_goss_endpoints():
    """
    Reads Goss server configuration file (goss-servers.json) and for each NCN type, generates a mapping from
    port number to endpoint name + suite name.
    These mappings are returned.
    """
    global goss_endpoints_by_ncn_type
    if goss_endpoints_by_ncn_type != None:
        return goss_endpoints_by_ncn_type
    config_file = goss_servers_config()
    if not os.path.isfile(config_file):
        raise ScriptException(f"Goss server configuration file does not exist or is not a regular file: {config_file}")
    
    start_port=0
    end_port=0
    suite_types_list = list()
    with open(config_file, "rt") as f:
        for line in f.readlines():
            line = line.strip()
            if len(line) == 0 or line[0] == "#":
                continue
            fields = line.split()
            if fields[0] == "start_port":
                if start_port != 0:
                    raise ScriptException(f"Server configuration ({config_file}) error: multiple start_port lines")
                elif len(fields) != 2:
                    raise ScriptException(f"Server configuration ({config_file}) error: start_port line must have exactly two fields. Invalid line: {line}")
                port_string = fields[1]
                if not port_re_prog.match(port_string):
                    raise ScriptException(f"Server configuration ({config_file}) error: Invalid port format: {line}")
                start_port = int(port_string)
                if end_port != 0 and start_port > end_port:
                    raise ScriptException(f"Server configuration ({config_file}) error: start_port ({start_port}) must be <= end_port ({end_port})")
                continue
            elif fields[0] == "end_port":
                if end_port != 0:
                    raise ScriptException(f"Server configuration ({config_file}) error: multiple end_port lines")
                elif len(fields) != 2:
                    raise ScriptException(f"Server configuration ({config_file}) error: end_port line must have exactly two fields. Invalid line: {line}")
                port_string = fields[1]
                if not port_re_prog.match(port_string):
                    raise ScriptException(f"Server configuration ({config_file}) error: Invalid port format: {line}")
                end_port = int(port_string)
                if start_port > end_port:
                    raise ScriptException(f"Server configuration ({config_file}) error: end_port ({end_port}) must be >= start_port ({start_port})")
                continue
            elif fields[0] != "suite":
                raise ScriptException(f"Server configuration ({config_file}) error: Unexpected line format: {line}")
            # suite line
            if len(fields) < 3:
                raise ScriptException(f"Server configuration ({config_file}) error: suite line must have at least three fields. Invalid line: {line}")
            try:
                suite = argparse_yaml_file_name(fields[1])
            except argparse.ArgumentTypeError:
                raise ScriptException(f"Server configuration ({config_file}) error: Invalid YAML suite file name: {line}")
            if any( s == suite for (s, t) in suite_types_list ):
                raise ScriptException(f"Server configuration ({config_file}) error: suite should only be specified on a single line. Duplicated suite: {line}")
            type_list = fields[2:]
            if not all(t in NCN_TYPES for t in type_list):
                raise ScriptException(f"Server configuration ({config_file}) error: Invalid NCN type listed on suite line: {line}")
            suite_types_list.append( (suite, type_list) )
            continue
    if start_port == 0:
        raise ScriptException(f"Server configuration ({config_file}) error: No start_port line")
    elif end_port == 0:
        raise ScriptException(f"Server configuration ({config_file}) error: No end_port line")
    elif len(suite_types_list) == 0:
        raise ScriptException(f"Server configuration ({config_file}) error: No suites specified")

    endpoints_by_type = { ntype: list() for ntype in NCN_TYPES }

    for (suite, type_list) in suite_types_list:
        for ntype in type_list:
            port = len(endpoints_by_type[ntype]) + start_port
            if port > end_port:
                raise ScriptException(f"Server configuration ({config_file}) error: Too many {ntype} suites for given port game ({start_port}-{end_port})")
            # Endpoint name is the suite name, minus the .yaml extension
            endpoint_name = suite[:-5]
            endpoints_by_type[ntype].append( (suite, endpoint_name, port) )

    goss_endpoints_by_ncn_type = endpoints_by_ncn_type
    return goss_endpoints_by_ncn_type
