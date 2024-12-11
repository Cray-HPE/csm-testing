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
This script will cleanup the all the data uploaded by IUF run of dummy-product.
"""

import os
import sys
from requests import Session
import requests
from csm_testing.lib.iuf_constants import (
    PRODUCT_NAME,
    PRODUCT_VERSION,
    NEXUS_URL,
)
from csm_testing.lib.iuf_common import (
    get_nexus_credentials,
    vcs_auth,
    run_command,
)

DELETION_FILE_PATH = "/etc/cray/upgrade/csm/iuf/deletion"
IMAGE = "registry.local/artifactory.algol60.net/csm-docker/stable/product-deletion-utility:1.0.1"


def cleanup_deliver_product():
    """Cleans up the data uploaded, repository created while running deliver-product stage
    using dummy-product"""

    repo_name = "dummy-repo"
    username, password = get_nexus_credentials()

    print(f"INFO: Deleting repository '{repo_name}' in Nexus...")
    delete_url = f"{NEXUS_URL}/service/rest/v1/repositories/{repo_name}"

    response = requests.delete(delete_url, auth=(username, password))
    if response.status_code == 204:
        print("INFO: Repository deleted successfully.")
    else:
        print(
            f"ERROR: Failed to delete repository: {response.status_code} - {response.text}"
        )
        sys.exit(1)

    if not os.path.exists(DELETION_FILE_PATH):
        with open(DELETION_FILE_PATH, "w", encoding="utf-8"):
            pass
    else:
        pass

    pod_command = f"""
        podman run --rm \
        --mount type=bind,src=/etc/kubernetes/admin.conf,target=/root/.kube/config,ro=true \
        --mount type=bind,src=/var/lib/ca-certificates,target=/var/lib/ca-certificates,ro=true \
        --mount type=bind,src=/etc/cray/upgrade/csm/iuf/deletion,target=/etc/cray/upgrade/csm/iuf/deletion,ro=false \
        {IMAGE} delete {PRODUCT_NAME} {PRODUCT_VERSION} \
        """
    print(f"INFO: Running podman command: {pod_command}")
    run_command(pod_command)

    remove_dummy_entry = (
        "kubectl patch configmap cray-product-catalog -n services --type merge -p "
        '\'{"data":{"dummy":null}}\''
    )

    print("INFO: Removing dummy entry from cray-product-catalog ConfigMap...")
    run_command(remove_dummy_entry)

    # Delete the cray-product-catalog-dummy ConfigMap
    delete_dummy_cm = "kubectl delete configmap cray-product-catalog-dummy -n services"
    print(
        "INFO: Deleting cray-product-catalog-dummy ConfigMap in services namespace..."
    )
    run_command(delete_dummy_cm)

    if os.path.exists(DELETION_FILE_PATH):
        print(f"INFO: Removing deletion file: {DELETION_FILE_PATH}")
        os.remove(DELETION_FILE_PATH)
    else:
        print(f"INFO: Deletion file {DELETION_FILE_PATH} not found, skipping deletion.")

    print("INFO: Cleanup complete for DELIVER-PRODUCT stage!")


def cleanup_vcs_repo():
    """Deleting the branch created while running update-vcs-config for dummy-product"""

    session = Session()
    dummy_repo_url, auth, ca_cert_path = vcs_auth()

    print(f"INFO: Attempting to delete Gitea repository: {dummy_repo_url}")
    resp = session.delete(dummy_repo_url, verify=ca_cert_path, auth=auth)

    if resp.status_code == 204:
        print(f"INFO: Repository '{dummy_repo_url}' deleted successfully.")
    elif resp.status_code == 404:
        print(f"WARNING: Repository '{dummy_repo_url}' not found.")
    else:
        print(f"ERROR: Failed to delete repository: {resp.status_code}, {resp.text}")
        sys.exit(1)

    if os.path.exists(ca_cert_path):
        print(f"INFO: Removing certificate file: {ca_cert_path}")
        os.remove(ca_cert_path)
    else:
        print(f"INFO: Certificate file {ca_cert_path} not found, skipping deletion.")
    print("INFO: Cleanup complete for UPDATE-VCS-CONFIG stage!")


def cleanup_cfs_configurations():
    """Cleanup the configurations created by IUf for dummy-product"""
    cfs_delete_command = (
        "cray cfs configurations delete config-minimal-management-dummy-1.0.0"
    )
    run_command(cfs_delete_command)
    print("INFO: Cleanup complete for UPDATE-CFS-CONFIG stage!")


def cleanup_prepared_images():
    """Cleanup the images created by IUf for dummy-product"""
    print(
        "INFO: The ims images and s3 artifacts already deleted by product-deletion-utility"
    )
    print("INFO: Cleanup complete for PREPARE-IMAGES stage!")


def main():
    """Calls stage by stage cleanup functions for IUF"""
    print("---------------STARTING CLEANUP FOR STAGE OPERATIONS--------------")
    cleanup_deliver_product()
    cleanup_vcs_repo()
    cleanup_cfs_configurations()
    cleanup_prepared_images()
    print("--------------- CLEANUP FOR STAGE OPERATIONS COMPLETED --------------")


if __name__ == "__main__":
    main()
