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

def goss_base_dirs(validate: bool = False) -> tuple[str, str]:
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
            base_dir = f"{install_base_dir}/livecd"
        else:
            base_dir = f"{install_base_dir}/ncn"

        if validate and not os.path.isdir(base_dir):
            raise ScriptException(f"GOSS_BASE directory does not exist or is not a directory: {base_dir}")

    return install_base_dir, base_dir

def goss_install_base_dir(*args, **kwargs) -> str:
    return goss_base_dirs(*args, **kwargs)[0]

def goss_base(*args, **kwargs) -> str:
    return goss_base_dirs(*args, **kwargs)[1]

def goss_script_log_level() -> int:
    # Make it uppercase, just so that people who accidentally set a lowercase
    # log level are not tripped up
    requested_log_level = os.environ.get("GOSS_SCRIPT_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return logging.getLevelName(requested_log_level)

def goss_servers_config(validate: bool = False) -> str:
    gibd = goss_install_base_dir()
    config_file = os.environ.get("GOSS_SERVERS_CONFIG", f"{gibd}/dat/goss-servers.cfg")
    if validate and not os.path.isfile(config_file):
        raise ScriptException(f"GOSS_SERVERS_CONFIG file does not exist or is not a file: {config_file}")
    return config_file

def goss_log_base_dir(validate: bool = False) -> str:
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

def err_text(s: str) ->str:
    return f"{ERR_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def warn_text(s: str) -> str:
    return f"{WARN_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def ok_text(s: str) -> str:
    return f"{OK_TEXT_CODE}{s}{RESET_TEXT_CODE}"

def is_pit_node() -> bool:
    return os.path.isfile(PIT_NODE_RELEASE_FILE)

def goss_suites_dir() -> str:
    return f"{goss_base()}/suites"

def goss_env_variables() -> dict:
    return { 
        "GOSS_INSTALL_BASE_DIR": goss_install_base_dir(),
        "GOSS_SCRIPT_LOG_LEVEL": goss_script_log_level(),
        "GOSS_SERVERS_CONFIG": goss_servers_config(),
        "GOSS_LOG_BASE_DIR": goss_log_base_dir(),
        "GOSS_BASE": goss_base() }

def log_dir(script_name: str) -> str:
    # Strip off path and .py, if present, in script name
    script_name = script_name.split('/')[-1]
    if script_name[-3:] == ".py":
        script_name = script_name[:-3]

    mypid = os.getpid()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S.%f')
    randstring = ''.join(random.choices(string.ascii_lowercase + string.digits + string.ascii_uppercase, k=8))

    glbd = goss_log_base_dir()
    return f"{glbd}/{script_name}/{timestamp}-{mypid}-{randstring}"

def log_values(logmethod: function, **kwargs) -> None:
    for k, v in kwargs.items():
        # For dictionary values, format them nicely
        if isinstance(v, dict):
            try:
                logmethod(f"{k}=\n" + json.dumps(v, indent=2))
                continue
            except TypeError:
                # This can happen if the dict contains stuff that cannot be serialized as JSON
                pass
        logmethod(f"{k}={v}")

def log_goss_env_variables(logmethod: function) -> None:
    log_values(logmethod=logmethod, **goss_env_variables())

def stderr_print(s: str) -> None:
    sys.stderr.write(f"{s}\n")
    sys.stderr.flush()

def stdout_print(s: str) -> None:
    sys.stdout.write(f"{s}\n")
    sys.stdout.flush()

def multi_print(s: str, *methods) -> None:
    for m in methods:
        m(s)

def get_hostname() -> str:
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

def is_ncn_name(n: str) -> bool:
    if ncn_re_prog.match(n):
        return True
    return False

def is_master_ncn_name(n: str) -> bool:
    if ncn_master_re_prog.match(n):
        return True
    return False

def is_storage_ncn_name(n: str) -> bool:
    if ncn_storage_re_prog.match(n):
        return True
    return False

def is_worker_ncn_name(n: str) -> bool:
    if ncn_worker_re_prog.match(n):
        return True
    return False

def get_ncn_type(ncn_name: str) -> str:
    if is_master_ncn_name(ncn_name):
        return "master"
    elif is_storage_ncn_name(ncn_name):
        return "storage"
    elif is_worker_ncn_name(ncn_name):
        return "worker"
    raise ScriptException(f"Unexpected NCN name format: {ncn_name}")

def my_ncn_type() -> str:
    return get_ncn_type(get_hostname())

def argparse_nonempty_string(s: str) -> str:
    if len(s) > 0:
        return s
    raise argparse.ArgumentTypeError("Arguments may not be blank")

def argparse_yaml_file_name(s: str) -> str:
    try:
        argparse_nonempty_string(s)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError("YAML file names may not be blank")
    if s[-5:] == ".yaml":
        return s
    raise argparse.ArgumentTypeError(f"YAML file names are expected to have .yaml extension. Invalid: {s}")

def argparse_valid_ncn_name(n: str) -> str:
    if is_ncn_name(n):
        return n
    raise argparse.ArgumentTypeError(f"Invalid NCN name: {n}")

def fmt_exc(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"
