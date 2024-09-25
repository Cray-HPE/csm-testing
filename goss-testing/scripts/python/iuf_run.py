#!/usr/bin/env python3
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
This script executes iuf run command for creating an activity.
"""

import shutil
import subprocess
import sys
import os

# ACTIVITY_NAME = "test-activity"
FOLDER_NAME = "dummy-1.0.0" 
MEDIA_DIR = "/etc/cray/upgrade/csm/automation-tests"

def create_tar(tar_dir):
    os.chdir(tar_dir)
    
    tar_command = f"tar -cvf {FOLDER_NAME}.tar {FOLDER_NAME}/"
    try:
        subprocess.run(tar_command, shell=True, check=True)
        print(f"Successfully created {FOLDER_NAME}.tar")
    except subprocess.CalledProcessError as e:
        print(f"Error creating tar file: {e}")
        sys.exit(1)

def compress_tar():
    pigz_command = f"pigz -9 -c {FOLDER_NAME}.tar > {FOLDER_NAME}.tar.gz"
    try:
        subprocess.run(pigz_command, shell=True, check=True)
        print(f"Successfully compressed {FOLDER_NAME}.tar to {FOLDER_NAME}.tar.gz")
    except subprocess.CalledProcessError as e:
        print(f"Error compressing tar file: {e}")
        sys.exit(1)

def main(*args):
    ACTIVITY_NAME=args[0]
    if len(args)== 2:
        LOG_DIR=args[1]
        command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} --log-dir {LOG_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -r process-media"
    else:
        command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -r process-media"
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        print(f"Directory {MEDIA_DIR} created successfully.")
    except OSError as e:
        print(f"Error creating directory {MEDIA_DIR}: {e}")
        sys.exit(1)
    
    try:
        shutil.copy(f"{tar_dir}/{FOLDER_NAME}.tar.gz", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/product_vars.yaml", MEDIA_DIR)
        print(f"Files copied successfully to {MEDIA_DIR}.")
    except IOError as e:
        print(f"Error copying files: {e}")
        sys.exit(1)

    
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)
        print("------------------------ IUF RUN COMPLETED ------------------------")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: script.py <tar_dir> <ACTIVITY_NAME>")
        sys.exit(1)
    else:
        tar_dir = sys.argv[1]
        ACTIVITY_NAME = sys.argv[2]
        create_tar(tar_dir)
        compress_tar()
        if len(sys.argv) ==3:
            exit_code = main(ACTIVITY_NAME)
        else:
            LOG_DIR = sys.argv[3]
            exit_code = main(ACTIVITY_NAME,LOG_DIR)
        sys.exit(exit_code)
