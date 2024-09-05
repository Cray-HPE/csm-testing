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
This script executes logs deletion for an iuf activity.
"""

import subprocess
import sys

ACTIVITY_NAME = "test-activity"
LOG_DIR= "/etc/cray/upgrade/csm/iuf"
MEDIA_DIR= "/etc/cray/upgrade/csm/automation-tests"

def get_workflow():
    command = f"iuf -a {ACTIVITY_NAME} workflow"
    workflows=[]
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)
        workflows=result.stdout.splitlines()
        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr.strip()}")
        return e.returncode
    
    return workflows

def main():
    command_delete_logs = f"rm -r {LOG_DIR}/{ACTIVITY_NAME}"
    command_delete_media_dir = f"rm -r {MEDIA_DIR}"
    try:
        result = subprocess.run(command_delete_logs, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)
        result = subprocess.run(command_delete_media_dir, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)

        workflows = get_workflow()
        for workflow in workflows:
            command_delete_workflow = f"kubectl delete workflow {workflow} -n argo"
            result = subprocess.run(command_delete_workflow, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            print("Command output:", result.stdout)
                  
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
