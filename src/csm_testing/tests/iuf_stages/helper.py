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
"""Helper functions for iuf_stages module"""
import subprocess
import sys
import json
import requests
from csm_testing.lib.iuf_common import (
    get_nexus_credentials,
    run_command,
)
from csm_testing.lib.iuf_constants import (
    NEXUS_URL, )

REPO_URL = f"{NEXUS_URL}/service/rest/v1/repositories/yum/hosted"


def nexus_repo_setup():
    """creates a dummy-repo in nexus to upload the data from dummy-product installation."""
    repo_name = "dummy-repo"
    username, password = get_nexus_credentials()

    repo_data = {
        "name": repo_name,
        "online": True,
        "storage": {
            "blobStoreName": "default",
            "strictContentTypeValidation": True,
            "writePolicy": "ALLOW",
        },
        "cleanup": None,
        "yum": {
            "repodataDepth": 0,
            "deployPolicy": "STRICT"
        },
        "format": "yum",
        "type": "hosted",
    }

    response = requests.post(
        REPO_URL,
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        data=json.dumps(repo_data),
        verify=False,
    )

    if response.status_code == 201:
        print("INFO: Repository created successfully.")
    elif response.status_code == 200:
        print("INFO: Repository already exists.")
    else:
        print(
            f"ERROR: Failed to create repository: {response.status_code} - {response.text}"
        )
        sys.exit(1)


def check_product_data(dummy_product: dict):
    """
    Checks if any of the essential product attributes are empty.

    Args:
        dummy_product (dict): A dictionary representing the product data to be validated.
            Expected keys:
                - docker_images (list): A list of Docker image names or URIs.
                - recipes (list): A list of recipe files or paths.
                - loftsman_manifests (list): A list of Loftsman manifest files or paths.
                - helm_charts (list): A list of Helm chart directories or paths.

    Returns:
        bool: True if all product attributes are non-empty, False otherwise.
    """
    if not dummy_product.docker_images:
        print("ERROR: Docker images are empty!")
        return False
    if not dummy_product.recipes:
        print("ERROR: Recipes are empty!")
        return False
    if not dummy_product.loftsman_manifests:
        print("ERROR: Loftsman manifests are empty!")
        return False
    if not dummy_product.helm_charts:
        print("ERROR: Helm charts are empty!")
        return False
    return True


def run_iuf_script(*args):
    """Calls run_iuf_script to setup the media-dir and run process-media for dummy-product

    Returns:
        bool: True if the media directory setup and iuf_run.py execution were successful.
              False otherwise
    """
    tar_dir = args[0]
    activity_name = args[1]
    try:
        subprocess.run(
            [
                "python3",
                "/opt/cray/tests/install/ncn/scripts/python/iuf_run",
                tar_dir,
                activity_name,
            ],
            check=True,
        )
    except subprocess.CalledProcessError as err:
        print(f"ERROR: Error running iuf_run.py: {err}")
        return False
    return True


def validate_images(images_name_and_ids: str, test_cases: int):
    """Validates images in IMS and boot-images artifacts

    Args:
        images_name_and_ids (str): Image names and IDs as a newline-separated string

    Return:
        int: number of executed test cases
    """
    try:
        image_lines = images_name_and_ids.splitlines()

        print("TEST CASE: Checking ims images...")
        for image in image_lines:
            name, final_image_id = image.split(":")
            print(
                f"INFO: Checking cray ims images for image Name: {name.strip()} "
                f"with image ID: {final_image_id.strip()}")
            check_ims_cmd = f"cray ims images describe {final_image_id.strip()}"
            ims_info, _ = run_command(check_ims_cmd)
            if not ims_info:
                print(f"ERROR: Could not find ims image for {name}")
                print(
                    f"INFO: Total test cases executed for stage operations: {test_cases}"
                )
                sys.exit(1)
            print(ims_info)

        test_cases += 1
        print("TEST CASE: Checking boot-images artifacts..")
        for image in image_lines:
            name, final_image_id = image.split(":")
            print(
                f"INFO: Checking cray artifacts boot-images for image Name: {name.strip()}"
            )
            check_boot_images_cmd = f"cray artifacts describe boot-images {final_image_id.strip()}/manifest.json"
            boot_images_info, _ = run_command(check_boot_images_cmd)
            if not boot_images_info:
                print(f"ERROR: Could not find boot-image for {name}")
                print(
                    f"INFO: Total test cases executed for stage operations: {test_cases}"
                )
                sys.exit(1)
            print(boot_images_info)

        test_cases += 1
        return test_cases
    except subprocess.CalledProcessError as err:
        print(f"Error: {err}")
        print(
            f"INFO: Total test cases executed for stage operations: {test_cases}"
        )
        sys.exit(1)
