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

"""iSCSI node reboot test case"""

import sys
import time
import json
from jinja2 import Template
from csm_testing.lib.iscsi_common import run_command, get_compute_node, get_uan_node


class RebootError(Exception):
    """Custom exception class for handling boot errors."""


def get_node(node_type: str) -> str:
    """Fetches a node xName.

    Args:
        node_type (str): Compute or UAN

    Raises:
        RebootError : if invalid node type (other that compute or uan) is provided
        RebootError : if no nodes are found

    Returns:
        str: xname of the node
    """
    if node_type.lower() == "compute":
        nodes = get_compute_node()
    elif node_type.lower() == "uan":
        nodes = get_uan_node()
    else:
        raise RebootError(f"ERROR: Invalid node type provided: {node_type}")

    node = nodes[0] if nodes else None
    print(f"INFO: Using {node} for reboot")
    if not node:
        raise RebootError(f"ERROR: No {node_type} nodes found.")
    return node


def set_node_type(node_type: str) -> str:
    """sets the node name in bos template input file.

    Args:
        node_type (str) : Compute or UAN

    Returns:
        str: updated contents of bos template input file
    """

    if node_type.lower() == "uan":
        return "Application_UAN"
    return "Compute"


def get_rootfsproviderpassthrough(intfc: str) -> str:
    """sets the rootfsproviderpassthrough field in bos template input file.

    Args:
        intfc (str) : NMN or HSN

    Raises:
        RebootError : if the run_command fails

    Returns:
        rfp (str): rootfs provider passthrough
    """

    # Get the system name
    get_system_command = "craysys metadata get system-name"
    try:
        my_system_name, _ = run_command(get_system_command)
    except Exception as err:
        raise RebootError(
            f"Unable to run command '{get_system_command}': {err}"
        ) from err
    # Get Site Domain name
    get_site_domain_command = "craysys metadata get site-domain"
    try:
        my_site_domain, _ = run_command(get_site_domain_command)
    except Exception as err:
        raise RebootError(
            f"Unable to run command '{get_site_domain_command}': {err}"
        ) from err

    # Parse the rootfs_provider_passthrough
    rfp = (
        "sbps:v1:iqn.2023-06.csm.iscsi:_sbps-hsn._tcp.my_system_name.my_site_domain:300"
    )
    rfp = rfp.split(":")
    rfp3 = rfp[3].split(".")
    if intfc == "hsn":
        rfp3[0] = "_sbps-hsn"
    elif intfc == "nmn":
        rfp3[0] = "_sbps-nmn"
    rfp[3] = rfp3[0] + "." + rfp3[1] + "." + my_system_name + "." + my_site_domain
    rfp = rfp[0] + ":" + rfp[1] + ":" + rfp[2] + ":" + rfp[3] + ":" + rfp[-1]

    return rfp


def create_session_template(bos_session_input_file: str, node_type: str) -> str:
    """
    Creates a BOS session template using the provided input file and node type.

    Args:
        bos_session_input_file (str): The path to the BOS session input file.
        node_type (str): The type of node for which the session template is being created.

    Returns:
        str: The name of the created session template.

    Raises:
        RebootError: If the session template creation fails.
    """
    template_name = node_type.lower() + "-test-auto-template"
    # Creating the session template
    command = (
        "cray bos v2 sessiontemplates create --file "
        + bos_session_input_file
        + " "
        + template_name
    )
    print(f"INFO: Creating Bos Session Template {template_name}...")

    output, returncode = run_command(command)

    if returncode != 0:
        raise RebootError("ERROR: Unable to create the Bos Session template.")
    print(output)
    print("INFO: Bos Session Template Created.\n")
    return template_name


