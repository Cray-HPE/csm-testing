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

import subprocess
import os
from pathlib import Path
import sys
import yaml

MEDIA_DIR = "/etc/cray/upgrade/csm/automation-tests"
PRODUCT_CATALOG_CONFIG_MAP_NAMESPACE='services'

from cray_product_catalog.query import *

IMAGE = "registry.local/artifactory.algol60.net/csm-docker/stable/product-deletion-utility:1.0.0"
NAMESPACE = "services"
CONFIGMAP_NAME = "cray-product-catalog"
PRODUCT_NAME = "dummy"
PRODUCT_VERSION = "1.0.0"
DIRECTORY_PATH="/etc/cray/upgrade/csm/iuf/deletion"

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e.stderr.decode()}")
        return None

def check_product_data(dummy_product):
    """Check if any of the product attributes are empty and return a status."""
    if not dummy_product.docker_images:
        print("Error: Docker images are empty!")
        return False
    if not dummy_product.recipes:
        print("Error: Recipes are empty!")
        return False
    if not dummy_product.manifests:
        print("Error: Loftsman manifests are empty!")
        return False
    if not dummy_product.helm_charts:
        print("Error: Helm charts are empty!")
        return False
    if not dummy_product.images:
        print("Error: Images are empty!")
        return False
    if not dummy_product.repositories:
        print("Error: No repositories present!")
        return False
    return True

# Run iuf_run.py script
def run_iuf_script(*args):
    try:
        subprocess.run(['python3', '/opt/cray/tests/install/ncn/scripts/python/iuf_run.py', tar_dir,ACTIVITY_NAME], check=True)
        print("iuf_run.py executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error running iuf_run.py: {e}")
        return False
    return True

def process_media(*args):
    # Run iuf_run.py
    if run_iuf_script(tar_dir,ACTIVITY_NAME):
        folder_to_check = "/etc/cray/upgrade/csm/automation-tests/dummy-1.0.0"
        file_to_check = "/etc/cray/upgrade/csm/automation-tests/session_vars.yaml"

        # Check if folder exists
        if os.path.isdir(folder_to_check):
            print(f"Folder exists: {folder_to_check}")
        else:
            print(f"Folder does not exist: {folder_to_check}")
            sys.exit(1)

        # Check if file exists
        if os.path.isfile(file_to_check):
            print(f"File exists: {file_to_check}")
        else:
            print(f"File does not exist: {file_to_check}")
            sys.exit(1)
        
        check_configmap_command = f"kubectl get configmap {ACTIVITY_NAME} -n argo"
        configmap_output = run_command(check_configmap_command)

        if configmap_output:
            print(f"ConfigMap found.")
        else:
            print("ConfigMap not found.")
            sys.exit(1)

def pre_install_check(ACTIVITY_NAME):
    print("Running test cases for pre-install-check stage")
    command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -r pre-install-check"
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)
        print("------------------------ PRE_INSTALL_CHECKS COMPLETED ------------------------")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    return 0

