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
This script checks workflow templates.
"""

import json
import subprocess
import sys
import time
from kubernetes import client, config
import yaml


def is_main_container_finished(pod_name: str, namespace: str) -> bool:
    """
    Function to check if the main container is terminated
    Args:
        pod_name(str): Pod Name
        namespace(str): Pod Namespace
    Returns:
        Boolean True: if the main container is terminated
        Boolean False: if the main container is still running
    """
    k8s_v1 = client.CoreV1Api()
    pod = k8s_v1.read_namespaced_pod(name=pod_name, namespace=namespace)

    for container_status in pod.status.container_statuses:
        if container_status.name == "main":
            if container_status.state.terminated:
                return True
    return False


def check_and_kill_pod(workflow_name: str, namespace: str) -> bool:
    """
    Kills the pod if the main container is finished
    Args:
        worlflow_name(str): Name of the workflow
        namespace(str): Namespace of the workflow
    Returns:
        Boolean True: if the pod with terminated main container is deleted
        Boolean False: if the main container is still running in the pod
    """
    k8s_v1 = client.CoreV1Api()

    pods = k8s_v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"workflows.argoproj.io/workflow={workflow_name}",
    ).items

    for pod in pods:
        pod_name = pod.metadata.name
        print(f"INFO: Checking pod: {pod_name}")

        # Check if the main container has finished
        if is_main_container_finished(pod_name, namespace):
            print(f"INFO: Main container finished in pod {pod_name}. Deleting pod.")
            k8s_v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
            print(f"INFO: Pod {pod_name} deleted.")
            return True
        print(f"INFO: Main container still running in pod {pod_name}.")
    return False


def update_image_version_in_template(
    workflow_template_str: str,
    old_image_prefix: str,
    old_version: str,
    new_version: str,
):
    """Find the image in the workflowtemplate and replace its version
    with the user provided version

    Args:
        workflow_template_str (str): workflow template
        old_image_prefix (str): old image
        old_version (str): old image version
        new_version (str): new image version

    Returns:
        str: updated workflow template
    """
    updated_workflow_template_str = workflow_template_str.replace(
        old_image_prefix + old_version, old_image_prefix + new_version
    )
    return updated_workflow_template_str


def wait_for_workflow_to_succeed(
    namespace: str, workflow_name: str, timeout=6000, interval=20
):
    """
    Polls the workflow status until it succeeds or the timeout is reached.
    Args:
        namespace(str): Namespace of the workflow
        workflow_name(str): Workflow name
        timeout(int): Timeout duration
        interval(int): Interval duration
    Returns:
        Boolean: If workflow succeeds returns True,False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Get the workflow status
            command = [
                "kubectl",
                "get",
                "workflow",
                workflow_name,
                "-n",
                namespace,
                "-o",
                "jsonpath={.status.phase}",
            ]
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        except subprocess.CalledProcessError as err:
            print(f"ERROR: Exception when fetching workflow status: {err}")
            return False

        status = result.stdout.strip()

        # Check the status of the workflow
        print(f"Workflow {workflow_name} status: {status}")

        if status == "Succeeded":
            print(f"INFO: Workflow {workflow_name} succeeded.")
            return True

        if status in ["Failed", "Error"]:
            print(f"ERROR: Workflow {workflow_name} failed with status {status}.")
            return False

        if status == "Running":
            print("INFO: Check if main is done")
            if check_and_kill_pod(workflow_name, namespace):
                print(
                    f"WARNING: {workflow_name} is running but the main container is done."
                )
                return True
            return False

        # Wait before polling again
        time.sleep(interval)

    print(f"ERROR: Workflow {workflow_name} did not complete within {timeout} seconds.")
    return False


def delete_resources(namespace, workflow_name, workflow_template_name):
    """
    Delete the workflow, workflow template, and associated pods.
    Args:
        namespace(str): Namespace name
        workflow_name(str): Workflow name
        workflow_template_name(str): Workflow template name
    Returns:
        None
    """

    for resource, name in [
        ("workflow", workflow_name),
        ("workflowtemplate", workflow_template_name),
    ]:
        try:
            print(f"INFO: Deleting {resource} {name}...")
            subprocess.run(
                ["kubectl", "delete", resource, name, "-n", namespace], check=True
            )
            print(f"INFO: {resource.capitalize()} {name} deleted successfully.")
        except subprocess.CalledProcessError as err:
            print(f"ERROR: Failed to delete {resource} {name}: {err}")
            continue

    try:
        print(f"INFO: Finding pods owned by workflow {workflow_name}...")
        pods_json = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            check=True,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        ).stdout
    except subprocess.CalledProcessError as err:
        print(f"ERROR: Failed to retrieve pod list for workflow {workflow_name}: {err}")
        return
    try:
        pod_names = [
            pod["metadata"]["name"]
            for pod in json.loads(pods_json).get("items", [])
            if any(
                owner.get("name") == workflow_name
                for owner in pod.get("metadata", {}).get("ownerReferences", [])
            )
        ]

    except json.JSONDecodeError as err:
        print(f"ERROR: Failed to parse pod list: {err}")
        return

    # Delete the found pods
    if not pod_names:
        print(f"INFO: No pods found for workflow {workflow_name}.")
        return

    for pod_name in pod_names:
        try:
            print(f"INFO: Deleting pod {pod_name}...")
            subprocess.run(
                ["kubectl", "delete", "pod", pod_name, "-n", namespace], check=True
            )
            print(f"INFO: Pod {pod_name} deleted successfully.")
        except subprocess.CalledProcessError as err:
            print(f"ERROR: Failed to delete pod {pod_name}: {err}")


