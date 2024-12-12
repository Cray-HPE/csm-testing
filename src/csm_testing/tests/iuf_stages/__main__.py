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
This script runs IUF from process-media to prepare-images.
"""

import subprocess
import os
import sys
import yaml
import requests
from cray_product_catalog.query import ProductCatalog
from csm_testing.lib.iuf_common import (
    run_command,
    vcs_auth,
)
from csm_testing.lib.iuf_constants import (
    MEDIA_DIR,
    CONFIGMAP_NAME,
    NAMESPACE,
    PRODUCT_NAME,
    PRODUCT_VERSION,
    NEXUS_URL,
)
from csm_testing.tests.iuf_stages.helper import (
    nexus_repo_setup,
    check_product_data,
    run_iuf_script,
    validate_images,
)

REPO_URL = f"{NEXUS_URL}/service/rest/v1/repositories/yum/hosted"


def process_media(*args):
    """Runs process-media for a dummy-product"""
    tar_dir = args[0]
    activity_name = args[1]
    test_cases = args[2]

    if run_iuf_script(tar_dir, activity_name):
        folder_to_check = "/etc/cray/upgrade/csm/automation-tests/dummy-1.0.0"
        file_to_check = "/etc/cray/upgrade/csm/automation-tests/session_vars.yaml"

        if os.path.isdir(folder_to_check):
            print(f"TEST CASE: Folder exists: {folder_to_check}")
            test_cases += 1
        else:
            print(f"ERROR: Folder does not exist: {folder_to_check}")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)

        if os.path.isfile(file_to_check):
            print(f"TEST CASE: File exists: {file_to_check}")
            test_cases += 1
        else:
            print(f"ERROR: File does not exist: {file_to_check}")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)

        check_configmap_command = f"kubectl get configmap {activity_name} -n argo"
        configmap_output, _ = run_command(check_configmap_command)

        if configmap_output:
            print("TEST CASE: ConfigMap found.")
            test_cases += 1
            return test_cases
        print("ERROR: ConfigMap not found.")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)
    else:
        print("ERROR: Unable to run process-media.")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def pre_install_check(activity_name: str, test_cases: int):
    """Runs pre-install-check for a dummy-product

    Args:
        activity_name (str): name of the activity
        test_cases (int): number of test cases

    Returns:
        int: number of executed test cases
    """
    command = (
        f"iuf -a {activity_name} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml "
        f"-r pre-install-check"
    )
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        print("Command output:", result.stdout)
        print(
            "TEST CASES: pre-hook, post-hook and on-exit scripts executed successfully"
        )
        test_cases += 3
        return test_cases
    except subprocess.CalledProcessError as err:
        print(f"ERROR: {err}")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def deliver_product(activity_name: str, test_cases: int):
    """Runs deliver-product for a dummy-product

    Args:
        activity_name (str): name of the activity
        test_cases (int): number of test cases

    Returns:
        int: number of executed test cases
    """
    nexus_repo_setup()
    command = (
        f"iuf -a {activity_name} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml "
        f"-r deliver-product"
    )
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        print("Command output:", result.stdout)
        cray_product_catalog = ProductCatalog(name=CONFIGMAP_NAME, namespace=NAMESPACE)
        dummy_product = cray_product_catalog.get_product(PRODUCT_NAME, PRODUCT_VERSION)

        if not check_product_data(dummy_product):
            print("ERROR: Exiting due to missing product data.")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        test_cases += 5
        print("INFO: Checking cm...")
        check_configmap_command = (
            f"kubectl get configmap {CONFIGMAP_NAME} -n {NAMESPACE} -o json"
        )
        configmap_output, _ = run_command(check_configmap_command)
        if configmap_output:
            print(
                "INFO: ConfigMap found. Checking for entry 'dummy' in the product name..."
            )

            # Parse the YAML output to look for the product name "dummy"
            configmap_data = yaml.safe_load(configmap_output)
            product_data = configmap_data.get("data", {})

            # Check if "dummy" is in the product data keys
            if "dummy" in product_data:
                print("TEST CASE: Entry 'dummy' found in the ConfigMap.")
                test_cases += 1
                return test_cases
            print("ERROR: Entry 'dummy' not found in the ConfigMap.")
            print(
                f"INFO: Total test cases executed for stage operations: {test_cases}"
            )
            sys.exit(1)
        else:
            print(f"ERROR: ConfigMap {CONFIGMAP_NAME} not found.")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
    except subprocess.CalledProcessError as err:
        print(f"Error: {err}")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def update_vcs_config(activity_name: str, test_cases: int):
    """Runs update-vcs-config for a dummy-product

    Args:
        activity_name (str): name of the activity
        test_cases (int): number of test cases

    Returns:
        int: number of executed test cases
    """
    try:
        cray_product_catalog = ProductCatalog(name=CONFIGMAP_NAME, namespace=NAMESPACE)
        dummy_product = cray_product_catalog.get_product("dummy", "1.0.0")
        if not dummy_product.configuration:
            print("Error: No configurations present!")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        else:
            test_cases += 1
            print("TEST CASE: configurations present. Passed!")

        command = (
            f"iuf -a {activity_name} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml "
            f"-bm {MEDIA_DIR}/management-bootprep.yaml -r update-vcs-config"
        )
        run_command(command)

        dummy_repo_url, auth, ca_cert_path = vcs_auth()

        session = requests.Session()

        print(f"INFO: Attempting to fetch gitea repository:{dummy_repo_url}")
        resp = session.get(dummy_repo_url, verify=ca_cert_path, auth=auth)

        if resp.status_code == 200:
            print(f"TEST CASE: Repository '{dummy_repo_url}' exists.")
            test_cases += 1
            return test_cases
        if resp.status_code == 404:
            print(f"ERROR: Repository '{dummy_repo_url}' not found.")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        else:
            print(f"ERROR: Failed to fetch repository: {resp.status_code}, {resp.text}")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)

        repo_info = resp.json()
        if repo_info:
            print(f"INFO: Repository Name: {repo_info['name']}")
            print(f"INFO: Default Branch: {repo_info['default_branch']}")
    except subprocess.CalledProcessError as err:
        print(f"Error: {err}")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def update_cfs_config(activity_name: str, test_cases: int):
    """Runs update-cfs-config for a dummy-product

    Args:
        activity_name (str): name of the activity
        test_cases (int): number of test cases

    Returns:
        int: number of executed test cases
    """
    try:
        command = (
            f"iuf -a {activity_name} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml "
            f"-bm {MEDIA_DIR}/management-bootprep.yaml -r update-cfs-config"
        )
        run_command(command)

        kubectl_command = (
            f"kubectl get configmaps -n argo {activity_name} -o jsonpath="
            "'{.data.iuf_activity}' | jq '.operation_outputs.stage_params"
            '["update-cfs-config"]["update-management-cfs-config"]'
            '["sat-bootprep-run"].script_stdout' + "' | xargs -0 echo -e"
        )

        kubectl_output, _ = run_command(kubectl_command)

        if not kubectl_output:
            print(
                f"ERROR: The output for cfs configurations is null or empty in the "
                f"{activity_name} configmap."
            )
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        else:
            print("TEST CASE: Configmap updated with cfs configurations data")
            test_cases += 1

        cfs_command = "cray cfs configurations list | grep 'config-minimal-management-dummy-1.0.0'"
        cfs_output, _ = run_command(cfs_command)
        if not cfs_output:
            print("ERROR: No configuration found in cfs")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        print(f"TEST CASE: CFS configuration found {cfs_output}")
        test_cases += 1
        return test_cases
    except subprocess.CalledProcessError as err:
        print(f"Error: {err}")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def prepare_images(activity_name: str, test_cases: int):
    """Runs prepare-images for a dummy-product

    Args:
        activity_name (str): name of the activity
        test_cases (int): number of test cases

    Returns:
        int: number of executed test cases
    """
    try:
        command = (
            f"iuf -a {activity_name} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml "
            f"-bm {MEDIA_DIR}/management-bootprep.yaml -r prepare-images"
        )
        run_command(command)

        kubectl_command = (
            f"kubectl get configmaps -n argo {activity_name} -o jsonpath="
            "'{.data.iuf_activity}' | jq '.operation_outputs.stage_params"
            '["prepare-images"]["prepare-management-images"]'
            '["sat-bootprep-run"].script_stdout' + "' | xargs -0 echo -e"
        )
        kubectl_output, _ = run_command(kubectl_command)

        if not kubectl_output:
            print("Error: The output for configmap entry of images is null or empty.")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)
        else:
            print("INFO: Found the cm entry...")
            print(kubectl_output)
            test_cases += 1

        images_info_cmd = f"""
        kubectl get configmaps -n argo {activity_name} -o jsonpath='{{.data.iuf_activity}}' \
        | jq -r '.operation_outputs.stage_params["prepare-images"]["prepare-management-images"]["sat-bootprep-run"].script_stdout | fromjson | .images[] | "\(.name):\(.final_image_id)"'
        """

        images_name_and_ids, _ = run_command(images_info_cmd)

        if not images_name_and_ids:
            print("ERROR: No images names and id found")
            print(f"INFO: Total test cases executed for stage operations: {test_cases}")
            sys.exit(1)

        test_cases = validate_images(images_name_and_ids, test_cases)
        return test_cases
    except subprocess.CalledProcessError as err:
        print(f"Error: {err}")
        print(f"INFO: Total test cases executed for stage operations: {test_cases}")
        sys.exit(1)


def main():
    """Calls every stage functions to execute the stage and test-cases"""
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: script.py <tar_dir> <activity_name>")
        sys.exit(1)
    else:
        test_cases = 0
        tar_dir = sys.argv[1]
        activity_name = sys.argv[2]
        print("TEST CASE: process-media stage")
        test_cases = process_media(tar_dir, activity_name, test_cases)
        print(
            "----------------------- PROCESS-MEDIA tests completed -----------------------"
        )

        print("TEST CASES: pre-install-check stage")
        test_cases = pre_install_check(activity_name, test_cases)
        print(
            "----------------------- PRE-INSTALL-CHECK tests completed -----------------------"
        )

        print("TEST CASES: deliver-product stage")
        test_cases = deliver_product(activity_name, test_cases)
        print(
            "----------------------- DELIVER-PRODUCT tests completed -----------------------"
        )

        print("TEST CASES: update-vcs-config stage")
        test_cases = update_vcs_config(activity_name, test_cases)
        print(
            "----------------------- UPDATE-VCS-CONFIG tests completed -----------------------"
        )

        print("TEST CASES: update_cfs_config stage")
        test_cases = update_cfs_config(activity_name, test_cases)
        print(
            "----------------------- UPDATE-CFS-CONFIG tests completed -----------------------"
        )

        print("TEST CASES: prepare_images stage")
        test_cases = prepare_images(activity_name, test_cases)
        print(
            "----------------------- PREPARE-IMAGES tests completed -----------------------"
        )

        print(f"INFO: Total test cases executed for stage operations: {test_cases}")


if __name__ == "__main__":
    main()
