#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP
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

import os
import subprocess
import sys

MEDIA_DIR = "/etc/cray/upgrade/csm/automation-tests"

def check_logs(activity):
    # Define the log directory path
    LOG_DIR = f"/etc/cray/upgrade/csm/iuf/{activity}/log"
    
    # Check if the log directory exists
    if os.path.exists(LOG_DIR):
        print(f"Log directory exists for activity: {activity}")
    else:
        print(f"Log directory does NOT exist for activity: {activity}")
    
def check_configmap(activity):
    configmap_name = activity
    namespace = "argo"
    
    try:
        # Use kubectl command to check if the configmap exists in the Argo namespace
        result = subprocess.run(
            ["kubectl", "get", "configmap", configmap_name, "-n", namespace],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        print(f"ConfigMap '{configmap_name}' exists in the '{namespace}' namespace.")
    except subprocess.CalledProcessError as e:
        print(f"ConfigMap '{configmap_name}' does NOT exist in the '{namespace}' namespace.\nError: {e}")

def check_state(activity):
    STATE_DIR=f"/etc/cray/upgrade/csm/iuf/{activity}/state"

    print("INFO: Checking for state folder contents")
    if os.path.exists(STATE_DIR):
        print(f"State directory exists for activity: {activity}")
        if os.path.exists(f"{STATE_DIR}/activity_dict.yaml"):
            print(f"activity_dict.yaml present for {activity} in state folder")
        else:
            print(f"activity_dict.yaml not present for {activity} in state folder")
        
        if os.path.exists(f"{STATE_DIR}/stage_hist.yaml"):
            print(f"stage_hist.yaml present for {activity} in state folder")
        else:
            print(f"stage_hist.yaml not present for {activity} in state folder")
    else:
        print(f"State directory does NOT exist for activity: {activity}")

    print("Checking session_vars")
    if os.path.exists(f"{MEDIA_DIR}/session_vars.yaml"):
        print(f"session_vars present for {activity} ")
    else:
        print(f"session_vars not present for {activity} ")

if __name__ == "__main__":
    print()
    print("INFO: Running IUF post-checks...")
    if len(sys.argv) > 2:
        print("Usage: iuf_post_checks.py <ACTIVITY_NAME>")
        sys.exit(1)
    activity_name = sys.argv[1]
    exit_code =check_logs(activity_name)
    exit_code = check_configmap(activity_name)
    exit_code = check_state(activity_name)
    print("------------------------ END OF POST-CHECKS ------------------------")
    print()
    sys.exit(exit_code)