def create_workflowtemplate_and_workflow(
    workflow_template_dict: dict, workflow_dict: dict
):
    """
    Function to create workflow and workflow template
    Args:
        workflow_template_dict(dict): Wokflow templates
        workflow_dict(dict): Workflows
    Returns:
        None
    """
    api_instance = client.CustomObjectsApi()
    group = "argoproj.io"
    version = "v1alpha1"
    namespace = "argo"
    plural = "workflowtemplates"

    # Create the WorkflowTemplate in Kubernetes
    try:
        api_response = api_instance.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=plural,
            body=workflow_template_dict,
        )
        print("INFO: WorkflowTemplate created.")
    except client.exceptions.ApiException as err:
        if err.status == 409:
            print("INFO: WorkflowTemplate already exists, updating it...")
            api_response = api_instance.patch_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=workflow_template_dict["metadata"]["name"],
                body=workflow_template_dict,
            )
            print("INFO: WorkflowTemplate updated.")
        else:
            print(f"ERROR: Exception when creating WorkflowTemplate: {err}")
            sys.exit(1)

    # Submit the workflow
    try:
        api_response = api_instance.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural="workflows",
            body=workflow_dict,
        )
        print("INFO: Workflow submitted. Status:", api_response)
        return api_response
    except client.exceptions.ApiException as err:
        print(f"ERROR: Exception when submitting workflow: {err}")
        sys.exit(1)
    return None


def main():
    """
    The main entry point
    """
    if len(sys.argv) != 4:
        print(
            "Usage: python script.py <workflow_template_file_path> "
            "<workflow_file_path> <new_image_version>"
        )
        sys.exit(1)

    workflow_template_file = sys.argv[1]
    workflow_file = sys.argv[2]
    new_version = sys.argv[3]

    config.load_kube_config()

    with open(workflow_template_file, "r", encoding="utf-8") as stream:
        workflow_template_str = stream.read()

    # Update the image version in the WorkflowTemplate
    if "update_cpc_workflow.yaml" in workflow_file:
        old_image_prefix = "cray-product-catalog-update:"
        old_version = "2.0.1"
    elif "iuf_base_workflow.yaml" in workflow_file:
        old_image_prefix = "iuf:"
        old_version = "v0.1.12"  # Existing version for iuf
    else:
        print(f"ERROR: Unknown workflow file: {workflow_file}")
        sys.exit(1)

    # Update the image version in the WorkflowTemplate
    updated_workflow_template_str = update_image_version_in_template(
        workflow_template_str, old_image_prefix, old_version, new_version
    )

    # Load the updated string back into a YAML dict
    workflow_template_dict = yaml.safe_load(updated_workflow_template_str)

    # Load the Workflow YAML file
    with open(workflow_file, "r", encoding="utf-8") as stream:
        workflow_dict = yaml.safe_load(stream)

    api_response = create_workflowtemplate_and_workflow(
        workflow_template_dict, workflow_dict
    )
    workflow_name = api_response.get("metadata", {}).get("name")

    if not workflow_name:
        print("ERROR: Workflow name not found in the response.")
        sys.exit(1)

    workflow_template_name = workflow_template_dict["metadata"]["name"]

    print(f"INFO: Waiting for workflow {workflow_name} to succeed...")
    # Wait for the workflow to succeed
    time.sleep(15)
    workflow_status = wait_for_workflow_to_succeed("argo", workflow_name)

    if workflow_status:
        print("INFO: Workflow completed successfully, proceeding to next step.")
    else:
        print("ERROR: Workflow did not succeed, aborting.")
        sys.exit(1)

    delete_resources("argo", workflow_name, workflow_template_name)


if __name__ == "__main__":
    main()
