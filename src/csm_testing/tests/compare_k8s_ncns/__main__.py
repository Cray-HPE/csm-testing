#
# MIT License
#
# (C) Copyright 2023-2024 Hewlett Packard Enterprise Development LP
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
Checks to make sure that all masters have the same kernel version,
all workers have the same kernel version, and all Kubernetes NCNs have the
same values for several other fields (enumerated below in KubernetesNodeInfoFields)
"""

import sys
from typing import Any, Dict, List, NamedTuple, Tuple

import kubernetes

KubernetesNodeInfoFields = [
    "container_runtime_version", "kube_proxy_version", "kubelet_version",
    "os_image"
]

# For type checking

# map from kernel version to list of NCN names with that version
NcnKernelVersionMapType = Dict[str, List[str]]

# map from node info field name to:
#     map from values for that field to list of NCN names with that value
NcnNodeInfoValuesMap = Dict[str, Dict[Any, List[str]]]


class K8sNodeInfo(NamedTuple):
    """
    Information about the Kubernetes nodes on the system
    """
    master_kernel_version: NcnKernelVersionMapType
    worker_kernel_version: NcnKernelVersionMapType
    node_info_values: NcnNodeInfoValuesMap
    num_workers: int
    num_masters: int


def print_err(msg: str) -> None:
    """
    Print message to stderr, prepended with ERROR, plus a newline
    """
    sys.stderr.write(f"ERROR: {msg}\n")


def get_k8s_ncn_info() -> Tuple[K8sNodeInfo, bool]:
    """
    List all Kubernetes nodes and return information about them, as well as a boolean indicating
    pass/fail, in case problems were found during the checking
    """

    print("Loading Kubernetes configuration")
    kubernetes.config.load_kube_config()
    print("Initializing Kubernetes client")
    k8s_v1 = kubernetes.client.CoreV1Api()
    print("Listing Kubernetes nodes")
    node_list = k8s_v1.list_node()

    passed = True

    master_kernel_version = {}
    worker_kernel_version = {}
    node_info_values = {field: {} for field in KubernetesNodeInfoFields}

    num_workers = 0
    num_masters = 0

    for ncn in node_list.items:
        ncn_name = ncn.metadata.name
        print(f"\nChecking data for {ncn_name}")

        if ncn_name[:5] == "ncn-m":
            worker_ncn = False
            num_masters += 1
        elif ncn_name[:5] == "ncn-w":
            worker_ncn = True
            num_workers += 1
        else:
            print_err(f"NCN name has unexpected format: {ncn_name}")
            passed = False
            continue

        try:
            node_info = ncn.status.node_info
        except AttributeError:
            print_err(f"Unable to find node_info status field for {ncn_name}")
            passed = False
            continue

        try:
            ncn_kver = node_info.kernel_version
            print(f"kernel_version = '{ncn_kver}'")
            if not ncn_kver:
                print_err(
                    f"Empty kernel version field in node_info for {ncn_name}")
                passed = False
            elif worker_ncn:
                if ncn_kver in worker_kernel_version:
                    worker_kernel_version[ncn_kver].append(ncn_name)
                else:
                    worker_kernel_version[ncn_kver] = [ncn_name]
            else:
                # master NCN
                if ncn_kver in master_kernel_version:
                    master_kernel_version[ncn_kver].append(ncn_name)
                else:
                    master_kernel_version[ncn_kver] = [ncn_name]
        except AttributeError:
            print_err(
                f"Unable to find kernel_version field in node_info for {ncn_name}"
            )
            passed = False

        for field in KubernetesNodeInfoFields:
            try:
                ncn_field_value = getattr(node_info, field)
                print(f"{field} = '{ncn_field_value}'")
                if not ncn_field_value:
                    print_err(
                        f"Empty {field} field in node_info for {ncn_name}")
                    passed = False
                    continue
                if ncn_field_value in node_info_values[field]:
                    node_info_values[field][ncn_field_value].append(ncn_name)
                else:
                    node_info_values[field][ncn_field_value] = [ncn_name]
            except AttributeError:
                print_err(
                    f"Unable to find {field} field in node_info for {ncn_name}"
                )
                passed = False
    return K8sNodeInfo(master_kernel_version=master_kernel_version,
                       worker_kernel_version=worker_kernel_version,
                       node_info_values=node_info_values,
                       num_workers=num_workers,
                       num_masters=num_masters), passed


def check_k8s_node_info(k8s_node_info: K8sNodeInfo) -> bool:
    """
    Does a validation of the Kubernetes node information that was collected.
    Returns a boolean, with True indicating no problems found, and False otherwise.
    """
    passed = True
    num_masters = k8s_node_info.num_masters
    num_workers = k8s_node_info.num_workers
    worker_kernel_version = k8s_node_info.worker_kernel_version
    master_kernel_version = k8s_node_info.master_kernel_version
    node_info_values = k8s_node_info.node_info_values

    # The purpose of this test is not to make sure the number of NCNs found is correct. However,
    # because at least 2 masters and 2 workers are needed in order to do any value comparisons,
    # this test will fail if that is not the case.
    if num_masters == 0:
        print_err("No master NCNs found in list")
        passed = False
    elif num_masters == 1:
        print_err("Only one master NCN found in list")
        passed = False
    elif num_masters == 2:
        print("WARNING: Only two master NCNs found in list (three expected)")
    else:
        print(f"{num_masters} master NCNs found in list")

    if num_workers == 0:
        print_err("No worker NCNs found in list")
        passed = False
    elif num_workers == 1:
        print_err("Only one worker NCN found in list")
        passed = False
    elif num_workers == 2:
        print("WARNING: Only two worker NCNs found in list (three expected)")
    else:
        print(f"{num_workers} worker NCNs found in list")

    print("")

    if len(worker_kernel_version) > 1:
        print_err("Not all worker NCNs have the same kernel_version")
        print(f"{worker_kernel_version}\n")
        passed = False
    if len(master_kernel_version) > 1:
        print_err("Not all master NCNs have the same kernel_version")
        print(f"{master_kernel_version}\n")
        passed = False
    for field in KubernetesNodeInfoFields:
        if len(node_info_values[field]) > 1:
            print_err(f"Not all Kubernetes NCNs have the same {field}")
            print(f"{node_info_values[field]}\n")
            passed = False
    return passed


def main() -> None:  # pylint: disable=missing-function-docstring
    k8s_node_info, passed = get_k8s_ncn_info()
    if not check_k8s_node_info(k8s_node_info):
        passed = False

    if passed:
        print("PASSED")
        sys.exit(0)
    sys.stderr.write("FAILED\n")
    sys.exit(1)


if __name__ == '__main__':
    main()
