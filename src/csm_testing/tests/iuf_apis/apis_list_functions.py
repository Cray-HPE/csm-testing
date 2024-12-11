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
This script calls the list apis and is being imported by __main__.py for iuf_apis
"""

from urllib.error import HTTPError
from csm_testing.lib.iuf_classes import ApiInterface
from csm_testing.tests.iuf_apis.apis_activity_functions import (
    COUNT,
    print_no_of_test_passed,
)


def no_auth_list_stages():  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: w/o security API call: Try Api Call without token")
    apis = ApiInterface()
    api_path = "/stages"
    try:
        api_response = apis.request("GET", api_path, token=None)
        if api_response is not None:
            msg = "ERROR: Api Working without token"
            print_no_of_test_passed(msg)
    except HTTPError as err:
        print(f"INFO: {err}")
        COUNT += 1


def list_stages(apis):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: List Stages")
    try:
        stage_result = apis.get_stages()
        print(stage_result)
        stages = stage_result.json()
    except HTTPError as ex:
        print_no_of_test_passed(ex)

    if stages is not None:
        stage_list = [stage["name"] for stage in stages["stages"]]
        print("\n".join(stage_list))
        COUNT += 1
    else:
        msg = ""
        print_no_of_test_passed(msg)


def list_activities(apis):  # pylint: disable=missing-function-docstring
    global COUNT  # pylint: disable=global-statement
    print("TEST CASE: List Activities")
    try:
        activities_result = apis.get_activities()
        print(activities_result)
        COUNT += 1
        activities = activities_result.json()
    except HTTPError as ex:
        print_no_of_test_passed(ex)

    if activities is not None:
        act_list = sorted([act["name"] for act in activities])
        print("\n".join(act_list))
