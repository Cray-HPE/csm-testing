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
The script has common functions being used by iuf tests scripts
"""

import os
import shutil
import sys
import subprocess
import base64
from jsonschema import validate, ValidationError, SchemaError
from requests.auth import HTTPBasicAuth
import yaml
from kubernetes import client, config
from csm_testing.lib.iuf_constants import MEDIA_DIR, NAMESPACE

FOLDER_NAME = "dummy-1.0.0"


def run_command(command):  # pylint: disable=missing-function-docstring
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.decode().strip(), result.returncode
    except subprocess.CalledProcessError as err:
        print(f"ERROR: Command failed with error: {err}")
        sys.exit(1)


def media_dir_setup(tar_dir):  # pylint: disable=missing-function-docstring
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        print(f"INFO: Directory {MEDIA_DIR} created successfully.")
    except OSError as err:
        print(f"ERROR: Unable to create directory {MEDIA_DIR}: {err}")
        sys.exit(1)

    # Copying product tar file and manifest files into the media directory
    try:
        shutil.copy(f"{tar_dir}/{FOLDER_NAME}.tar.gz", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/product_vars.yaml", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/management-bootprep.yaml", MEDIA_DIR)
        print(f"INFO: Files copied successfully to {MEDIA_DIR}.")
    except IOError as err:
        print(f"ERROR: Failed while copying files: {err}")
        sys.exit(1)


def get_nexus_credentials(
    namespace="nexus", secret_name="nexus-admin-credential"
):  # pylint: disable=missing-function-docstring
    """Retrieve Nexus credentials from a Kubernetes secret."""
    # Check if the secret exists
    run_command(f"kubectl get secret -n {namespace} {secret_name}")

    # Retrieve and decode credentials
    username_base64, _ = run_command(
        f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.username}}}}"
    )
    password_base64, _ = run_command(
        f"kubectl get secret -n {namespace} {secret_name} --template={{{{.data.password}}}}"
    )

    if username_base64 and password_base64:
        username = base64.b64decode(username_base64).decode()
        password = base64.b64decode(password_base64).decode()
        return username, password
    sys.exit("ERROR: Failed to retrieve credentials")


def get_ca_certificates(namespace, cert_configmap_name):
    """Retrieve CA certificates from the specified ConfigMap"""
    config.load_kube_config()

    v1 = client.CoreV1Api()  # pylint: disable=invalid-name
    configmap = v1.read_namespaced_config_map(cert_configmap_name, namespace)

    ca_cert_path = "/tmp/ca.crt"
    with open(ca_cert_path, "w", encoding="utf-8") as file:
        file.write(configmap.data["certificate_authority.crt"])

    return ca_cert_path


def vcs_auth():  # pylint: disable=missing-function-docstring
    user_cmd = (
        "kubectl get secret -n services vcs-user-credentials "
        "--template={{.data.vcs_username}} | base64 --decode"
    )

    pass_cmd = (
        "kubectl get secret -n services vcs-user-credentials "
        "--template={{.data.vcs_password}} | base64 --decode"
    )
    vcs_user, _ = run_command(user_cmd)
    vcs_password, _ = run_command(pass_cmd)

    configmap_name = "cray-configmap-ca-public-key"
    gitea_base_url = "https://api-gw-service-nmn.local/vcs"
    gitea_url = f'{gitea_base_url.rstrip("/")}/api/v1'
    org = "cray"
    repo_name = "dummy-config-management"

    ca_cert_path = get_ca_certificates(NAMESPACE, configmap_name)
    auth = HTTPBasicAuth(vcs_user, vcs_password)
    dummy_repo_url = f"{gitea_url}/repos/{org}/{repo_name}"

    return dummy_repo_url, auth, ca_cert_path


# Custom exception for IUF Product Manifest validation errors
class ManifestValidationError(Exception):
    """Custom exception for validation errors."""


def load_yaml(file_path):
    """Load a YAML file and return the parsed data."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except yaml.YAMLError as err:
        raise ManifestValidationError(
            f"ERROR: Error loading YAML file {file_path}: {err}"
        ) from err
    except FileNotFoundError as err:
        raise ManifestValidationError(
            f"ERROR: File not found: {file_path}: {err}"
        ) from err
    except Exception as err:
        raise ManifestValidationError(
            f"ERROR: Error reading file {file_path}: {err}"
        ) from err


def validate_instance(instance, schema):
    """Validate the instance data against the schema."""
    try:
        validate(instance=instance, schema=schema)
    except ValidationError as err:
        raise ManifestValidationError(f"ERROR: Validation failed: {err}") from err
    except SchemaError as err:
        raise ManifestValidationError(f"ERROR: Schema error: {err}") from err
