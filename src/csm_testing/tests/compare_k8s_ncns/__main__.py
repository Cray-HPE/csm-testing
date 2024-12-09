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
    master_kver_map: NcnKernelVersionMapType
    worker_kver_map: NcnKernelVersionMapType
    node_info_values: NcnNodeInfoValuesMap
    num_workers: int
    num_masters: int


def print_err(msg: str) -> None:
    """
    Print message to stderr, prepended with ERROR, plus a newline
    """
    sys.stderr.write(f"ERROR: {msg}\n")


def update_kernel_data(ncn_name: str, ncn_kver: str,
                       kernel_version_map: NcnKernelVersionMapType) -> None:
    """
    Print the kernel version.
    If the specified kernel version is invalid, raise a ValueError.
    Otherwise, update the specified kernel_version_map with the specified kernel version for the
    specified NCN.
    """
    print(f"kernel_version = '{ncn_kver}'")
    if not ncn_kver:
        raise ValueError(
            f"Empty kernel version field in node_info for {ncn_name}")
    if ncn_kver in kernel_version_map:
        kernel_version_map[ncn_kver].append(ncn_name)
    else:
        kernel_version_map[ncn_kver] = [ncn_name]


def update_node_info_field(ncn_name: str, field: str, ncn_field_value: str,
                           node_info_values: NcnNodeInfoValuesMap) -> None:
    """
    Print the name and value of the field.
    If the value is blank, raise a ValueError.
    Otherwise, update the specified node_info_values map.
    """
    print(f"{field} = '{ncn_field_value}'")
    if not ncn_field_value:
        raise ValueError(f"Empty {field} field in node_info for {ncn_name}")
    if ncn_field_value in node_info_values[field]:
        node_info_values[field][ncn_field_value].append(ncn_name)
    else:
        node_info_values[field][ncn_field_value] = [ncn_name]


def classify_ncn(ncn_name: str, num_workers: int,
                 num_masters: int) -> Tuple[int, int, bool]:
    """
    Raises ValueError if specified NCN name is invalid.
    Returns Tuple:
    updated num_workers,
    updated num_masters,
    True if NCN is a worker, False otherwise
    """
    if ncn_name[:5] == "ncn-m":
        worker_ncn = False
        num_masters += 1
    elif ncn_name[:5] == "ncn-w":
        worker_ncn = True
        num_workers += 1
    else:
        raise ValueError(f"NCN name has unexpected format: {ncn_name}")
    return num_workers, num_masters, worker_ncn


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

    master_kver_map = {}
    worker_kver_map = {}
    node_info_values = {field: {} for field in KubernetesNodeInfoFields}

    num_workers = 0
    num_masters = 0

    for ncn in node_list.items:
        ncn_name = ncn.metadata.name
        print(f"\nChecking data for {ncn_name}")
        try:
            num_workers, num_masters, worker_ncn = classify_ncn(
                ncn_name, num_workers, num_masters)
        except ValueError as exc:
            print_err(str(exc))
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
            update_kernel_data(
                ncn_name, ncn_kver,
                worker_kver_map if worker_ncn else master_kver_map)
        except AttributeError:
            print_err(
                f"Unable to find kernel_version field in node_info for {ncn_name}"
            )
            passed = False
        except ValueError as exc:
            print_err(str(exc))
            passed = False

        for field in KubernetesNodeInfoFields:
            try:
                ncn_field_value = getattr(node_info, field)
                update_node_info_field(ncn_name, field, ncn_field_value,
                                       node_info_values)
            except AttributeError:
                print_err(
                    f"Unable to find {field} field in node_info for {ncn_name}"
                )
                passed = False
            except ValueError as exc:
                print_err(str(exc))
                passed = False

    return K8sNodeInfo(master_kver_map=master_kver_map,
                       worker_kver_map=worker_kver_map,
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
    worker_kver_map = k8s_node_info.worker_kver_map
    master_kver_map = k8s_node_info.master_kver_map
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

    if len(worker_kver_map) > 1:
        print_err("Not all worker NCNs have the same kernel_version")
        print(f"{worker_kver_map}\n")
        passed = False
    if len(master_kver_map) > 1:
        print_err("Not all master NCNs have the same kernel_version")
        print(f"{master_kver_map}\n")
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
