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
This script executes iuf apis testing.
"""

import time
import sys
import urllib3
from csm_testing.lib.iuf_constants import MEDIA_DIR
from csm_testing.lib.iuf_common import media_dir_setup

from csm_testing.lib.iuf_classes import ApiInterface
from csm_testing.tests.iuf_apis.apis_list_functions import (
    no_auth_list_stages,
    list_activities,
    list_stages,
)
from csm_testing.tests.iuf_apis.apis_activity_functions import (
    activity_create,
    activity_restart,
    activity_resume,
    activity_run,
    activity_abort,
)
from csm_testing.tests.iuf_apis.apis_session_function import (
    get_activity_session,
    get_history,
    get_history_time,
    get_sessions,
    get_workflows,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    """
    The main entry point of the program
    """
    tar_dir = "/opt/cray/tests/install/ncn/scripts/iuf_run_setup"
    media_dir_setup(tar_dir)
    activity = sys.argv[1]
    print(f"INFO: This is the activity: {activity}")

    count = 0
    apis = ApiInterface()
    count = no_auth_list_stages(count)
    print("*" * 50)

    count = list_stages(apis, count)
    print("*" * 50)

    count = list_activities(apis, count)
    print("*" * 50)

    count = activity_create(apis, activity, count)
    print("*" * 50)

    count = activity_run(apis, activity, MEDIA_DIR, count)
    print("*" * 50)
    time.sleep(3)

    count = activity_abort(apis, activity, count)
    print("*" * 50)
    time.sleep(3)

    count = activity_resume(apis, activity, count)
    print("*" * 50)
    time.sleep(3)

    count = activity_abort(apis, activity, count)
    print("*" * 50)
    time.sleep(3)

    count = activity_restart(apis, activity, count)
    print("*" * 50)

    count = get_sessions(apis, activity, count)
    print("*" * 50)

    count = get_workflows(apis, activity, count)
    print("*" * 50)

    count = get_history(apis, activity, count)
    print("*" * 50)

    count = get_history_time(apis, activity, count)
    print("*" * 50)

    count = get_activity_session(apis, activity, count)
    print("*" * 50)

    print("~" * 50)
    print(f"INFO: Total test cases passed: {count} test cases skipped: {15 - count}")
    print("~" * 50)


if __name__ == "__main__":
    main()
