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
"""Shared Python function library: HSM: State/Components"""

from typing import List, Optional

from csm_testing.lib.api_requests import get_retry_validate
from csm_testing.lib.hsm.defs import MGMT_NCN_HSM_SUBROLE, HSM_V2_BASE_URL

SMD_HSM_COMPONENTS_URL = f"{HSM_V2_BASE_URL}/State/Components"


def get_management_ncn_xnames(subrole: Optional[MGMT_NCN_HSM_SUBROLE] = None) -> List[str]:
    """
    Return a sorted list of the xnames of the management NCNs
    """
    params = {"type": "Node", "role": "Management"}
    if subrole is not None:
        params["subrole"] = subrole
    resp = get_retry_validate(url=SMD_HSM_COMPONENTS_URL, expected_status_codes=200,
                              add_api_token=True, params=params)
    component_list = resp.json()["Components"]
    return sorted([comp["ID"] for comp in component_list])
