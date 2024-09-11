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

"""
This script executes deletion of logs , workflows and directories created for an iuf activity.
"""

import subprocess
import sys
from pathlib import Path

LOG_DIR= "/etc/cray/upgrade/csm/iuf"
MEDIA_DIR= "/etc/cray/upgrade/csm/automation-tests"

def get_workflows(activity_name):
    command = f"iuf -a {activity_name} workflow"
    workflows=[]
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if not result.returncode:
            workflows=result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        return e.returncode
    return workflows

def main(activity_name = "test-activity"):
    command_delete_logs = f"rm -r {LOG_DIR}/{activity_name}"
    command_delete_media_dir = f"rm -r {MEDIA_DIR}"
    try:
        workflows = get_workflows(activity_name)
        if isinstance(workflows, list) and all(isinstance(wf, str) for wf in workflows) :
            print(f"Workflows found for {activity_name} :{workflows}")
            for workflow in workflows:
                command_delete_workflow = f"kubectl delete workflow {workflow} -n argo"
                result = subprocess.run(command_delete_workflow, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                print("Command output:", result.stdout)
        logs_path = Path(f"{LOG_DIR}/{activity_name}")
        if logs_path.is_dir():
            print(f"{logs_path} exists.")
            result = subprocess.run(command_delete_logs, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        else:
            print(f"{logs_path} does not exist.")
        media_path = Path(MEDIA_DIR)         
        if media_path.is_dir():
            print(f"{media_path} exists.")
            result = subprocess.run(command_delete_media_dir, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        else:
            print(f"{media_path} does not exist." )   
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Usage: script.py <ACTIVITY_NAME>")
        sys.exit(1)
    elif len(sys.argv) == 2:
        activity_name = sys.argv[1]
        exit_code = main(activity_name)
        sys.exit(exit_code)
    else:
        exit_code = main()
        sys.exit(exit_code)
