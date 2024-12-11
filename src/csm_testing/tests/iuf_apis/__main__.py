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

from csm_testing.lib.iuf_classes import ApiInterface_no_token
from csm_testing.lib.iuf_classes import ApiInterface
from .apis_list_functions import no_auth_list_stages, list_activities, list_stages
from .apis_activity_functions import (
    activity_create,
    activity_restart,
    activity_resume,
    activity_run,
    activity_abort,
)
from .apis_session_function import (
    get_activity_session,
    get_history,
    get_history_time,
    get_sessions,
    get_workflows,
)
from .apis_activity_functions import count, total_count

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main(): # pylint: disable=missing-function-docstring
    tar_dir = "/opt/cray/tests/install/ncn/scripts/iuf_run_setup"
    media_dir_setup(tar_dir)
    activity = sys.argv[1]
    print(f"INFO: This is the activity: {activity}")

    apis_no_token = ApiInterface_no_token()

    no_auth_list_stages(apis_no_token)
    print("*" * 50)

    apis = ApiInterface()

    list_stages(apis)
    print("*" * 50)

    list_activities(apis)
    print("*" * 50)

    activity_create(apis, activity)
    print("*" * 50)

    activity_run(apis, activity, MEDIA_DIR)
    print("*" * 50)
    time.sleep(3)

    activity_abort(apis, activity)
    print("*" * 50)
    time.sleep(3)

    activity_resume(apis, activity)
    print("*" * 50)
    time.sleep(3)

    activity_abort(apis, activity)
    print("*" * 50)
    time.sleep(3)

    activity_restart(apis, activity)
    print("*" * 50)

    get_sessions(apis, activity)
    print("*" * 50)

    get_workflows(apis, activity)
    print("*" * 50)

    get_history(apis, activity)
    print("*" * 50)

    get_history_time(apis, activity)
    print("*" * 50)

    get_activity_session(apis, activity)
    print("*" * 50)

    print("~" * 50)
    print(
        f"INFO: Total test cases passed: {count} test cases skipped: {total_count - count}"
    )
    print("~" * 50)


if __name__ == "__main__":
    main()
