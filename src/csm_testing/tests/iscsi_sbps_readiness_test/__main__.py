#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
This script validates run iSCSI SBPS Readiness Test.
"""
import sys
import re
import os
from typing import List, Tuple
from csm_testing.lib.iscsi_common import (
    run_command,
    get_compute_node,
    get_worker_node,
    check_cli_minimum_version_xname,
    iscsi_sbps_failed,
)


def get_fileio_count(command_output: str) -> int:
    """
    Function to get fileio objects count
    Args:
        command_output(string): targetcli output
    Returns:
        fileio objects count
    """
    lines = command_output.splitlines()
    for line in lines:
        if "fileio" in line:
            # Extract the "Storage Objects" count
            start_idx = line.find("[Storage Objects:") + len("[Storage Objects:")
            end_idx = line.find("]", start_idx)
            count = int(line[start_idx:end_idx].strip())
            print(f"INFO: LIO fileio backstore count: {count}")
            return count


def get_lun_count(command_output: str) -> int:
    """
    Function to get LUNs count
    Args:
        command_output(string): targetcli output
    Returns:
        LUNs count
    """
    lines = command_output.splitlines()
    for line in lines:
        if "luns" in line.lower() and "LUNs:" in line:
            # Extract LUN count
            start_idx = line.find("[LUNs:") + len("[LUNs:")
            end_idx = line.find("]", start_idx)
            count = int(line[start_idx:end_idx].strip())
            print(f"INFO: iSCSI LUNs count: {count}")
            return count


def count_entries(command_output: str, section: str) -> Tuple[int, int]:
    """
    Function to get squashfs , rootfs count .
    Args:
        command_output(string),section(string)
    Returns:
       squashfs_count(int), rootfs_count(int)
    """
    lines = command_output.splitlines()
    inside_section = False
    squashfs_count = 0
    rootfs_count = 0

    for line in lines:
        if section in line.lower():  # Identify the relevant section
            inside_section = True
        elif inside_section and line.strip() == "":  # Exit the section
            break
        elif inside_section:
            if ".squashfs" in line:
                squashfs_count += 1
            if "/rootfs" in line:
                rootfs_count += 1

    return squashfs_count, rootfs_count


def get_fileio_objects(targetcli_output: str) -> List[str]:
    """
    Function to get list of fileio objects
    Args:
        targetcli_output(string)
    Returns:
        fileio objects List
    """
    # Regex pattern to extract FileIO Storage Objects
    fileio_pattern = r"\[(/var/lib/cps-local/boot-images/.+?\.squashfs|/var/lib/cps-local/boot-images/.+?/rootfs)"  # pylint: disable=line-too-long

    # Extract FileIO Storage Objects
    fileio_objects = re.findall(fileio_pattern, targetcli_output)
    return fileio_objects


def get_luns(targetcli_output: str) -> List[str]:
    """
    Function to get list of LUNS
    Args:
        targetcli_output(string)
    Returns:
        LUNs List
    """
    # Regex pattern to extract LUNS
    luns_pattern = r"\[fileio/[a-z0-9]+ \((/var/lib/cps-local/boot-images/.+?\.squashfs|/var/lib/cps-local/boot-images/.+?/rootfs)\)"  # pylint: disable=line-too-long

    # Extract LUNs
    luns = re.findall(luns_pattern, targetcli_output)
    return luns


def compare_fileio_luns(fileio_objects: List[str], luns: List[str]) -> None:
    """
    Function to compare given fileio objects , LUNS and print the result info.
    Args:
        fileio_objects(int), luns(int) : Lists to compare
    Returns:
        None
    """
    # check if fileio objects are present in LUNS
    comparison = {path: (path in luns) for path in fileio_objects}
    print("INFO: Starting Comparison of FileIO with iSCSI LUNs:")
    for path, is_present in comparison.items():
        if not is_present:
            print(f"ERROR:  {path}: Not in iSCSI LUNs")
            iscsi_sbps_failed()
    print("INFO:  Comparison of FileIO with iSCSI LUNs completed sucessfully")


def check_targetcli_output(xname: str) -> None:
    """
    check targetcli ls output on worker nodes
    Args:
        xname(str)
    Returns:
        None
    """
    # Get targetcli output on worker nodes and verify output for iscsi readiness
    ssh_command = f'ssh -o BatchMode=yes -q  root@{xname} "targetcli ls" '
    targetcli_output, returncode = run_command(ssh_command)
    if returncode != 0:
        print(
            f"ERROR: Command targetcli ls returned error on {xname}. Return code: {returncode}"
        )
        iscsi_sbps_failed(xname)
    fileio_count = get_fileio_count(targetcli_output)
    lun_count = get_lun_count(targetcli_output)

    # check if there are equal fileio backstore objects, LUNs
    if fileio_count != lun_count:
        print(
            f"ERROR: Number of LIO fileio backstore ({fileio_count}) and "
            f"iSCSI LUNs ({lun_count}) do not match for {xname}"
        )
        iscsi_sbps_failed(xname)
        print(
        f"INFO: There are equal number ({lun_count}) of LIO fileio "
        f"backstore and iSCSI LUNs for {xname}"
    )

    if fileio_count == 0:
        print(f"WARNING: There are no fileio backstore and iSCSI LUNs for {xname}")

    # Get count of fileio_squashfs , fileio_rootfs from targetcli output
    fileio_squashfs_count, fileio_rootfs_count = count_entries(
        targetcli_output, "fileio"
    )
    print("INFO:  LIO fileio backstore:")
    print(f"INFO:  .squashfs PE image projection count : {fileio_squashfs_count}")
    print(f"INFO:  /rootfs image projection count : {fileio_rootfs_count}")

    # Get count of LUNS_squashfs , LUNS_rootfs from targetcli output
    luns_squashfs_count, luns_rootfs_count = count_entries(targetcli_output, "luns")
    print("INFO:  iSCSI LUNs:")
    print(f"INFO:  .squashfs PE image projection count : {luns_squashfs_count}")
    print(f"INFO:  /rootfs image projection count : {luns_rootfs_count}")

    # check if LUNS_squashfs , fileio_squashfs backstore objects are equal
    if fileio_squashfs_count != luns_squashfs_count:
        print(
            "ERROR: Number of PE image projections in LIO fileio "
            f"backstore ({fileio_squashfs_count}) and PE LUNs "
            f"({luns_squashfs_count}) do not match for {xname}"
        )
        iscsi_sbps_failed(xname)
    print(
        "INFO: Number of PE image projections in LIO fileio backstore "
        f"({luns_squashfs_count}) = iSCSI PE LUNs for {xname}"
    )
    if fileio_squashfs_count == 0:
        print(f"WARNING: There are no PE image projections for {xname}")

    # check if LUNS_rootfs , fileio_rootfs backstore objects are equal
    if fileio_rootfs_count != luns_rootfs_count:
        print(
            "ERROR: Number of rootfs image projections in LIO fileio backstore "
            f"({fileio_rootfs_count}) and LUNs ({luns_rootfs_count}) do not match "
            f"for {xname}"
        )
        iscsi_sbps_failed(xname)
    print(
        "INFO: Number of rootfs image projections in LIO fileio backstore "
        f"({luns_rootfs_count}) = rootfs LUNs for {xname}"
    )
    if fileio_rootfs_count == 0:
        print(f"WARNING: There are no rootfs image projections for {xname}")

    fileio_objects = get_fileio_objects(targetcli_output)
    luns = get_luns(targetcli_output)
    # check if fileio objects are present in LUNS
    compare_fileio_luns(fileio_objects, luns)


def check_target_service(xname: str) -> None:
    """
    Function to check target service and print the info.
    Args:
        xname(str)
    Returns:
        None
    """
    # check if target.service is active or not on all configured  worker nodes
    ssh_command = (
        f'ssh -o BatchMode=yes -q  root@{xname} "systemctl is-active target.service"  '
    )
    target_service_status, returncode = run_command(ssh_command)
    if returncode != 0 or target_service_status.strip() != "active":
        print(f"ERROR: iscsid service status is inactive on {xname} worker node")
        iscsi_sbps_failed(xname)
    print(f"INFO: target service status is active on {xname} worker node")


def iscsi_sbps_sanity_check(xname: str) -> bool:
    """
    Function to check iSCSI  sbps sanity and print the info.
    Args:
        xname(str)
    Returns:
        Bool
    """

    # Specify path
    iscsi_sbps_sanity_path = "/opt/cray/tests/install/ncn/scripts/iscsi_sbps_sanity.sh"
    ssh_command = f'ssh -o BatchMode=yes -q  root@{xname} "{iscsi_sbps_sanity_path}" '

    sbps_sanity_check_output, returncode = run_command(ssh_command)
    sbps_sanity_check_output = sbps_sanity_check_output.split("\n")
    skip_test_case = False
    if returncode != 0:
        print(f"ERROR: iSCSI sanity check failed on {xname}")
        for line in sbps_sanity_check_output:
            print(f"DEBUG: {line}")
        iscsi_sbps_failed(xname)
    if "iSCSI is not configured, exiting" in sbps_sanity_check_output:
        print(f"WARNING: iSCSI is not configured on {xname}")
        skip_test_case = True
    return skip_test_case


def main() -> None:
    """
    The main entry point and it exits at each error
    Args:
        None
    Returns:
        None
    """
    print(
        "----------------------START OF iSCSI SBPS Readiness Test -------------------\n"
    )
    print("INFO: Running iSCSI SBPS Readiness Test")
    # check if there are required arguments are passed or not
    if len(sys.argv) != 5:
        print(
            """Usage: script.py  <target_cli_minimum_version>
            <python3_targetcli_fb_minimum_version> <sbps_marshal_cli_minimum_version>
            <python_rtslib_minimum_version>"""
        )
        iscsi_sbps_failed()

    cli_minimum_version_dict = {}
    cli_minimum_version_dict["targetcli-fb-common"] = sys.argv[1]
    cli_minimum_version_dict["python3-targetcli-fb"] = sys.argv[2]
    cli_minimum_version_dict["sbps-marshal"] = sys.argv[3]
    cli_minimum_version_dict["python-rtslib-fb-common"] = sys.argv[4]

    # check iSCSI SBPS Readiness on worker nodes
    sbps_readiness_node_count = 0
    for xname in get_worker_node():
        print(
            f"\n-------------START OF iSCSI SBPS Readiness Test on worker node {xname}----------"
        )
        print(f"INFO: Running iSCSI SBPS Readiness Test on worker node {xname}")
        iscsi_sbps_sanity_check(xname)
        if not iscsi_sbps_sanity_check(xname):
            check_targetcli_output(xname)
            check_target_service(xname)

            for cli_name, cli_minimum_version in cli_minimum_version_dict.items():
                check_cli_minimum_version_xname(cli_name, cli_minimum_version, xname)

            print(f"INFO: iSCSI SBPS Readiness Test Successful on worker node {xname}")
            sbps_readiness_node_count += 1
        else:
            print(f"INFO: Skipping iSCSI SBPS Readiness Test on worker node {xname}")

        print(
            f"-------------END OF iSCSI SBPS Readiness Test on worker node {xname}--------------"
        )

    if sbps_readiness_node_count >= 2:
        print("INFO: iSCSI SBPS Readiness Test Successful on worker nodes")
    else:
        print(
            "ERROR: iSCSI SBPS Readiness Test is not Successful on at least 2 worker nodes"
        )
        iscsi_sbps_failed()

    print(
        "------------------START OF iSCSI SBPS Readiness Test on compute nodes----------------"
    )

    # Get compute nodes list and check if iSCSI initiator s/w is running on compute nodes
    compute_nodes = ",".join(get_compute_node())
    os.environ[
        "PDSH_SSH_ARGS"
    ] = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
    iscsiadm_command = f"pdsh -k -w {compute_nodes} 'iscsiadm --help'"
    iscsiadm_output, returncode = run_command(iscsiadm_command)
    if returncode != 0:
        print("INFO: iSCSI initiator s/w is not running on some compute node")
        iscsiadm_output_lines = iscsiadm_output.split("\n")
        for line in iscsiadm_output_lines:
            xname, iscsiadm_command_xname = line.split()
            print(f"ERROR: Unable to run iSCSI initiator s/w on {xname} compute node.")
            print(f"ERROR: {iscsiadm_command_xname}")
        iscsi_sbps_failed()
    else:
        print("INFO: iSCSI initiator s/w is running on compute nodes")

    print("INFO: iSCSI SBPS Readiness Test Successful on compute nodes")
    print(
        "--------------END OF iSCSI SBPS Readiness Test Successful on Compute nodes-------------"
    )
    print("INFO: iSCSI SBPS Readiness Test Successful")

    print("---------------------END OF iSCSI SBPS Readiness Test------------------")


if __name__ == "__main__":
    main()
