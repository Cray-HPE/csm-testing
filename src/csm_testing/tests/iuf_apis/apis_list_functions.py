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
import requests
from csm_testing.tests.iuf_apis.apis_activity_functions import (
    print_no_of_test_passed, )


def no_auth_list_stages(count: int):
    """
    Function to try and access apis without a token
    Args:
        None
    Returns:
        None
    """
    print("TEST CASE: w/o security API call: Try Api Call without token")
    try:
        api_response = requests.get(
            "https://api-gw-service-nmn.local/apis/iuf/v1/stages")
        if api_response is not None:
            msg = "ERROR: Api Working without token"
            print_no_of_test_passed(msg, count)
    except HTTPError as err:
        print(f"INFO: {err}")
        count += 1
        return count


def list_stages(apis, count: int):
    """
    Function to list iuf stages
    Args:
        apis: ApiInterface Object
    """
    print("TEST CASE: List Stages")
    try:
        stage_result = apis.get_stages()
        print(stage_result)
        stages = stage_result.json()
    except HTTPError as ex:
        print_no_of_test_passed(ex, count)

    if stages is not None:
        stage_list = [stage["name"] for stage in stages["stages"]]
        print("\n".join(stage_list))
        count += 1
        return count
    msg = ""
    print_no_of_test_passed(msg, count)


def list_activities(apis, count: int):
    """
    Function to list iuf activities
    Args:
        apis: ApiInterface object
    """
    print("TEST CASE: List Activities")
    try:
        activities_result = apis.get_activities()
        print(activities_result)
        count += 1
        activities = activities_result.json()
    except HTTPError as ex:
        print_no_of_test_passed(ex, count)

    if activities is not None:
        act_list = sorted([act["name"] for act in activities])
        print("\n".join(act_list))
    return count