def monitor_boot_status(session_name: str) -> None:
    """Monitors the session booting the node

    Args:
        session_name (str): name of the session booting the node

    Raises:
        RebootError : if node monitoring fails or timeout reached
    """
    timeout = 20 * 60  # 20 minutes in seconds
    interval = 2 * 60  # 2 minutes in seconds
    elapsed_time = 0

    while elapsed_time < timeout:
        try:
            # Run the cray bos sessions describe command and capture the output
            output, _ = run_command(
                f"cray bos sessions describe {session_name} --format json"
            )
            session_info = json.loads(output)

            # Check the status
            status = session_info["status"]["status"]
            if status == "complete":
                print(f"INFO: Session {session_name} is complete.")
                return
            print(f"DEBUG: Session {session_name} status: {status}")

            # Wait for 2 minutes bfore checking again
            print("Sleeping for 2 minutes...")
            time.sleep(interval)
            elapsed_time += interval

        except Exception as err:
            raise RebootError(
                f"ERROR: An error occurred while monitoring the node: {err}"
            ) from err

    raise RebootError(
        f"ERROR: Timeout reached. Session {session_name} did not complete within 20 minutes."
    )


def reboot_and_check_multipath(node: str, template: str) -> None:
    """Reboots the compute node and checks multipath output.

    Args:
        node (str): xname of the node to be rebooted
        template (str): name of BOS session template being used for reboot

    Raises:
        RebootError: If rootfs or PE image is not found in multipath output
    """

    print(f"INFO: Rebooting node {node} using session template {template}...")
    output, _ = run_command(
        (
            f"cray bos sessions create --template-name {template} "
            f"--operation reboot --limit {node} --format json"
        )
    )
    session_info = json.loads(output)
    session_name = session_info["name"]
    print(f"INFO: Waiting for node {node} to reboot...")
    monitor_boot_status(session_name)
    time.sleep(15)

    print(f"INFO: Checking multipath output on node {node}...")
    ssh_command = f"ssh {node} 'multipath -ll'"
    multipath_output, _ = run_command(ssh_command)

    if "rootfs" in multipath_output:
        print("SUCCESS: Rootfs image found.")
    else:
        raise RebootError("ERROR: Rootfs image not found in multipath output.")

    print("INFO: Waiting for 15 minutes for PE images to come up...")
    time.sleep(900)

    retries = 2
    while retries > 0:
        print(f"INFO: Re-checking multipath output on node {node}...")
        multipath_output, _ = run_command(ssh_command)
        if "PE" in multipath_output:
            print("SUCCESS: PE image found.")
            return
        print(
            f"WARNING: PE image not found. Retrying in 5 minutes... ({retries} retries left)"
        )
        time.sleep(300)  # Wait for 5 minutes
        retries -= 1

    raise RebootError(
        "ERROR: PE image not found in multipath output after multiple retries."
    )


def main() -> None:
    """
    Main function to run the reboot test.

    Args :
        None

    Returns :
        None

    """
    if len(sys.argv) != 7:
        print(
            "Usage: script.py <node_type> <interface_type> "
            "<image_path> <image_etag> <cfs_configuration> <json_path>"
        )
        sys.exit(1)
    try:
        node = get_node(sys.argv[1])

        # Load the JSON template
        try:
            with open(
                f"{sys.argv[6]}/bos-template.json", "r", encoding="utf-8"
            ) as file:
                template_content = file.read()
        except Exception as err:
            raise RebootError(f"Unable to update the bos-template.json: {err}") from err

        # Create a Jinja2 Template object
        template = Template(template_content)

        context = {
            "description": (
                f"Template for booting {sys.argv[1]} nodes, "
                "generated by the installation"
            ),
            "node_type": sys.argv[1],
            "rootfs_provider_passthrough": get_rootfsproviderpassthrough(sys.argv[2]),
            "node_roles_groups": set_node_type(sys.argv[1]),
            "path": sys.argv[3],
            "etag": sys.argv[4],
            "cfs_configuration": sys.argv[5],
        }

        rendered_content = template.render(context)

        with open(
            f"{sys.argv[6]}/bos-auto-template.json", "w", encoding="utf-8"
        ) as file:
            file.write(rendered_content)

        template_name = create_session_template(
            f"{sys.argv[6]}/bos-auto-template.json", sys.argv[1]
        )
        reboot_and_check_multipath(node, template_name)
        print("INFO: Test completed successfully.")
    except RebootError as err:
        print(f"ERROR: {err}")
        sys.exit(1)
    except Exception as err:
        print(f"Unexpected error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
