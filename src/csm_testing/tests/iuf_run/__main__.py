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
This script sets up the media directory and executes process-media stage in IUF
for creating an activity.
"""

import subprocess
import sys
from csm_testing.lib.iuf_constants import MEDIA_DIR
from csm_testing.lib.iuf_common import media_dir_setup


def run(*args):
    """Runs process media using dummy product

    Args: tar_dir is from where media_dir content will be copied,
          activity_name for the IUF run
    """
    tar_dir = args[0]
    activity_name = args[1]
    if len(args) == 3:
        log_dir = args[2]
        command = (
            f"iuf -a {activity_name} -m {MEDIA_DIR} --log-dir {log_dir} run "
            f"-rv {MEDIA_DIR}/product_vars.yaml -r process-media"
        )
    else:
        command = (
            f"iuf -a {activity_name} -m {MEDIA_DIR} run "
            f"-rv {MEDIA_DIR}/product_vars.yaml -r process-media"
        )
    media_dir_setup(tar_dir)
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        print("INFO: Command output:", result.stdout)
        print("INFO: IUF run completed")
    except subprocess.CalledProcessError as err:
        print(f"ERROR: {err}")
        sys.exit(1)


def main():
    """entry point"""
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: script.py <tar_dir> <activity_name>")
        sys.exit(1)
    else:
        tar_dir = sys.argv[1]
        activity_name = sys.argv[2]
        if len(sys.argv) == 3:
            run(tar_dir, activity_name)
        else:
            log_dir = sys.argv[3]
            run(tar_dir, activity_name, log_dir)


if __name__ == "__main__":
    main()
