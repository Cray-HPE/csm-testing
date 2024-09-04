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
This script validates run some pre checks for IUF.
"""

import subprocess
import sys
import requests
import shutil
from packaging import version

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return result.stdout.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stderr.strip(), e.returncode

def compare_versions(version1, version2):
    
    v1 = version.parse(version1)
    v2 = version.parse(version2)
    
    if v1 == v2:
        print(f"INFO: Version {version1} is equal to required version {version2}")
    elif v1 < v2:
        print(f"ERROR: Version {version1} is less than required version {version2}")
        sys.exit(1)
    else:
        print(f"INFO: Version {version1} is greater than required version {version2}")

def check_k8s_version(minimum_version):
    k8s_version, returncode = run_command("kubectl version --short | grep -i 'server version' | awk '{print $3}'")
    if returncode != 0:
        print(f"Error: Failed to get Kubernetes version. Return code: {returncode}")
        sys.exit(1)

    print(f"INFO: Kubernetes version: {k8s_version}")
    compare_versions(k8s_version, minimum_version)

def check_iuf_cli_version(minimum_version):
    iuf_cli_version, returncode = run_command("rpm -qa | grep iuf-cli | awk -F- '{print $3}'")
    if returncode != 0:
        print("Error: Failed to get iuf-cli version. Return code: {returncode}")
        sys.exit(1)

    if not iuf_cli_version:
        print("Error: iuf-cli rpm is not installed")
        sys.exit(1)
    else:
        print(f"INFO: iuf-cli rpm is installed: {iuf_cli_version}")

    compare_versions(iuf_cli_version, minimum_version)

def check_pod_status():
    nls_pods, returncode = run_command("kubectl get po -n argo | grep -i '^cray-' | grep -v 'Running'")
    if returncode == 1:
        print("INFO: All cray-* pods are running")
    elif returncode == 0 and nls_pods:
        print("Error: Some pods are not running")
        print(nls_pods)
        sys.exit(1)
    else:
        print(f"Unexpected error: Return code {returncode}")
        print(nls_pods)
        sys.exit(1)


def check_available_space():
    total, used, free = shutil.disk_usage("/etc/cray/upgrade/csm/")
    free_gb = free // (2**30)
    if free_gb < 5:
        print("Error: Insufficient space in /etc/cray/upgrade/csm/.")
        sys.exit(1)
    else:
        print(f"INFO: Available space: {free_gb}G")

def check_url_status(cluster_name):
    urls = [
        f"https://argo.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/",
        f"https://vcs.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/",
        f"https://nexus.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/"
    ]
    
    for url in urls:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code not in [200, 302]:
                print(f"Error: {url} Unreachable. Received status code {response.status_code}")
                sys.exit(1)
            else:
                print(f"INFO: {url} is reachable.")
        except requests.RequestException as e:
            print(f"Error: {url} Unreachable. Exception: {e}")
            sys.exit(1)

def main():
    if len(sys.argv) != 4:
        print("Usage: script.py <K8S_MINIMUM_VERSION> <IUF_CLI_MINIMUM_VERSION> <CLUSTER_NAME>")
        sys.exit(1)
    
    k8s_minimum_version = sys.argv[1]
    iuf_cli_minimum_version = sys.argv[2]
    cluster_name = sys.argv[3]
    
    check_k8s_version(k8s_minimum_version)
    check_iuf_cli_version(iuf_cli_minimum_version)
    check_pod_status()
    check_available_space()
    check_url_status(cluster_name)

if __name__ == "__main__":
    main()
