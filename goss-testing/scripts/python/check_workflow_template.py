from kubernetes import client, config
import yaml

# Load kubeconfig (adjust if running inside a cluster)
config.load_kube_config()

# Hardcode the values for the parameters
product_name = "my-hardcoded-product"
product_version = "1.0.0"
yaml_content = "hardcoded-yaml-content"

# Define the WorkflowTemplate with hardcoded values
workflow_template_yaml = f"""
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: update-product-catalog-template
  namespace: auto
  labels:
    version: "4.0.1"
spec:
  entrypoint: catalog-update
  templates:
  - name: catalog-update
    inputs:
      parameters:
        - name: product-catalog-configmap-name
          value: "cray-product-catalog-dummy"
        - name: product-catalog-configmap-namespace
          value: "auto"
        - name: product-name
          value: "{product_name}"
        - name: product-version
          value: "{product_version}"
        - name: yaml-content
          value: "{yaml_content}"
    container:
      image: artifactory.algol60.net/csm-docker/stable/cray-product-catalog-update:2.3.1
      command: [catalog_update]
      env:
        - name: PRODUCT
          value: "{{inputs.parameters.product-name}}"
        - name: PRODUCT_VERSION
          value: "{{inputs.parameters.product-version}}"
        - name: CONFIG_MAP
          value: "{{inputs.parameters.product-catalog-configmap-name}}"
        - name: CONFIG_MAP_NAMESPACE
          value: "{{inputs.parameters.product-catalog-configmap-namespace}}"
        - name: YAML_CONTENT_STRING
          value: "{{inputs.parameters.yaml-content}}"
        - name: VALIDATE_SCHEMA
          value: "true"
        - name: REMOVE_ACTIVE_FIELD
          value: "true"
"""

# Convert the YAML to a dictionary
workflow_template_dict = yaml.safe_load(workflow_template_yaml)

# Create the WorkflowTemplate in Kubernetes
api_instance = client.CustomObjectsApi()
group = "argoproj.io"
version = "v1alpha1"
namespace = "auto"
plural = "workflowtemplates"

try:
    # Create or apply the WorkflowTemplate
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
        # Update the existing WorkflowTemplate
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

# Submit a workflow from the WorkflowTemplate
workflow_submit_yaml = """
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: update-product-catalog-workflow-
  namespace: auto
spec:
  workflowTemplateRef:
    name: update-product-catalog-template
"""

# Convert the workflow submission YAML to a dictionary
workflow_submit_dict = yaml.safe_load(workflow_submit_yaml)

# Submit the workflow
try:
    api_response = api_instance.create_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural="workflows",
        body=workflow_submit_dict
    )
    print("Workflow submitted. Status:", api_response)
except client.exceptions.ApiException as e:
    print(f"Exception when submitting workflow: {e}")
