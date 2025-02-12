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
This script validates run iSCSI PRE-CHECKS.
"""

import os
import sys
import re
import json
from csm_testing.lib.iscsi_common import (
    run_command,
    compare_versions,
    iscsi_prechecks_failed,
    get_compute_node,
    get_worker_node,
    check_iscsid,
    check_multipathd,
)


def check_craycli_minimum_version(minimum_version: str) -> None:
    """
    Function to check craycli version and print the info.
    Args:
        minimum_version(str)
    Returns:
        None
    """
    craycli_current_version, returncode = run_command(
        command="rpm -qa | grep craycli | sed 's/^[a-zA-Z.-]*-\\([0-9][^ ]*\\)-.*$/\\1/'"
    )
    if returncode != 0:
        print("ERROR: craycli rpm is not installed. Return code: {returncode}")
        iscsi_prechecks_failed()
    # Now clean up the version by removing the package name prefix
    # Regex to extract the version part from the package name
    matched_craycli_version = re.search(r"(\d+\.\d+\.\d+)", craycli_current_version)
    if not matched_craycli_version:
        print(
            f"ERROR: Failed to extract craycli rpm version : {craycli_current_version}"
        )
        iscsi_prechecks_failed()
    # Now change version to required format version in compare_versions
    cleaned_craycli_version = matched_craycli_version.group(1)
    if not cleaned_craycli_version:
        print(
            f"ERROR: Failed to extract craycli rpm version : {matched_craycli_version}"
        )
        iscsi_prechecks_failed()
    if not compare_versions(cleaned_craycli_version, minimum_version):
        print(
            f"ERROR: craycli rpm version {cleaned_craycli_version} < {minimum_version}"
        )
        iscsi_prechecks_failed()
    print(f"INFO: craycli rpm version {cleaned_craycli_version} >= {minimum_version}")


def check_bos_minimum_version(minimum_version: str) -> None:
    """
    Function to check cray bos version and print the info.
    Args:
        minimum_version(str)
    Returns:
        None
    """
    command = "cray bos version list"
    cray_bos_current_version, returncode = run_command(command)
    if returncode != 0:
        print(
            f"ERROR: Failed to get {cray_bos_current_version} version. Return code: {returncode}"
        )
        iscsi_prechecks_failed()
    # Regular expression to extract major, minor, and patch
    version_pattern = r'major\s*=\s*"(.*?)".*?minor\s*=\s*"(.*?)".*?patch\s*=\s*"(.*?)"'

    # Search for the pattern
    cray_bos_version = re.search(version_pattern, cray_bos_current_version, re.DOTALL)

    # Construct the version if match is found
    if not cray_bos_version:
        print("ERROR: cray bos version not found")
        iscsi_prechecks_failed()

    # Now change version to required format version in compare_versions
    major, minor, patch = cray_bos_version.groups()
    cray_bos_cleaned_version = f"{major}.{minor}.{patch}"
    if not compare_versions(cray_bos_cleaned_version, minimum_version):
        print(f"ERROR: cray bos version {cray_bos_cleaned_version} < {minimum_version}")
        iscsi_prechecks_failed()
    print(f"INFO: cray bos version {cray_bos_cleaned_version} >= {minimum_version}")


def check_cfs_config_minimum_version(minimum_version: str) -> None:
    """
    Function to check cfs config component version and print the info.
    Args:
        minimum_version(str): cfs config component version
    Returns:
        None
    """
    cfs_config_version_command = "/usr/share/doc/csm/scripts/operations/configuration/get_git.py | awk '{ print $3 }' "  # pylint: disable=line-too-long
    current_cfs_config_version, returncode = run_command(cfs_config_version_command)

    if returncode != 0:
        print("ERROR: Failed to get CFS Config version")
        print(f"ERROR: Return code: {returncode}")
        iscsi_prechecks_failed()
    # Now change version to required format version in compare_versions
    cfs_config_cleaned_version = current_cfs_config_version.split("/")[-1]
    if not compare_versions(cfs_config_cleaned_version, minimum_version):
        print(
            f"ERROR: CFS Config version {current_cfs_config_version} < {minimum_version}"
        )
        iscsi_prechecks_failed()
    print(f"INFO: CFS Config version {current_cfs_config_version} >= {minimum_version}")


def check_ims_api_minimum_version(minimum_version: str) -> None:
    """
    Function to check ims api version and print the info.
    Args:
        minimum_version(str): ims api version
    Returns:
        None
    """
    export_token_command = """ curl -s -S -d grant_type=client_credentials \
                        -d client_id=admin-client \
                        -d client_secret=`kubectl get secrets admin-client-auth \
                        -o jsonpath='{.data.client-secret}' | base64 -d` \
                        https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token \
                        | jq -r '.access_token' """
    # Get token to use in ims api version curl command
    token, returncode = run_command(export_token_command)
    if returncode != 0:
        print(f"ERROR: Failed to extract and set token. Return code: {returncode}")
        iscsi_prechecks_failed()
    os.environ["IMS_API_TOKEN"] = token
    print("DEBUG: Successfully extracted and set token")
    ims_api_version_command = """curl -H "Authorization: Bearer ${IMS_API_TOKEN}" \
                        https://api-gw-service-nmn.local/apis/ims/version"""
    ims_api_version, returncode = run_command(ims_api_version_command)
    if returncode != 0:
        print(
            f"ERROR: Failed to get ims api {ims_api_version} version. Return code: {returncode}"
        )
        iscsi_prechecks_failed()
    json_output = json.loads(ims_api_version)
    # Now change version to required format version in compare_versions
    ims_api_cleaned_version = json_output["version"]
    if not compare_versions(ims_api_cleaned_version, minimum_version):
        print(
            f"ERROR: ims api version {ims_api_cleaned_version} < ims api  {minimum_version}"
        )
        iscsi_prechecks_failed()
    print(
        f"INFO: ims api version {ims_api_cleaned_version} >= ims api  {minimum_version}"
    )


