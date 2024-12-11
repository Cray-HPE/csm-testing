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
This script executes session apis testing.
"""

from urllib.error import HTTPError
from csm_testing.tests.iuf_apis.apis_activity_functions import (
    COUNT,
    print_no_of_test_passed,
)


def get_sessions(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Get Sessions")
    print(f"INFO: Get Sessions for activity: {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"INFO: Sessions for activity: {activity}")
        sessions = sessions_result.json()
    except HTTPError as ex:
        print(f"ERROR: Unable to get sessions for activity: {activity}")
        print_no_of_test_passed(ex)

    if sessions is not None:
        session_list = [session["name"] for session in sessions]
        print("\n".join(session_list))
        COUNT += 1
    else:
        msg = f"ERROR: Sessions not found for activity: {activity}"
        print_no_of_test_passed(msg)


def get_workflows(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Get Workflows")
    print(f"INFO: Get Workflows for activity: {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"INFO: Workflows for activity: {activity}")
        sessions = sessions_result.json()
    except HTTPError as ex:
        print(f"ERROR: Unable to get workflows for activity: {activity}")
        print_no_of_test_passed(ex)

    if sessions is not None:
        session_workflows = [session["workflows"] for session in sessions]
        workflow_list = []
        for session_workflow in session_workflows:
            for workflow in session_workflow:
                workflow_list.append(workflow["id"])
        print("\n".join(workflow_list))
        COUNT += 1
    else:
        msg = f"ERROR: workflows not found for activity: {activity}"
        print(msg)


def get_history(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Get History")
    print(f"INFO: Get history for activity: {activity}")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    try:
        history = apis.get_activity_history(activity)
    except HTTPError as ex:
        print(f"ERROR: Unable to get history for activity: {activity}")
        print_no_of_test_passed(ex)

    if history is not None:
        print(history)
        COUNT += 1
    else:
        msg = "ERROR: History not found for activity: {activity}"
        print_no_of_test_passed(msg)


def get_history_time(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Get History/time")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print_no_of_test_passed(msg)
    try:
        history = apis.get_activity_history(activity).json()
    except HTTPError as ex:
        print(f"ERROR: Unable to get history for activity: {activity}")
        print_no_of_test_passed(ex)
    if history is not None:
        time = history[0]["start_time"]
    else:
        msg = "ERROR: History not found"
        print_no_of_test_passed(msg)

    print(f"INFO: Get history/time for activity: {activity} , time:{time}")
    try:
        history_time = apis.get_activity_history_time(activity, time)
    except HTTPError as ex:
        print(
            f"ERROR: Unable to get history/time for activity: {activity} , time:{time}"
        )
        print_no_of_test_passed(ex)

    if history_time is not None:
        print(history_time)
        COUNT += 1
    else:
        msg = "ERROR: history/time for activity: {activity} , time:{time} not found"
        print_no_of_test_passed(msg)


def get_activity_session(apis, activity):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: Get Activity Session")
    if not apis.activity_exists(activity):
        msg = f"ERROR: Activity {activity} does not exist."
        print(msg)
    sessions = apis.get_activity_sessions(activity).json()
    if sessions is not None:
        session = sessions[0]["name"]
    else:
        msg = f"ERROR: Sessions not found for activity: {activity}"
        print_no_of_test_passed(msg)

    print(f"INFO: Get activity/session for activity: {activity} , session:{session}")

    try:
        session = apis.get_activity_session(activity, session)
        print(session)
        COUNT += 1
    except HTTPError as ex:
        print(
            f"ERROR: Unable to get activity/session for activity: {activity} , session:{session}"
        )
        print_no_of_test_passed(ex)