def deliver_product(ACTIVITY_NAME):
    print("Running test cases for deliver-product stage")
    command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -r deliver-product"
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print("Command output:", result.stdout)
        cray_product_catalog= ProductCatalog(name='cray-product-catalog', namespace='services')
        dummy_product=cray_product_catalog.get_product('dummy','1.0.0')

        if not check_product_data(dummy_product):
            print("Exiting due to missing product data.")
            exit(1)

        if not os.path.exists(DIRECTORY_PATH):
            print(f"Creating directory {DIRECTORY_PATH}...")
            os.makedirs(DIRECTORY_PATH)
        else:
            print(f"Directory {DIRECTORY_PATH} already exists.")
        pod_command = f"""
        podman run --rm \
        --mount type=bind,src=/etc/kubernetes/admin.conf,target=/root/.kube/config,ro=true \
        --mount type=bind,src=/var/lib/ca-certificates,target=/var/lib/ca-certificates,ro=true \
        --mount type=bind,src=/etc/cray/upgrade/csm/iuf/deletion,target=/etc/cray/upgrade/csm/iuf/deletion,ro=false \
        {IMAGE} delete {PRODUCT_NAME} {PRODUCT_VERSION} \
        """
        print(f"Running podman command: {pod_command}")
        run_command(pod_command)

        

        remove_dummy_entry = "kubectl patch configmap cray-product-catalog -n services --type merge -p '{\"data\":{\"dummy\":null}}'"
        print("Removing dummy entry from cray-product-catalog ConfigMap...")
        run_command(remove_dummy_entry)

        # Delete the cray-product-catalog-dummy ConfigMap
        delete_dummy_cm = "kubectl delete configmap cray-product-catalog-dummy -n services"
        print("Deleting cray-product-catalog-dummy ConfigMap...")
        run_command(delete_dummy_cm)

        print("Cleanup complete!")
        
        print("Checking cm...")
        # Check if the configmap exists after the pod runs
        check_configmap_command = f"kubectl get configmap {CONFIGMAP_NAME} -n {NAMESPACE} -o json"
        configmap_output = run_command(check_configmap_command)
        if configmap_output:
            print(f"ConfigMap found. Checking for entry 'dummy' in the product name...")

            # Parse the YAML output to look for the product name "dummy"
            configmap_data = yaml.safe_load(configmap_output)
            product_data = configmap_data.get("data", {})

            # Check if "dummy" is in the product data keys
            if "dummy" in product_data:
                print(f"Entry 'dummy' found in the ConfigMap.")
            else:
                print(f"Entry 'dummy' not found in the ConfigMap.")
        else:
            print("ConfigMap not found.")
        print("------------------------ DELIVER-PRODUCT TESTS COMPLETED ------------------------")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    return 0

def update_vcs_config(ACTIVITY_NAME):
    try:
        cray_product_catalog= ProductCatalog(name='cray-product-catalog', namespace='services')
        dummy_product=cray_product_catalog.get_product('dummy','1.0.0')
        if not dummy_product.configurations:
            print("Error: No configurations present!")
            exit(1)

        command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -bm {MEDIA_DIR}/management-bootprep.yaml -r update-vcs-config"
        run_command(command)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    return 0

def update_cfs_config(ACTIVITY_NAME):
    try:
        command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -bm {MEDIA_DIR}/management-bootprep.yaml -r update-cfs-config"
        run_command(command)

        # Check output of kubectl command
        kubectl_command = (
            f"kubectl get configmaps -n argo {ACTIVITY_NAME} -o jsonpath="
            "'{.data.iuf_activity}' | jq '.operation_outputs.stage_params"
            '["update-cfs-config"]["update-management-cfs-config"]'
            '["sat-bootprep-run"].script_stdout' + "' | xargs -0 echo -e"
        )
        
        kubectl_output = run_command(kubectl_command)

        # Exit with error if the output is null/empty
        if not kubectl_output:
            print("Error: The output is null or empty.")
            exit(1)        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    return 0

def prepare_images(ACTIVITY_NAME):
    try:
        command = f"iuf -a {ACTIVITY_NAME} -m {MEDIA_DIR} run -rv {MEDIA_DIR}/product_vars.yaml -bm {MEDIA_DIR}/management-bootprep.yaml -r prepare_images"
        run_command(command)

        # Check output of kubectl command
        kubectl_command = (
            f"kubectl get configmaps -n argo {ACTIVITY_NAME} -o jsonpath="
            "'{.data.iuf_activity}' | jq '.operation_outputs.stage_params"
            '["prepare-images"]["prepare-management-images"]'
            '["sat-bootprep-run"].script_stdout' + "' | xargs -0 echo -e"
        )
        
        kubectl_output = run_command(kubectl_command)

        # Exit with error if the output is null/empty
        if not kubectl_output:
            print("Error: The output is null or empty.")
            exit(1)        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return e.returncode
    return 0

# Main function
def main(*args):
    process_media(tar_dir,ACTIVITY_NAME)
    pre_install_check(ACTIVITY_NAME)
    deliver_product(ACTIVITY_NAME)
    update_vcs_config(ACTIVITY_NAME)
    update_cfs_config(ACTIVITY_NAME)

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: script.py <tar_dir> <ACTIVITY_NAME>")
        sys.exit(1)
    else:
        tar_dir = sys.argv[1]
        ACTIVITY_NAME = sys.argv[2]
        main(tar_dir,ACTIVITY_NAME)

