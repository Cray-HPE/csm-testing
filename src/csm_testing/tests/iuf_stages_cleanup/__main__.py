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
import base64
import os
import subprocess
from requests import Session
import requests
from requests.auth import HTTPBasicAuth
from kubernetes import client, config
import sys

IMAGE = "registry.local/artifactory.algol60.net/csm-docker/stable/product-deletion-utility:1.0.1"
NAMESPACE = "services"
CONFIGMAP_NAME = "cray-product-catalog"
PRODUCT_NAME = "dummy"
PRODUCT_VERSION = "1.0.0"
DELETION_FILE_PATH="/etc/cray/upgrade/csm/iuf/deletion"
NEXUS_URL = "https://packages.local"
REPO_URL = f"{NEXUS_URL}/service/rest/v1/repositories/yum/hosted"

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command {command} failed with error: {e.stderr.decode()}")
        sys.exit(1)

def get_nexus_credentials(namespace="nexus", secret_name="nexus-admin-credential"):
    """Retrieve Nexus credentials from a Kubernetes secret."""
    # Check if the secret exists
    run_command(f"kubectl get secret -n {namespace} {secret_name}")

    # Retrieve and decode credentials
    username_base64 = run_command(f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.username}}}}")
    password_base64 = run_command(f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.password}}}}")

    if username_base64 and password_base64:
        username = base64.b64decode(username_base64).decode()
        password = base64.b64decode(password_base64).decode()
        return username, password
    else:
        sys.exit("ERROR: Failed to retrieve credentials")

# function to get certificates for making api calls
def get_ca_certificates(namespace, cert_configmap_name):
    """ Retrieve CA certificates from the specified ConfigMap """
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config() 

    v1 = client.CoreV1Api()
    configmap = v1.read_namespaced_config_map(cert_configmap_name, namespace)

    # Save the CA certificate to a file
    ca_cert_path = '/tmp/ca.crt'
    with open(ca_cert_path, 'w') as f:
        f.write(configmap.data['certificate_authority.crt'])

    return ca_cert_path

def cleanup_deliver_product():
    repo_name = "dummy-repo"
    username,password = get_nexus_credentials()
    """Delete repository from Nexus."""
    print(f"INFO: Deleting repository '{repo_name}' in Nexus...")
    delete_url = f"{NEXUS_URL}/service/rest/v1/repositories/{repo_name}"

    response = requests.delete(delete_url, auth=(username, password))

    if response.status_code == 204:
        print("INFO: Repository deleted successfully.")
    else:
        print(f"ERROR: Failed to delete repository: {response.status_code} - {response.text}")
        sys.exit(1)

    if not os.path.exists(DELETION_FILE_PATH):
        with open(DELETION_FILE_PATH,"w"):
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

    remove_dummy_entry = "kubectl patch configmap cray-product-catalog -n services --type merge -p '{\"data\":{\"dummy\":null}}'"
    print("INFO: Removing dummy entry from cray-product-catalog ConfigMap...")
    run_command(remove_dummy_entry)

    # Delete the cray-product-catalog-dummy ConfigMap
    delete_dummy_cm = "kubectl delete configmap cray-product-catalog-dummy -n services"
    print("INFO: Deleting cray-product-catalog-dummy ConfigMap in services namespace...")
    run_command(delete_dummy_cm)

    if os.path.exists(DELETION_FILE_PATH):
        print(f"INFO: Removing deletion file: {DELETION_FILE_PATH}")
        os.remove(DELETION_FILE_PATH)
    else:
        print(f"INFO: Deletion file {DELETION_FILE_PATH} not found, skipping deletion.")

    print("INFO: Cleanup complete for DELIVER-PRODUCT stage!")

def cleanup_vcs_branch():
    # getting vcs creds
    vcs_user = run_command("kubectl get secret -n services vcs-user-credentials --template={{.data.vcs_username}} | base64 --decode")
    vcs_password = run_command("kubectl get secret -n services vcs-user-credentials --template={{.data.vcs_password}} | base64 --decode")

    configmap_name = 'cray-configmap-ca-public-key'
    gitea_base_url="https://api-gw-service-nmn.local/vcs"
    gitea_url = f'{gitea_base_url.rstrip("/")}/api/v1'
    org ="cray"
    repo_name = "dummy-config-management"

    session = Session()
    ca_cert_path = get_ca_certificates(NAMESPACE, configmap_name)
    auth = HTTPBasicAuth(vcs_user, vcs_password)
    dummy_repo_url = '{}/repos/{}/{}'.format(gitea_url, org, repo_name)

    print(f"INFO: Attempting to delete Gitea repository: {dummy_repo_url}")
    resp = session.delete(dummy_repo_url,verify=ca_cert_path, auth=auth)
    
    if resp.status_code == 204:
        print(f"INFO: Repository '{repo_name}' deleted successfully.")
    elif resp.status_code == 404:
        print(f"WARNING: Repository '{repo_name}' not found.")
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
    cfs_delete_command = "cray cfs configurations delete config-minimal-management-dummy-1.0.0"
    cfs_delete_output = run_command(cfs_delete_command)
    print("INFO: Cleanup complete for UPDATE-CFS-CONFIG stage!")

def cleanup_prepared_images():
    print("INFO: The ims images and s3 artifacts already deleted by product-deletion-utility")
    print("INFO: Cleanup complete for PREPARE-IMAGES stage!")

def main():
    print("---------------STARTING CLEANUP FOR STAGE OPERATIONS--------------")
    cleanup_deliver_product()
    cleanup_vcs_branch()
    cleanup_cfs_configurations()
    cleanup_prepared_images()
    print("--------------- CLEANUP FOR STAGE OPERATIONS COMPLETED --------------")

if __name__ == "__main__":
    main()