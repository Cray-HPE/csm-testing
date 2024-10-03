import sys
from kubernetes import client, config
import yaml

def main(workflow_template_file, workflow_file):
    # Load kubeconfig (adjust if running inside a cluster)
    config.load_kube_config()

    # Load the WorkflowTemplate YAML file
    with open(workflow_template_file, 'r') as stream:
        workflow_template_dict = yaml.safe_load(stream)

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
        print("WorkflowTemplate created. Status:", api_response)
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print("WorkflowTemplate already exists, updating it...")
            api_response = api_instance.patch_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=workflow_template_dict['metadata']['name'],
                body=workflow_template_dict
            )
            print("WorkflowTemplate updated. Status:", api_response)
        else:
            print(f"Exception when creating WorkflowTemplate: {e}")

    # Submit the workflow
    try:
        api_response = api_instance.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural="workflows",
            body=workflow_dict
        )
        print("Workflow submitted. Status:", api_response)
    except client.exceptions.ApiException as e:
        print(f"Exception when submitting workflow: {e}")

# Entry point
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <workflow_template_file_path> <workflow_file_path>")
        sys.exit(1)

    workflow_template_file = sys.argv[1]
    workflow_file = sys.argv[2]

    main(workflow_template_file, workflow_file)
