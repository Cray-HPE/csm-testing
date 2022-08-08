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

import colorama
from datetime import datetime
import json
import logging
import os
import random
import socket
import string
import sys

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_GOSS_INSTALL_BASE_DIR = "/opt/cray/tests/install"
PIT_NODE_RELEASE_FILE = "/etc/pit-release"

def goss_script_log_level():
    # Make it uppercase, just so that people who accidentally set a lowercase
    # log level are not tripped up
    requested_log_level = os.environ.get("GOSS_SCRIPT_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return logging.getLevelName(requested_log_level)

def goss_install_base_dir():
    return os.environ.get("GOSS_INSTALL_BASE_DIR", DEFAULT_GOSS_INSTALL_BASE_DIR)

def goss_servers_config():
    gibd = goss_install_base_dir()
    return os.environ.get("GOSS_SERVERS_CONFIG", f"{gibd}/dat/goss-servers.cfg")

def goss_log_base_dir():
    gibd = goss_install_base_dir()
    return f"{gibd}/logs"

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

def goss_base():
    try:
        return os.environ["GOSS_BASE"]
    except KeyError:
        gibd = goss_install_base_dir()
        if is_pit_node():
            return f"{gibd}/livecd"
        else:
            return f"{gibd}/ncn"

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
