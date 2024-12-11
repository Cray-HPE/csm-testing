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
This script runs pre-checks for IUF.
"""

import os
import sys
import shutil
import subprocess
import requests
from packaging import version
from csm_testing.lib.iuf_common import run_command


# compare_versions is a helper functions being used by other functions
def compare_versions(version1, version2):
    """
    Function to compare given two versions and print the result info.
    Args:
        version1(int/float), version2(int/float) : versions to compare
    Returns:
        None
    """
    ver_1 = version.parse(version1)
    ver_2 = version.parse(version2)

    if ver_1 == ver_2:
        print(f"INFO: Version {version1} is equal to required version {version2}")
    elif ver_1 < ver_2:
        print(f"ERROR: Version {version1} is less than required version {version2}")
        sys.exit(1)
    else:
        print(f"INFO: Version {version1} is greater than required version {version2}")


def check_proxy():
    """
    Function to check proxy settings in the session and print the info.
    Args:
        None
    Returns:
        None
    """

    http_proxy = os.environ.get("http_proxy")
    https_proxy = os.environ.get("https_proxy")
    no_proxy = os.environ.get("no_proxy")

    proxy_variables = {
        "http_proxy": http_proxy,
        "https_proxy": https_proxy,
        "no_proxy": no_proxy,
    }

    set_proxies = {key: value for key, value in proxy_variables.items() if value}

    if set_proxies:
        for key, value in set_proxies.items():
            print(f"{key} is set to: {value}")

        print("ERROR: Proxy variables should not be set.")
        sys.exit(1)
    else:
        print("INFO: No proxy variables are set.")


def check_k8s_version(minimum_version):
    """
    Function to check k8s version and print the info.
    Args:
        minimum_version(int/float): Kubernetes version
    Returns:
        None
    """
    k8s_version, returncode = run_command(
        "kubectl version --short | grep -i 'server version' | awk '{print $3}'"
    )
    if returncode != 0:
        print(f"ERROR: Failed to get Kubernetes version. Return code: {returncode}")
        sys.exit(1)

    print(f"INFO: Kubernetes version: {k8s_version}")
    compare_versions(k8s_version, minimum_version)


def check_iuf_cli_version(minimum_version):
    """
    Function to check iuf cli version and print the info.
    Args:
        minimum_version(int/float): IUF CLI version
    Returns:
        None
    """
    iuf_cli_version, returncode = run_command(
        "rpm -qa | grep iuf-cli | awk -F- '{print $3}'"
    )
    if returncode != 0:
        print("ERROR: Failed to get iuf-cli version. Return code: {returncode}")
        sys.exit(1)

    if not iuf_cli_version:
        print("ERROR: iuf-cli rpm is not installed")
        sys.exit(1)
    else:
        print(f"INFO: iuf-cli rpm is installed: {iuf_cli_version}")

    compare_versions(iuf_cli_version, minimum_version)


def check_nls_image(minimum_version):
    """
    Function to check cray-nls image and print the info.
    Args:
        minimum_version(int/float): NLS Image version
    Returns:
        None
    """
    cray_nls_version, returncode = run_command(
        "kubectl get deployment cray-nls -n argo \
-o=jsonpath='{.spec.template.spec.containers[*].image}'"
    )
    cray_nls_version = cray_nls_version.split(":")[1]
    if returncode != 0:
        print(f"ERROR: Failed to get cray-nls version. Return code: {returncode}")
        sys.exit(1)

    print(f"INFO: cray-nls version: {cray_nls_version}")
    compare_versions(cray_nls_version, minimum_version)


def check_nls_pod_status():
    """
    Function to check cray-nls pod status and print the info.
    Args:
        None
    Returns:
        None
    """
    nls_pods, returncode = run_command(
        "kubectl get deployment cray-nls -n argo -o=jsonpath='{.status.availableReplicas}'"
    )

    if returncode == 0 and int(nls_pods) == 3:
        print("INFO: All cray-nls pods are running")
    elif returncode == 0:
        print("ERROR: Some cray-nls pods are not running")
        print(nls_pods)
        sys.exit(1)
    else:
        print(f"Unexpected error: Return code {returncode}")
        print(nls_pods)
        sys.exit(1)


def check_nls_workflow_server():
    """
    Function to check cray-nls workflow server and print the info.
    Args:
        None
    Returns:
        None
    """
    nls_workflow_server, returncode = run_command(
        "kubectl get deployment cray-nls-argo-workflows-server \
-n argo -o=jsonpath='{.status.availableReplicas}'"
    )

    if returncode == 0 and int(nls_workflow_server) == 3:
        print("INFO: All cray-nls-argo-workflows-server pods are running")
    elif returncode == 0:
        print("ERROR: Some cray-nls-argo-workflows-server pods are not running")
        print(nls_workflow_server)
        sys.exit(1)
    else:
        print(f"Unexpected error: Return code {returncode}")
        print(nls_workflow_server)
        sys.exit(1)


def check_nls_workflow_controller():
    """
    Function to check cray-nls controller and print the info.
    Args:
        None
    Returns:
        None
    """
    nls_controller_pods, returncode = run_command(
        "kubectl get deployment cray-nls-argo-workflows-workflow-controller \
-n argo -o=jsonpath='{.status.availableReplicas}'"
    )

    if returncode == 0 and int(nls_controller_pods) == 2:
        print("INFO: All cray-nls-argo-workflows-workflow-controller pods are running")
    elif returncode == 0:
        print(
            "ERROR: Some cray-nls-argo-workflows-workflow-controller pods are not running"
        )
        print(nls_controller_pods)
        sys.exit(1)
    else:
        print(f"Unexpected error: Return code {returncode}")
        print(nls_controller_pods)
        sys.exit(1)


def check_nls_postgres():
    """
    Function to check cray-nls-postgres statefulset and print the info.
    Args:
        None
    Returns:
        None
    """
    nls_postgres, returncode = run_command(
        "kubectl get statefulset cray-nls-postgres \
-n argo -o=jsonpath='{.status.availableReplicas}'"
    )

    if returncode == 0 and int(nls_postgres) == 3:
        print("INFO: All cray-nls pods are running")
    elif returncode == 0:
        print("ERROR: Some cray-nls pods are not running")
        print(nls_postgres)
        sys.exit(1)
    else:
        print(f"Unexpected error: Return code {returncode}")
        print(nls_postgres)
        sys.exit(1)


def check_cray_iuf_chart(minimum_version):
    """
    Function to check cray-iuf helm chart and print the info.
    Args:
        minimum_version(int/float): Cray IUF Chart Version
    Returns:
        None
    """
    cray_iuf_chart_version, returncode = run_command(
        "helm get values cray-iuf -n argo  -o json | jq -r '.global.chart.version'"
    )
    if returncode != 0:
        print("ERROR: Failed to get cray iuf chart version. Return code: {returncode}")
        sys.exit(1)

    if not cray_iuf_chart_version:
        print("ERROR: cray iuf chart  is not installed")
        sys.exit(1)
    else:
        print(f"INFO: cray iuf chart is installed: {cray_iuf_chart_version}")

    compare_versions(cray_iuf_chart_version, minimum_version)


def check_cray_nls_chart(minimum_version):
    """
    Function to check cray-nls helm chart and print the info.
    Args:
        minimum_version(int/float): Cray NLS Chart Version
    Returns:
        None
    """
    cray_nls_chart_version, returncode = run_command(
        "helm get values cray-nls -n argo  -o json | jq -r '.global.chart.version'"
    )
    if returncode != 0:
        print("ERROR: Failed to get cray nls chart version. Return code: {returncode}")
        sys.exit(1)

    if not cray_nls_chart_version:
        print("ERROR: cray nls chart  is not installed")
        sys.exit(1)
    else:
        print(f"INFO: cray nls chart is installed: {cray_nls_chart_version}")

    compare_versions(cray_nls_chart_version, minimum_version)


def check_cfs():
    """
    Function to check cfs pods and print the info.
    Args:
        None
    Returns:
        None
    """
    command = "kubectl get po -n services | grep -i '^cray-cfs-api' | grep -v 'Running'"
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cfs_api_pods = result.stdout.decode().strip()
        if result.returncode == 0 and cfs_api_pods:
            print("ERROR: Some cray-cfs-api pods are not running")
            print(cfs_api_pods)
            sys.exit(1)

        else:
            print(f"Unexpected error: Return code {result.returncode}")
            print(cfs_api_pods)
            sys.exit(1)
    except subprocess.CalledProcessError:
        print("INFO: All cray-cfs-api* pods are running")
    except Exception:    # pylint: disable=W0703
        sys.exit(1)

    command = (
        "kubectl get po -n services | grep -i '^cfs-ara-postgres' | grep -v 'Running'"
    )
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        cfs_ara_pods = result.stdout.decode().strip()
        if result.returncode == 0 and cfs_ara_pods:
            print("ERROR: Some pods are not running")
            print(cfs_ara_pods)
            sys.exit(1)
        else:
            print(f"ERROR: Return code {result.returncode}")
            print(cfs_ara_pods)
            sys.exit(1)
    except subprocess.CalledProcessError:
        print("INFO: All cfs-ara-postgres* pods are running")
    except Exception:    # pylint: disable=W0703
        sys.exit(1)


def check_sat():
    """
    Function to check sat status and print the info.
    Args:
        None
    Returns:
        None
    """
    sat, returncode = run_command("sat --version")
    if returncode == 0:
        print(f"INFO: sat is installed. {sat}")
    else:
        print("ERROR: Unable to run sat.Please verify if sat is installed and working")
        sys.exit(1)


def check_docs_and_libcsm():
    """
    Function to check docs-csm and lib-csm rpms and print the info.
    Args:
        None
    Returns:
        None
    """
    docs_csm, returncode = run_command("rpm -qa | grep docs-csm")
    if returncode == 0:
        print(f"INFO: docs-csm rpm is installed. Version: {docs_csm}")
    else:
        print("ERROR: Unable to find docs. Please verify if docs is installed.")
        sys.exit(1)
    lib_csm, returncode = run_command("rpm -qa | grep docs-csm")
    if returncode == 0:
        print(f"INFO: lib-csm is installed. Version: {lib_csm}")
    else:
        print("ERROR: Unable to find libcsm. Please verify if libcsm is installed.")
        sys.exit(1)


def check_cpc():
    """
    Function to check cray-product-catalog configmap and print the info.
    Args:
        None
    Returns:
        None
    """
    _, returncode = run_command(
        "kubectl get cm -n services | grep cray-product-catalog"
    )
    if returncode == 0:
        print("INFO: Cray-Product-Catalog configmap exists in services namespace")
    else:
        print("ERROR: Unable to find Cray-Product-Catalog configmap.")
        sys.exit(1)


def check_available_space():
    """
    Function to check available disk space and print the info.
    Args:
        None
    Returns:
        None
    """
    _, _, free = shutil.disk_usage("/etc/cray/upgrade/csm/")
    free_gb = free // (2**30)
    if free_gb < 5:
        print("ERROR: Insufficient space in /etc/cray/upgrade/csm/.")
        sys.exit(1)
    else:
        print(f"INFO: Available space: {free_gb}G")


def check_url_status(cluster_name):
    """
    Function to check argo,vcs,nexus reachability and print the info.
    Args:
        cluster_name(str): Cluster name
    Returns:
        None
    """
    urls = [
        f"https://argo.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/",
        f"https://vcs.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/",
        f"https://nexus.cmn.{cluster_name}.hpc.amslabs.hpecorp.net/",
    ]

    for url in urls:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code not in [200, 302]:
                print(
                    f"Error: {url} Unreachable. Received status code {response.status_code}"
                )
                sys.exit(1)
            else:
                print(f"INFO: {url} is reachable.")
        except requests.RequestException as err:
            print(f"ERROR: {url} Unreachable. Exception: {err}")
            sys.exit(1)


# function to check ssh connectivity
def check_ssh():
    """
    Function to check ssh connectivity and print the info.
    Args:
        None
    Returns:
        None
    """
    ssh_command = "ssh -o BatchMode=yes -q ncn-m002 exit"
    ssh_output, returncode = run_command(ssh_command)

    if returncode == 0:
        print("INFO: SSH to ncn-m002 successful. Now going back to ncn-m001...")
        ssh_command_2 = "ssh -o BatchMode=yes -q ncn-m001 exit"
        ssh_output_2, r_code = run_command(ssh_command_2)
        if r_code == 0:
            print("INFO: SSH to ncn-m001 successful.")
        else:
            print("ERROR: Unable to SSH to ncn-m001. Error:", ssh_output_2)
    else:
        print("ERROR: Unable to SSH to ncn-m002. Error:", ssh_output)


def main():
    """
    The main entry point of the program
    Args:
        None
    Returns:
        None
    """
    print("INFO: Running IUF pre-checks")
    if len(sys.argv) != 7:
        print(
            "Usage: script.py \
<K8S_MINIMUM_VERSION> <IUF_CLI_MINIMUM_VERSION> <CLUSTER_NAME> \
<CRAY_NLS_IMAGE_MINIMUM_VERSION> <IUF_CHART_MINIMUM_VERSION> \
<CRAY_NLS_CHART_MINIMUM_VERSION>"
        )
        sys.exit(1)

    k8s_minimum_version = sys.argv[1]
    iuf_cli_minimum_version = sys.argv[2]
    cluster_name = sys.argv[3]
    nls_minimum_version = sys.argv[4]
    iuf_chart_minimum_version = sys.argv[5]
    nls_chart_minimum_version = sys.argv[6]

    check_proxy()
    check_k8s_version(k8s_minimum_version)
    check_iuf_cli_version(iuf_cli_minimum_version)
    check_nls_image(nls_minimum_version)
    check_nls_pod_status()
    check_nls_workflow_server()
    check_nls_workflow_controller()
    check_nls_postgres()
    check_cray_iuf_chart(iuf_chart_minimum_version)
    check_cray_nls_chart(nls_chart_minimum_version)
    check_cfs()
    check_sat()
    check_docs_and_libcsm()
    check_cpc()
    check_available_space()
    check_url_status(cluster_name)
    check_ssh()

    print("-----------------------END OF PRE-CHECKS--------------------")
    print()


if __name__ == "__main__":
    main()
