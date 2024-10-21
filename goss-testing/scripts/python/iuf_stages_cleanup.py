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

import os
import subprocess
from requests import Session
import requests
from requests.auth import HTTPBasicAuth
from kubernetes import client, config

IMAGE = "registry.local/artifactory.algol60.net/csm-docker/stable/product-deletion-utility:1.0.0"
NAMESPACE = "services"
CONFIGMAP_NAME = "cray-product-catalog"
PRODUCT_NAME = "dummy"
PRODUCT_VERSION = "1.0.0"
DELETION_FILE_PATH="/etc/cray/upgrade/csm/iuf/deletion"

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e.stderr.decode()}")
        return None

def cleanup_deliver_product():

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
    print(f"Running podman command: {pod_command}")
    run_command(pod_command)

    remove_dummy_entry = "kubectl patch configmap cray-product-catalog -n services --type merge -p '{\"data\":{\"dummy\":null}}'"
    print("Removing dummy entry from cray-product-catalog ConfigMap...")
    run_command(remove_dummy_entry)

    # Delete the cray-product-catalog-dummy ConfigMap
    delete_dummy_cm = "kubectl delete configmap cray-product-catalog-dummy -n services"
    print("Deleting cray-product-catalog-dummy ConfigMap in services namespace...")
    run_command(delete_dummy_cm)

    if os.path.exists(DELETION_FILE_PATH):
        print(f"Removing deletion file: {DELETION_FILE_PATH}")
        os.remove(DELETION_FILE_PATH)
    else:
        print(f"Deletion file {DELETION_FILE_PATH} not found, skipping deletion.")

    print("Cleanup complete for DELIVER-PRODUCT stage!")

def cleanup_vcs_branch():
    # function to get certificates for making api calls
    def get_ca_certificates(namespace, cert_configmap_name):
        """ Retrieve CA certificates from the specified ConfigMap """
        try:
            # Attempt to load in-cluster configuration
            config.load_incluster_config()
        except Exception:
            # If in-cluster config fails, fall back to local kube config
            config.load_kube_config() 

        v1 = client.CoreV1Api()
        configmap = v1.read_namespaced_config_map(cert_configmap_name, namespace)

        # Save the CA certificate to a file
        ca_cert_path = '/tmp/ca.crt'
        with open(ca_cert_path, 'w') as f:
            f.write(configmap.data['certificate_authority.crt'])
    
        return ca_cert_path
    
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

    org_repos_url= '{}/orgs/{}/repos'.format(gitea_url, org)
    print(f"Attempting to fetch list of all gitea repositories: {org_repos_url}")
    try:
        resp = session.get(org_repos_url, verify=ca_cert_path,auth=auth)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            print('error: %s' % err)
            exit(1)
    repo_data = resp.json()
    
    # Print the names of the repositories
    for repo_info in repo_data:
        print(f"Repository name: {repo_info.get('name')}") 

    dummy_repo_url = '{}/repos/{}/{}'.format(gitea_url, org, repo_name)

    print(f"Attempting to fetch gitea repository:{dummy_repo_url}")
    resp = session.get(dummy_repo_url, verify=ca_cert_path,auth=auth)
    
    if resp.status_code == 200:
        print(f"Repository '{repo_name}' exists.")
    elif resp.status_code == 404:
        print(f"Repository '{repo_name}' not found.")
        return
    else:
        print(f"Failed to fetch repository: {resp.status_code}, {resp.text}")
        return
    
    repo_info=resp.json()
    if repo_info:
        # Print a few details about the repository
        print(f"Repository Name: {repo_info['name']}")
        print(f"Repository Full Name: {repo_info['full_name']}")
        print(f"Private: {repo_info['private']}")
        print(f"Default Branch: {repo_info['default_branch']}")

    print(f"Attempting to delete Gitea repository: {dummy_repo_url}")
    resp = session.delete(dummy_repo_url,verify=ca_cert_path, auth=auth)
    
    if resp.status_code == 204:
        print(f"Repository '{repo_name}' deleted successfully.")
    elif resp.status_code == 404:
        print(f"Repository '{repo_name}' not found.")
    else:
        print(f"Failed to delete repository: {resp.status_code}, {resp.text}")
    
    if os.path.exists(ca_cert_path):
        print(f"Removing certificate file: {ca_cert_path}")
        os.remove(ca_cert_path)
    else:
        print(f"Certificate file {ca_cert_path} not found, skipping deletion.")
    print("Cleanup complete for UPDATE-VCS-CONFIG stage!")

def cleanup_cfs_configurations():
    cfs_delete_command = "cray cfs configurations delete config-minimal-management-dummy-1.0.0"
    cfs_delete_output = run_command(cfs_delete_command)
    print("Cleanup complete for UPDATE-CFS-CONFIG stage!")

def cleanup_prepared_images():
    print("The ims images and s3 artifacts already deleted by product-deletion-utility")
    print("Cleanup complete for PREPARE-IMAGES stage!")

if __name__ == "__main__":
    print("---------------STARTING CLEANUP FOR STAGE OPERATIONS--------------")
    cleanup_deliver_product()
    cleanup_vcs_branch()
    cleanup_cfs_configurations()
    cleanup_prepared_images()
    print("--------------- CLEANUP FOR STAGE OPERATIONS COMPLETED --------------")
    