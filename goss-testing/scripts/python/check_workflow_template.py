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
This script checks workflow templates.
"""

import sys
import time
from kubernetes import client, config
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
        else:
            print(f"INFO: Main container still running in pod {pod_name}.")

def update_image_version_in_template(workflow_template_str,old_image_prefix,old_version, new_version):
    # Find the image string and replace its version
    updated_workflow_template_str = workflow_template_str.replace(
        old_image_prefix + old_version, 
        old_image_prefix + new_version
    )
    return updated_workflow_template_str

def main(workflow_template_file, workflow_file,new_version):
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
        print(f"INFO: WorkflowTemplate created. Status: {api_response}")
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
            print(f"INFO: WorkflowTemplate updated. Status: {api_response}")
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

    # Check if the workflow template is iuf-base-template and handle pod cleanup
    if workflow_template_dict['metadata']['name'] == "iuf-base-template":
        workflow_name = workflow_dict['metadata']['name']
        time.sleep(10)  # Wait for the pod to be created
        check_and_kill_pod(workflow_name, namespace)

# Entry point
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <workflow_template_file_path> <workflow_file_path> <new_image_version>")
        sys.exit(1)

    workflow_template_file = sys.argv[1]
    workflow_file = sys.argv[2]
    new_image_version= sys.argv[3]

    main(workflow_template_file, workflow_file,new_image_version)
