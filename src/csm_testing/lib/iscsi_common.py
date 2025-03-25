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
The script has common functions being used by iscsi tests scripts
"""
import sys
import subprocess
import re
from typing import List, NoReturn, Optional, Tuple
from packaging import version


def run_command(command: str) -> Tuple[str, int]:
    """
    Function to run a given command
    Args:
        command(str): Command to be executed
    Returns:
        stdout/stderr(str),returncode(int)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return result.stdout.strip(), result.returncode
    except subprocess.CalledProcessError as err:
        if err.stderr.strip():
            return err.stderr.strip(), err.returncode
        return err.stdout.strip(), err.returncode


def compare_versions(version1: str, version2: str) -> bool:
    """
    Function to compare given two versions and print the result info.
    Args:
        version1(str), version2(str) : versions to compare
    Returns:
        Bool
    """
    ver_1 = version.parse(version.Version(version1).base_version)
    ver_2 = version.parse(version2)

    if ver_1 < ver_2:
        return False
    return True


def iscsi_prechecks_failed() -> NoReturn:
    """
    Function to handle exit and print the ERROR info.
    Args:
        None
    Returns:
        None
    """
    print("ERROR: iSCSI pre checks Failed")
    print(
        "-----------------------END OF iSCSI PRE-CHECKS--------------------------------"
    )
    sys.exit(1)


def iscsi_sbps_failed(xname: Optional[str] = None) -> NoReturn:
    """
    Function to handle exit and print the ERROR info.
    Args:
        xname(str)
    Returns:
        None
    """
    if xname is not None:
        print(f"ERROR: iSCSI SBPS Readiness Test Failed on Worker Node {xname}")
        print(
            f"---------------------END OF iSCSI SBPS Readiness Test on {xname}------------------"
        )
    else:
        print("ERROR: iSCSI SBPS Readiness Test Failed")
        print(
            "-----------------------END OF iSCSI SBPS Readiness Test--------------------"
        )
    sys.exit(1)


def check_ssh_xname(xname: str) -> bool:
    """
    Function to check ssh connectivity and print the info.
    Args:
        xname(string)
    Returns:
        Bool
    """
    ssh_command = f"ssh -o BatchMode=yes -q {xname} exit"
    ssh_output, returncode = run_command(ssh_command)

    if returncode == 0:
        return True
    print(f"ERROR: Unable to SSH to {xname}")
    if ssh_output != "":
        print(f"ERROR: {ssh_output}")
    return False


def get_compute_node() -> List[str]:
    """
    Function to get list of stable compute nodes.
    Args:
        None
    Returns:
        Compute Nodes List (list)
    """
    # Get List of configured compute nodes
    sat_status_output, returncode = run_command(
        command="""sat status --filter 'role=compute and \
               State=Ready and \"Configuration Status\"=configured ' \
               --fields xname  --no-borders --no-headings"""
    )
    if returncode != 0:
        print(f"ERROR: Command sat status returned error. Return code: {returncode}")
        iscsi_prechecks_failed()
    if sat_status_output == "":
        print("ERROR: No Compute Node Found")
        iscsi_prechecks_failed()
    # check if compute nodes are present
    compute_node_list = [xname.strip() for xname in sat_status_output.split("\n")]
    compute_node_list = [xname for xname in compute_node_list if check_ssh_xname(xname)]
    if len(compute_node_list) == 0:
        print(
            "ERROR: There should be atleast one iSCSI initiators/clients (compute node) node"
        )
        iscsi_prechecks_failed()
    return compute_node_list