def check_csm_minimum_version(csm_minimum_version: str) -> None:
    """
    Function to check CSM version and print the info.
    Args:
        minimum_version(str): CSM component version
    Returns:
        None
    """
    # Get List of CSM Versions
    csm_version_list_command = """sat showrev --products --filter product_name=csm \
                               --fields product_version --sort-by product_version \
                               --reverse --no-headings --no-borders"""
    csm_version_list, returncode = run_command(csm_version_list_command)
    if returncode != 0:
        print(f"ERROR: Failed to get CSM version. Return code: {returncode}")
        iscsi_prechecks_failed()
    # Find latest CSM Version from List of CSM Versions
    csm_current_version = csm_version_list.split("\n")[0].strip()
    csm_current_version = re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", csm_current_version)
    if not csm_current_version:
        print("ERROR: CSM version not found")
        iscsi_prechecks_failed()
    csm_current_version = csm_current_version.group(0)

    if not compare_versions(csm_current_version, csm_minimum_version):
        print(
            f"ERROR: CSM version {csm_current_version} < CSM version {csm_minimum_version}"
        )
        iscsi_prechecks_failed()
    print(
        f"INFO: CSM version {csm_current_version} >= CSM version {csm_minimum_version}"
    )


def check_uss_minimum_version(uss_minimum_version: str) -> None:
    """
    Function to check USS version and print the info.
    Args:
        minimum_version(str): USS version
    Returns:
        None
    """
    # Get List of USS Versions
    uss_version_list_command = """sat showrev --products --filter product_name=uss \
                            --fields product_version --sort-by product_version \
                            --reverse --no-headings --no-borders"""
    uss_version_list, returncode = run_command(uss_version_list_command)
    # Find latest USS Version from List of USS Versions
    uss_current_version = uss_version_list.split("\n")[0].strip().split("-")[0]
    if returncode != 0:
        print(f"ERROR: Failed to get USS version. Return code: {returncode}")
        iscsi_prechecks_failed()
    if not compare_versions(uss_current_version, uss_minimum_version):
        print(f"ERROR: USS version {uss_current_version} < {uss_minimum_version}")
        iscsi_prechecks_failed()
    print(f"INFO: USS version {uss_current_version} >= {uss_minimum_version}")


def main() -> None:
    """
    The main entry point and it exits at each error
    Args:
        None
    Returns:
        None
    """
    print(
        "----------------------START OF iSCSI PRE-CHECKS-------------------------------"
    )
    print("INFO: Running iSCSI pre-checks\n")
    print(
        "----------------------START OF iSCSI master node PRE-CHECKS-------------------"
    )
    hostname = os.environ.get("HOSTNAME")
    print(f"INFO: Running iSCSI pre-checks on {hostname}")
    # check if there are required arguments are passed or not
    if len(sys.argv) != 7:
        print(
            """ Usage: script.py  <csm_minimum_version> <uss_minimum_version>
            <cfs_minimum_version>  <ims_api_minimum_version>
            <cray_cli_minimum_version>  <cray_bos_minimum_version> """
        )
        iscsi_prechecks_failed()

    csm_minimum_version = sys.argv[1]
    check_csm_minimum_version(csm_minimum_version)

    uss_minimum_version = sys.argv[2]
    check_uss_minimum_version(uss_minimum_version)

    cfs_config_minimum_version = sys.argv[3]
    check_cfs_config_minimum_version(cfs_config_minimum_version)

    ims_api_minimum_version = sys.argv[4]
    check_ims_api_minimum_version(ims_api_minimum_version)

    cray_cli_minimum_version = sys.argv[5]
    check_craycli_minimum_version(cray_cli_minimum_version)

    cray_bos_minimum_version = sys.argv[6]
    check_bos_minimum_version(cray_bos_minimum_version)

    print(f"INFO: iSCSI master node pre checks Successful on {hostname}")
    print(
        "-----------------------END OF iSCSI master node PRE-CHECKS--------------------\n"
    )

    # check if atleast 2 worker nodes are present
    get_worker_node()

    print(
        "\n--------------------START OF iSCSI compute node PRE-CHECKS---------------------------"
    )
    print("INFO: Running iSCSI compute node pre-checks\n")
    # Get list of compute nodes and check iscsid,multipathd service on compute nodes
    compute_node_list = get_compute_node()
    compute_node_str = ",".join(compute_node_list)
    os.environ[
        "PDSH_SSH_ARGS"
    ] = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

    # check iscsid service on compute nodes
    check_iscsid(compute_node_str, "compute")
    # check multipathd service on compute nodes
    check_multipathd(compute_node_str, "compute")

    print("INFO: iSCSI compute node prechecks Successful")
    print(
        "-----------------------END OF iSCSI Compute Node PRE-CHECKS--------------------"
    )

    print("INFO: iSCSI pre checks Successful")
    print(
        "-----------------------END OF iSCSI PRE-CHECKS--------------------------------"
    )


if __name__ == "__main__":
    main()
