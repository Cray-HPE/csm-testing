#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
"""Shared Python function library: HSM: Groups"""

from typing import List, Union
from typing_extensions import Required, TypedDict

from csm_testing.lib.api_requests import get_retry_validate
from csm_testing.lib.hsm.defs import HSM_V2_BASE_URL

SMD_HSM_GROUPS_URL = f"{HSM_V2_BASE_URL}/groups"


class GroupMembersInfo(TypedDict, total=False):
    """
    https://github.com/Cray-HPE/hms-smd/blob/master/api/swagger_v2.yaml
    '#/definitions/Members.1.0.0'
    """
    ids: List[str]


class GroupInfo(TypedDict, total=False):
    """
    https://github.com/Cray-HPE/hms-smd/blob/master/api/swagger_v2.yaml
    '#/definitions/Group.1.0.0'
    """
    label: Required[str]
    description: str
    exclusiveGroup: str
    tags: List[str]
    members: GroupMembersInfo


def get_group(group_name: str) -> Union[GroupInfo, None]:
    """
    Returns the data about the group if it exists, otherwise returns None
    """
    resp = get_retry_validate(url=f"{SMD_HSM_GROUPS_URL}/{group_name}",
                              expected_status_codes=(200,404),
                              add_api_token=True)
    if resp.status_code == 404:
        return None
    return resp.json()


def get_members(group: GroupInfo) -> List[str]:
    """
    Return the 'ids' list of the group members, if available.
    Otherwise return an empty list
    """
    return group.get("members", {}).get("ids", [])
