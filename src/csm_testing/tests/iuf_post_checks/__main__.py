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
"""
This script performs post-checks for IUF run by checking if
    1. log directory was created
    2. activity specific configmap was created
    3. state directory was created and relevant files are present inside or not.
"""

import os
import subprocess
import sys
from csm_testing.lib.iuf_constants import MEDIA_DIR


def check_logs(activity: str):
    """
    Function to check the logs for the activity and print the info.
    Args:
        activity(str): Activity name
    Returns:
        None
    """
    # Define the log directory path
    log_dir = f"/etc/cray/upgrade/csm/iuf/{activity}/log"

    # Check if the log directory exists
    if os.path.exists(log_dir):
        print(f"TEST CASE: Log directory exists for activity: {activity}")
    else:
        print(f"ERROR: Log directory does NOT exist for activity: {activity}")
        sys.exit(1)


def check_configmap(activity: str):
    """
    Function to check the configmap for the activity and print the info.
    Args:
        activity(str): Activity name
    Returns:
        None
    """
    configmap_name = activity
    namespace = "argo"

    try:
        # Use kubectl command to check if the configmap exists in the Argo namespace
        subprocess.run(
            ["kubectl", "get", "configmap", configmap_name, "-n", namespace],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        print(
            f"TEST CASE: ConfigMap '{configmap_name}' exists in the '{namespace}' namespace."
        )

    except subprocess.CalledProcessError as err:
        print(
            f"ERROR: ConfigMap '{configmap_name}' does NOT exist in the '{namespace}' namespace.\n\
Error: {err}")
        sys.exit(1)


def check_state(activity: str):
    """
    Function to check the contents of the state directory.
    Args:
        activity(str): Activity name
    Returns:
        None
    """
    state_dir = f"/etc/cray/upgrade/csm/iuf/{activity}/state"

    print("INFO: Checking for state folder contents")
    if os.path.exists(state_dir):
        print(f"TEST CASE: State directory exists for activity: {activity}")
        if os.path.exists(f"{state_dir}/activity_dict.yaml"):
            print(
                f"TEST CASE: activity_dict.yaml present for {activity} in state folder"
            )
        else:
            print(
                f"ERROR: activity_dict.yaml not present for {activity} in state folder"
            )
            sys.exit(1)

        if os.path.exists(f"{state_dir}/stage_hist.yaml"):
            print(
                f"TEST CASE: stage_hist.yaml present for {activity} in state folder"
            )
        else:
            print(
                f"ERROR: stage_hist.yaml not present for {activity} in state folder"
            )
            sys.exit(1)
    else:
        print(
            f"ERROR: State directory does NOT exist for activity: {activity}")
        sys.exit(1)

    print("INFO:Checking session_vars")
    if os.path.exists(f"{MEDIA_DIR}/session_vars.yaml"):
        print(f"TEST CASE: session_vars present for {activity} ")
    else:
        print(f"ERROR: session_vars not present for {activity} ")
        sys.exit(1)


def main():
    """
    The main entry point of the program.
    Args:
        None
    Returns:
        None
    """
    print()
    print("INFO: Running IUF post-checks...")
    if len(sys.argv) > 2:
        print("Usage: iuf_post_checks.py <ACTIVITY_NAME>")
        sys.exit(1)
    activity_name = sys.argv[1]
    check_state(activity_name)
    check_logs(activity_name)
    check_configmap(activity_name)
    print(
        "------------------------ END OF POST-CHECKS ------------------------")
    print()


if __name__ == "__main__":
    main()
