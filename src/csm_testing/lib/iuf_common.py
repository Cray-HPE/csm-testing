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

import os
import shutil
import sys
import subprocess
import base64
from jsonschema import validate, ValidationError, SchemaError
import yaml
from kubernetes import client, config
from csm_testing.lib.iuf_constants import MEDIA_DIR

FOLDER_NAME = "dummy-1.0.0"

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip(), result.returncode
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with error: {e.stderr.decode()}")
        sys.exit(1)

def media_dir_setup(tar_dir):
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        print(f"INFO: Directory {MEDIA_DIR} created successfully.")
    except OSError as e:
        print(f"ERROR: Unable to create directory {MEDIA_DIR}: {e}")
        sys.exit(1)
    
    # Copying product tar file and manifest files into the media directory
    try:
        shutil.copy(f"{tar_dir}/{FOLDER_NAME}.tar.gz", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/product_vars.yaml", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/management-bootprep.yaml", MEDIA_DIR)
        print(f"INFO: Files copied successfully to {MEDIA_DIR}.")
    except IOError as e:
        print(f"ERROR: Failed while copying files: {e}")
        sys.exit(1)

def get_nexus_credentials(namespace="nexus", secret_name="nexus-admin-credential"):
    """Retrieve Nexus credentials from a Kubernetes secret."""
    # Check if the secret exists
    run_command(f"kubectl get secret -n {namespace} {secret_name}")

    # Retrieve and decode credentials
    username_base64 = run_command(f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.username}}}}")
    password_base64 = run_command(f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.password}}}}")

    if username_base64 and password_base64:
        username = base64.b64decode(username_base64).decode()
        password = base64.b64decode(password_base64).decode()
        return username, password
    else:
        sys.exit("ERROR: Failed to retrieve credentials")

# function to get certificates for making api calls
def get_ca_certificates(namespace, cert_configmap_name):
    """ Retrieve CA certificates from the specified ConfigMap """
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config() 

    v1 = client.CoreV1Api()
    configmap = v1.read_namespaced_config_map(cert_configmap_name, namespace)

    # Save the CA certificate to a file
    ca_cert_path = '/tmp/ca.crt'
    with open(ca_cert_path, 'w') as f:
        f.write(configmap.data['certificate_authority.crt'])

    return ca_cert_path

# Custom exception for IUF Product Manifest validation errors
class ManifestValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def load_yaml(file_path):
    """Load a YAML file and return the parsed data."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as err:
        raise ManifestValidationError(f"ERROR: Error loading YAML file {file_path}: {err}")
    except FileNotFoundError as err:
        raise ManifestValidationError(f"ERROR: File not found: {file_path}")
    except Exception as err:
        raise ManifestValidationError(f"ERROR: Error reading file {file_path}: {err}")

def validate_instance(instance, schema):
    """Validate the instance data against the schema."""
    try:
        validate(instance=instance, schema=schema)
    except ValidationError as err:
        raise ManifestValidationError(f"ERROR: Validation failed: {err.message}")
    except SchemaError as err:
        raise ManifestValidationError(f"ERROR: Schema error: {err.message}")