def get_worker_node() -> List[str]:
    """
    Function to get list of stable worker nodes.
    Args:
        None
    Returns:
        Worker Nodes List (list)
    """
    # Get List of configured worker nodes
    sat_status_output, returncode = run_command(
        command="""sat status --filter 'SubRole=Worker and \
               State=Ready and \"Configuration Status\"=configured ' \
               --fields xname  --no-borders --no-headings"""
    )
    if returncode != 0:
        print(f"ERROR: Command sat status returned error. Return code: {returncode}")
        iscsi_prechecks_failed()
    if sat_status_output == "":
        print("ERROR: No worker node Found")
        iscsi_prechecks_failed()
    # check if atleast 2 worker nodes are present
    worker_node_list = [xname.strip() for xname in sat_status_output.split("\n")]
    worker_node_list = [xname for xname in worker_node_list if check_ssh_xname(xname)]
    if len(worker_node_list) < 2:
        print("ERROR: Required atleast 2 iSCSI target/server (worker node) nodes")
        iscsi_prechecks_failed()
    print("INFO: SSH to worker nodes is successful.")
    return worker_node_list


def check_cli_minimum_version_xname(
    cli_name: str, minimum_version: str, xname: str
) -> None:
    """
    Function to check cli version and print the info.
    Args:
        cli_name(str),minimum_version(str),xname(str)
    Returns:
        None
    """
    cli_version_command = f"rpm -q --qf '%{{VERSION}}' {cli_name}"
    ssh_command = f'ssh -o BatchMode=yes -q  root@{xname} "{cli_version_command}" '
    current_cli_version, returncode = run_command(ssh_command)
    if returncode != 0:
        print(f"ERROR: Failed to get {cli_name} version. Return code: {returncode}")
        iscsi_sbps_failed(xname)

    # Now clean up the version by removing the package name prefix
    # Regex to extract the version part from the package name
    matched_cli_version = re.search(r"(\d+\.\d+\.\d+)", current_cli_version)

    if not matched_cli_version:
        print("ERROR: Could not extract version from {cli_name} rpm")
        iscsi_sbps_failed(xname)

    # Now change version to required format version in compare_versions
    cleaned_cli_version = matched_cli_version.group(1)

    if not cleaned_cli_version:
        print(f"ERROR: {cli_name} rpm is not installed")
        iscsi_sbps_failed(xname)

    if not compare_versions(cleaned_cli_version, minimum_version):
        print(
            f"ERROR: {cli_name} rpm version {cleaned_cli_version} < {minimum_version}"
        )
        iscsi_sbps_failed(xname)

    print(f"INFO: {cli_name} rpm version {cleaned_cli_version} >= {minimum_version}")


def check_iscsid(node_str: str, node_role: str) -> None:
    """
    Function to check nodes iscsid service and print the info.
    Args:
        node_str(str): nodes, node_role(str)
    Returns:
        None
    """
    iscsid_command = f"pdsh -w {node_str} 'systemctl is-active iscsid.service'"
    iscsid_output, returncode = run_command(iscsid_command)
    if returncode != 0:
        iscsi_prechecks_failed()

    iscsid_output_lines = iscsid_output.split("\n")
    is_error = False
    for line in iscsid_output_lines:
        xname, iscsid_output_xname = line.split()
        if iscsid_output_xname.strip() != "active":
            print(
                f"ERROR: iscsid Service status is not active on {xname} {node_role} node"
            )
            is_error = True

    if is_error:
        print(f"ERROR: iscsid Service is not active on some {node_role} node")
        iscsi_prechecks_failed()

    print(f"INFO: iscsid Service is active on {node_role} nodes")


def check_multipathd(node_str: str, node_role: str) -> None:
    """
    Function to check nodes multipathd service and print the info.
    Args:
        node_str(str): nodes, node_role(str)
    Returns:
        None
    """
    multipathd_command = f"pdsh -w {node_str} 'systemctl is-active multipathd.service'"
    multipathd_output, returncode = run_command(multipathd_command)
    if returncode != 0:
        iscsi_prechecks_failed()

    multipathd_output_lines = multipathd_output.split("\n")
    is_error = False
    for line in multipathd_output_lines:
        xname, multipathd_output_xname = line.split()
        if multipathd_output_xname.strip() != "active":
            print(
                f"ERROR: Multipathd Service status is not active on {xname} {node_role} node"
            )
            is_error = True

    if is_error:
        print(f"ERROR: Multipathd Service is not active on some {node_role} node")
        iscsi_prechecks_failed()

    print(f"INFO: Multipathd Service is active on {node_role} nodes")
