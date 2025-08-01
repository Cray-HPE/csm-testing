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
"""
Checks to make sure that if the iSCSI HSM group exists, that it contains at
least one worker NCN. This is because if the group exists but has no worker
NCNs in it, then no worker NCNs will be enabled for iSCSI. This in turn
means that no compute nodes will be able to boot. Because of this, it is
considered an error to be in this state. Hence this test.
"""

import sys

from csm_testing.lib.common import stderr_print
from csm_testing.lib.hsm.state_components import get_management_ncn_xnames
from csm_testing.lib.hsm.groups import get_group, get_members
from csm_testing.lib.iscsi_common import HSM_GROUP_NAME


def err(msg: str) -> None:
    """
    Prepends the message with ERROR: and prints to stderr
    """
    stderr_print(f"ERROR: {msg}")


def main() -> int:  # pylint: disable=missing-function-docstring
    # Get the iSCSI group. If it does not exist, we're done.
    hsm_group_info = get_group(HSM_GROUP_NAME)
    if hsm_group_info is None:
        # This means it does not exist
        print(f"iSCSI HSM group ({HSM_GROUP_NAME}) does not exist")
        print("PASSED")
        return 0

    group_members = get_members(hsm_group_info)

    if not group_members:
        err(f"iSCSI HSM group ({HSM_GROUP_NAME}) exists but has no members. "
            "This is not supported.")
        # Return a different error code for each error, so that even if someone
        # only sees the high level Goss status, they'll know how the test
        # failed
        return 10

    # There's no reason anyone should do it, but in theory the group could
    # have xnames in it that are not workers. This will have no effect on those
    # nodes, but it means that we cannot stop here just because the group
    # has members. We have to also make sure that at least one of those
    # members is a worker NCN.
    worker_ncns = get_management_ncn_xnames("Worker")

    if not worker_ncns:
        err("No Management_Worker NCNs found in HSM State/Components")
        return 15

    workers_in_group = set(worker_ncns).intersection(group_members)
    if len(workers_in_group) == 0:
        err(f"iSCSI HSM group ({HSM_GROUP_NAME}) exists and has members, but "
            "none of the members are worker NCNs. This is not supported.")
        return 20
    if len(workers_in_group) == 1:
        # This is not technically an error, but we will print a warning
        stderr_print(f"WARNING: iSCSI HSM group ({HSM_GROUP_NAME}) contains "
                     "only a single worker NCN, making it a single point of "
                     "failure for all booted managed nodes")
    else:
        print(f"iSCSI HSM group ({HSM_GROUP_NAME}) contains "
              f"{len(workers_in_group)} worker NCNs")
    print("PASSED")
    return 0


if __name__ == '__main__':
    sys.exit(main())
