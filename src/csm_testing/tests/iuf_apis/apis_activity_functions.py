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
This script calls the activity apis and is being imported by __main__.py for iuf_apis
"""
import sys
import copy
from urllib.error import HTTPError
import requests

COUNT = 0
TOTAL_COUNT = 15


def print_no_of_test_passed(ex):
    """
    Function to print the number of test cases passed
    Args:
        ex(str): the messages to be printed
    Returns:
        None
    """
    print(f"ERROR: {ex}")
    print("~" * 50)
    print(
        f"INFO: TOTAL test cases passed: {COUNT} test cases skipped: {TOTAL_COUNT - COUNT}"
    )
    print("~" * 50)
    sys.exit(1)


def activity_create(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Create Activity")
    print(f"INFO: Attempting to create activity {activity}")
    payload = {"input_parameters": {}, "name": activity}

    if not apis.activity_exists(activity):
        try:
            print(apis.post_activity(payload))
            print(f"INFO: Created activity: {activity}")
            COUNT += 1
        except HTTPError as ex:
            print(f"ERROR: Unable to create activity: {activity}")
            print_no_of_test_passed(ex)
    else:
        print("WARNING: Skipping the test case: Create Activity")
        print(f"INFO: Activity {activity} already exists")


def activity_run(
    apis, activity, media_dir
):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Run Activity")
    print(f"INFO: Attempting to run activity {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    payload = {
        "input_parameters": {
            media_dir: media_dir,
            "site_parameters": "",
            "limit_management_nodes": None,
            "limit_managed_nodes": ["Compute"],
            "managed_rollout_strategy": "stage",
            "concurrent_management_rollout_percentage": 20,
            "media_host": "ncn-m001",
            "concurrency": 0,
            "bootprep_config_managed": "",
            "bootprep_config_management": "",
            "stages": ["process-media"],
            "force": False,
        },
        "name": activity,
    }
    print("TEST CASE: Patch Activity")
    try:
        print(apis.post_activity_history_run(activity, payload))
        COUNT += 1
        print(f"INFO: Activity {activity} is started")

        # Generate site_parameters and patch the activity.
        patched_payload = copy.deepcopy(payload)
        # patched_payload["site_parameters"] = self.site_conf.site_params

        # Remove the "force" key from input_parameters for the patched
        # activity.
        patched_payload["input_parameters"].pop("force", None)
        print(f"INFO: Patch activity: {activity}")
        print(apis.patch_activity(activity, patched_payload))
        COUNT += 1

    except HTTPError as ex:
        print(f"ERROR: Unable to run activity {activity}")
        print_no_of_test_passed(ex)


def activity_abort(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Abort Activity")
    print(f"INFO: Attempting to abort activity {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    payload = {
        "input_parameters": {},
        "name": activity,
        "comment": "sending an abort",
        "force": None,
    }
    try:
        print(apis.abort_activity(activity, payload))
        print(f"INFO: Aborted activity: {activity}")
        COUNT += 1
    except requests.ReadTimeout:
        print("ERROR: Timed out sending an abort request.")
        msg = f"ERROR: Ensure the argo workflow for {activity} is not running."
        print_no_of_test_passed(msg)
    except HTTPError as ex:
        print(f"ERROR: Unable to abort activity: {activity}")
        print_no_of_test_passed(ex)


def activity_resume(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Resume Activity")
    print(f"INFO: Attempting to resume activity {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    payload = {
        "input_parameters": {},
        "comment": "Restart activity ",
        "activity_name": activity,
        "force": False,
    }

    try:
        api_results = apis.post_resume(activity, payload)
        print(api_results)
        print(f"INFO: Resumed activity: {activity}")
        COUNT += 1
    except HTTPError as ex:
        print(f"ERROR: Unable to resume activity {activity}")
        print_no_of_test_passed(ex)


def activity_restart(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Restart Activity")
    print(f"INFO: Attempting to restart activity {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    payload = {
        "input_parameters": {},
        "comment": "Restart activity ",
        "activity_name": activity,
        "force": False,
    }

    try:
        api_results = apis.post_restart(activity, payload)
        print(api_results)
        print(f"INFO: Restarted activity: {activity}")
        COUNT += 1
    except HTTPError as ex:
        print(f"ERROR: Unable to restart activity: {activity}")
        print_no_of_test_passed(ex)
