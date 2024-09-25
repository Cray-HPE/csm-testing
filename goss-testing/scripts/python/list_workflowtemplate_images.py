from kubernetes import client, config
import yaml

def load_k8s_config():
    """Load Kubernetes config from default location."""
    try:
        config.load_kube_config()
        print("Kubernetes config loaded successfully.")
    except Exception as e:
        print(f"Error loading Kubernetes config: {e}")
        exit(1)

def get_workflow_templates(namespace='argo'):
    """Fetch all WorkflowTemplates in the given namespace."""
    try:
        api_instance = client.CustomObjectsApi()
        workflow_templates = api_instance.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="workflowtemplates"
        )
        return workflow_templates.get('items', [])
    except client.exceptions.ApiException as e:
        print(f"Exception when fetching workflow templates: {e}")
        exit(1)

def extract_images_from_template(template):
    """Extract all images used in a WorkflowTemplate, including script-based images."""
    images = set()
    spec = template.get("spec", {})
    templates = spec.get("templates", [])

    # Iterate through all templates
    for tmpl in templates:
        # Check for container images
        container = tmpl.get("container", {})
        image = container.get("image")
        if image:
            images.add(image)

        # Check for script images
        script = tmpl.get("script", {})
        script_image = script.get("image")
        if script_image:
            images.add(script_image)

        # Check for images in the steps field
        steps = tmpl.get("steps", [])
        for step in steps:
            for s in step:
                # Steps may refer to another template
                template_name = s.get("template")
                if template_name:
                    # Skip as we are not resolving the steps in this example
                    continue

                # Check for container or script images inside step
                container = s.get("container", {})
                step_image = container.get("image")
                if step_image:
                    images.add(step_image)

                script = s.get("script", {})
                step_script_image = script.get("image")
                if step_script_image:
                    images.add(step_script_image)

    return images

def main():
    # Load Kubernetes configuration
    load_k8s_config()

    # Fetch all WorkflowTemplates in the namespace 'argo'
    workflow_templates = get_workflow_templates(namespace='argo')

    if not workflow_templates:
        print("No WorkflowTemplates found in the 'argo' namespace.")
        exit(0)

    # Set to store all unique images
    all_images = set()

    # Loop through each template and collect images
    for template in workflow_templates:
        images = extract_images_from_template(template)
        all_images.update(images)

    # Print all unique images at the end
    if all_images:
        print("Unique Images Found:")
        for image in sorted(all_images):
            print(f"  - {image}")
    else:
        print("No images found.")

if __name__ == "__main__":
    main()
