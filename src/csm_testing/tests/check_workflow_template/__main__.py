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
from kubernetes.client.rest import ApiException
import yaml

def is_main_container_finished(pod_name, namespace):
    # Create a CoreV1 API instance to interact with the pod
    v1 = client.CoreV1Api()
    pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

    # Check the status of containers in the pod
    for container_status in pod.status.container_statuses:
        if container_status.name == "main":  # Assuming main container is named "main"
            if container_status.state.terminated:
                return True
    return False

def check_and_kill_pod(workflow_name, namespace):
    v1 = client.CoreV1Api()
    
    # Get the list of pods
    pods = v1.list_namespaced_pod(namespace=namespace, label_selector=f"workflows.argoproj.io/workflow={workflow_name}").items
    
    for pod in pods:
        pod_name = pod.metadata.name
        print(f"INFO: Checking pod: {pod_name}")
        
        # Check if the main container has finished
        if is_main_container_finished(pod_name, namespace):
            print(f"INFO: Main container finished in pod {pod_name}. Deleting pod.")
            v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
            print(f"INFO: Pod {pod_name} deleted.")
            return True
        else:
            print(f"INFO: Main container still running in pod {pod_name}.")

def update_image_version_in_template(workflow_template_str,old_image_prefix,old_version, new_version):
    # Find the image string and replace its version
    updated_workflow_template_str = workflow_template_str.replace(
        old_image_prefix + old_version, 
        old_image_prefix + new_version
    )
    return updated_workflow_template_str

def wait_for_workflow_to_succeed(namespace, workflow_name, timeout=6000, interval=20):
    """
    Polls the workflow status until it succeeds or the timeout is reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Get the workflow status
            command = [
            "kubectl", "get", "workflow", workflow_name, "-n", namespace, "-o", "jsonpath={.status.phase}"
            ]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            status=result.stdout.strip()
            
            # Check the status of the workflow
            print(f"Workflow {workflow_name} status: {status}")
            
            if status == "Succeeded":
                print(f"INFO: Workflow {workflow_name} succeeded.")
                return True
            elif status in ["Failed", "Error"]:
                print(f"ERROR: Workflow {workflow_name} failed with status {status}.")
                return False
            elif status in ["Running"]:
                print("INFO; Check if main is done")
                if check_and_kill_pod(workflow_name, namespace):
                    print(f"WARNING: Workflow {workflow_name} is running but main container is done.")
                    return True
        except ApiException as e:
            print(f"ERROR: Exception when fetching workflow status: {e}")
            return False

        # Wait before polling again
        time.sleep(interval)

    print(f"ERROR: Workflow {workflow_name} did not complete within {timeout} seconds.")
    return False

def delete_resources(namespace, workflow_name, workflow_template_name):
    """Delete the workflow, workflow template, and associated pods."""
    try:
        # Delete the workflow and workflow template
        for resource, name in [("workflow", workflow_name), ("workflowtemplate", workflow_template_name)]:
            print(f"INFO: Deleting {resource} {name}...")
            subprocess.run(
                ["kubectl", "delete", resource, name, "-n", namespace],
                check=True
            )
            print(f"INFO: {resource.capitalize()} {name} deleted successfully.")
        
        # Find pods owned by the workflow
        print(f"INFO: Finding pods owned by workflow {workflow_name}...")
        pods_json = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            check=True, stdout=subprocess.PIPE, universal_newlines=True
        ).stdout
        pod_names = [
            pod["metadata"]["name"]
            for pod in json.loads(pods_json).get("items", [])
            if any(owner.get("name") == workflow_name for owner in pod.get("metadata", {}).get("ownerReferences", []))
        ]

        # Delete the found pods
        for pod_name in pod_names:
            print(f"INFO: Deleting pod {pod_name}...")
            subprocess.run(
                ["kubectl", "delete", "pod", pod_name, "-n", namespace],
                check=True
            )
            print(f"INFO: Pod {pod_name} deleted successfully.")
        
        if not pod_names:
            print(f"INFO: No pods found for workflow {workflow_name}.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to delete resources: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse pod list: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py <workflow_template_file_path> <workflow_file_path> <new_image_version>")
        sys.exit(1)
    
    workflow_template_file = sys.argv[1]
    workflow_file = sys.argv[2]
    new_version= sys.argv[3]
    # Load kubeconfig (adjust if running inside a cluster)
    config.load_kube_config()
    
    with open(workflow_template_file, 'r') as stream:
        workflow_template_str = stream.read()

    # Update the image version in the WorkflowTemplate
    if "update_cpc_workflow.yaml" in workflow_file:
        old_image_prefix = "cray-product-catalog-update:"
        old_version = "2.0.1"  # Existing version for cray-product-catalog-update
    elif "iuf_base_workflow.yaml" in workflow_file:
        old_image_prefix = "iuf:"
        old_version = "v0.1.12"  # Existing version for iuf
    else:
        print(f"ERROR: Unknown workflow file: {workflow_file}")
        sys.exit(1)

    # Update the image version in the WorkflowTemplate
    updated_workflow_template_str = update_image_version_in_template(workflow_template_str, old_image_prefix, old_version, new_version)

    # Load the updated string back into a YAML dict
    workflow_template_dict = yaml.safe_load(updated_workflow_template_str)

    # Load the Workflow YAML file
    with open(workflow_file, 'r') as stream:
        workflow_dict = yaml.safe_load(stream)

    # Kubernetes API instance
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
            body=workflow_template_dict
        )
        print(f"INFO: WorkflowTemplate created.")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print("INFO: WorkflowTemplate already exists, updating it...")
            api_response = api_instance.patch_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=workflow_template_dict['metadata']['name'],
                body=workflow_template_dict
            )
            print(f"INFO: WorkflowTemplate updated.")
        else:
            print(f"ERROR: Exception when creating WorkflowTemplate: {e}")
            sys.exit(1)

    # Submit the workflow
    try:
        api_response = api_instance.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural="workflows",
            body=workflow_dict
        )
        print("INFO: Workflow submitted. Status:", api_response)
    except client.exceptions.ApiException as e:
        print(f"ERROR: Exception when submitting workflow: {e}")
        sys.exit(1)
    workflow_name = api_response.get("metadata", {}).get("name")

    if not workflow_name:
        print("ERROR: Workflow name not found in the response.")
        sys.exit(1)
    
    workflow_template_name = workflow_template_dict['metadata']['name']

    print(f"INFO: Waiting for workflow {workflow_name} to succeed...")
    # Wait for the workflow to succeed
    time.sleep(15)
    workflow_status = wait_for_workflow_to_succeed( namespace, workflow_name)
    
    if workflow_status:
        print("INFO: Workflow completed successfully, proceeding to next step.")
    else:
        print("ERROR: Workflow did not succeed, aborting.")
        sys.exit(1)
    
    delete_resources(namespace,workflow_name,workflow_template_name)

if __name__ == "__main__":
    main()
