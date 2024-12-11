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
from csm_testing.lib.iuf_constants import MEDIA_DIR

LOG_DIR = "/etc/cray/upgrade/csm/iuf"


def get_workflows(activity_name):
    """
    Function to get the list of workflows for the activity.
    Args:
        activity_name(str): The activity name whose workflows list needs to be generated
    Returns:
        configmaps(List[str]): List of workflows for the activity
    """
    command = f"kubectl get workflow -n argo -o \
custom-columns=NAME:.metadata.name|grep {activity_name}"
    workflows = []
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if not result.returncode:
            workflows = result.stdout.splitlines()
    except subprocess.CalledProcessError as err:
        return err.returncode
    return workflows


def get_configmaps(activity_name):
    """
    Function to get the list of configmaps for the activity.
    Args:
        activity_name(str): The activity name whose configmaps list needs to be generated
    Returns:
        configmaps(List[str]): List of configmaps for the activity
    """
    command = f"kubectl get configmap -n argo -o \
custom-columns=NAME:.metadata.name|grep {activity_name}"
    configmaps = []
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if not result.returncode:
            configmaps = result.stdout.splitlines()
    except subprocess.CalledProcessError as err:
        return err.returncode
    return configmaps

# pylint: disable=too-many-branches
def cleanup(activity_name="test-activity"):
    """
    Function to remove the log files, media directories, workflows and configmaps for the activity.
    Args:
        activity_name(str, optional): The activity name whose logs, media dir(s),
                                      workflows and configmaps need to be deleted.
                                      Defaults to "test-activity".
    Returns:
        None

    """
    command_delete_logs = f"rm -r {LOG_DIR}/{activity_name}"
    command_delete_media_dir = f"rm -r {MEDIA_DIR}"
    try:
        # Deleting log files for the activity
        logs_path = Path(f"{LOG_DIR}/{activity_name}")
        if logs_path.is_dir():
            print(
                f"INFO: {logs_path} exists. Deleting log directory for activity: {activity_name}"
            )
            result = subprocess.run(
                command_delete_logs,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        else:
            print(f"WARNING: {logs_path} does not exist.")

        # Deleting media dir for the activity
        media_path = Path(MEDIA_DIR)
        if media_path.is_dir():
            print(
                f"INFO: {media_path} exists. Deleting media directory for activity: {activity_name}"
            )
            result = subprocess.run(
                command_delete_media_dir,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        else:
            print(f"WARNING: {media_path} does not exist.")

        # Deleting workflows for the activity
        workflows = get_workflows(activity_name)
        if isinstance(workflows, list) and all(isinstance(wf, str) for wf in workflows):
            print(f"INFO: Workflows found for {activity_name} :{workflows}")
            for workflow in workflows:
                command_delete_workflow = f"kubectl delete workflow {workflow} -n argo"
                try:
                    result = subprocess.run(
                        command_delete_workflow,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )
                    print("INFO: Command output:", result.stdout)
                # Handles the case when the command fails (non-zero exit code)
                except subprocess.CalledProcessError as err:
                    print(f"ERROR: Command failed with an error: {err}")
                # Handles all other errors
                except Exception as err:    # pylint: disable=W0703
                    print(f"ERROR: Unable to delete workflow {workflow} , {err}")
        else:
            print(f"WARNING: Workflows not found for {activity_name}")
            sys.exit(1)

        # Deleting configmaps for the activity
        configmaps = get_configmaps(activity_name)
        if isinstance(configmaps, list) and all(
            isinstance(cm, str) for cm in configmaps
        ):
            print(f"INFO: configmaps found for {activity_name} :{configmaps}")
            for configmap in configmaps:
                command_delete_configmap = (
                    f"kubectl delete configmap {configmap} -n argo"
                )
                try:
                    result = subprocess.run(
                        command_delete_configmap,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )
                    print("INFO: Command output:", result.stdout)
                # Handles the case when the command fails (non-zero exit code)
                except subprocess.CalledProcessError as err:
                    print(f"ERROR: Command failed with an error: {err}")
                # Handles all other errors
                except Exception as err:    # pylint: disable=W0703
                    print(f"ERROR: Unable to delete configmap {configmap} , {err}")
        else:
            print(f"WARNING: Workflows not found for {activity_name}")
            sys.exit(1)
    except subprocess.CalledProcessError as err:
        print(f"ERROR: {err}")
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
    print("INFO: Running cleanup..")
    if len(sys.argv) > 2:
        print("Usage: script.py <ACTIVITY_NAME>")
        sys.exit(1)
    elif len(sys.argv) == 2:
        activity_name = sys.argv[1]
        cleanup(activity_name)
    else:
        cleanup()


if __name__ == "__main__":
    main()
