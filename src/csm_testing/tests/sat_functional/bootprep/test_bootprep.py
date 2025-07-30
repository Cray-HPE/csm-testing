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
Tests for functionality of the `sat bootprep` command.
"""
import base64
import re
from datetime import datetime
import functools
import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from typing import List
import unittest

import requests.exceptions
from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.kube_config import load_kube_config
import pkg_resources
from semver import VersionInfo
import yaml


logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def skip_test_if_csm_var_missing(var_names: List[str]) -> callable:
    """Decorator to skip a test if given CSM vars are unavailable"""
    def decorator(test_method):
        @functools.wraps(test_method)
        def wrapper(self, *args, **kwargs):
            missing_vars = [var_name for var_name in var_names if var_name not in self.csm_vars]
            if missing_vars:
                self.skipTest('\n'.join(
                    [f'Missing CSM vars from vars file: {", ".join(missing_vars)}.'] +
                    getattr(self, 'set_up_errors', []))
                )
            return test_method(self, *args, **kwargs)

        return wrapper

    return decorator


class BootprepRunTestCase(unittest.TestCase):
    """Base test class for `sat bootprep run` tests.

    This base class handles setting up a temporary directory into which bootprep
    input files will be copied. The `sat bootprep` command will be run with this
    temporary directory as the current working directory, which allows it to access
    the files it contains.
    """

    def tearDown(self):
        self.delete_all_cfs_configurations_matching_prefix(self.test_prefix)
        self.delete_all_ims_images_matching_prefix(self.test_prefix)
        self.delete_all_session_templates_matching_prefix(self.test_prefix)

    @classmethod
    def setUpClass(cls):
        """Create a temporary directory for bootprep input files."""
        cls.set_up_errors = []
        cls.temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

        cls.test_prefix = f'sat-bp-testing-{datetime.now().strftime("%Y-%m-%d")}'
        cls.config_name = f'{cls.test_prefix}-simple-configuration'
        cls.image_name = f'{cls.test_prefix}-simple-image'
        cls.session_template_name = f'{cls.test_prefix}-simple-session-template'

        cls.get_product_catalog_data()
        cls.get_csm_vars()

        # TODO (CRAYSAT-2007): Improve error handling
        vcs_repo_name = cls.create_vcs_repository(f'sat-vcs-goss-testing-{datetime.now().strftime("%Y-%m-%d")}')
        if vcs_repo_name != "":
            cls.vcs_repo_name = vcs_repo_name
        else:
            cls.set_up_errors.append("Unable to create the vcs repository")

        # Create the vars.yaml file in the temporary directory
        cls.vars_file_name = 'vars.yaml'
        vars_file_path = os.path.join(cls.temp_dir.name, cls.vars_file_name)
        vars_data = {
            'test': {
                'prefix': cls.test_prefix,
                'vcs_repo_name': cls.vcs_repo_name,
                'config_name': f'{cls.config_name}',
                'image_name': f'{cls.image_name}',
                'session_template_name': f'{cls.session_template_name}'
            },
            'default': {
                'system_name': 'test_system_name',
                'site_domain': 'test_site_domain'
            },
            'csm': cls.csm_vars
        }
        with open(vars_file_path, 'w', encoding='utf-8') as vars_file:
            yaml.dump(vars_data, vars_file)

        for error in cls.set_up_errors:
            logging.warning(f"{error}")

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary directory for bootprep input files."""
        cls.temp_dir.cleanup()
        if cls.delete_vcs_repository(cls.vcs_repo_name, silent=False) == "":
            cls.set_up_errors.append(f"Unable to delete the vcs repository {cls.vcs_repo_name}")

    @classmethod
    def get_product_catalog_data(cls) -> None:
        """Get the product catalog data from the cray-product-catalog configmap

        We access the ConfiMap directly using the Kubernetes API to avoid using
        the same cray_product_catalog.query module used by the sat code under test.
        """
        cls.product_catalog_data = {}
        try:
            load_kube_config()
        except ConfigException as err:
            cls.set_up_errors.append(f'Unable to get product catalog; failed to '
                                     f'load kubeconfig: {err}')
            return

        try:
            kube_api = CoreV1Api()
            # Get the data from the cray-product-catalog configmap in the services namespace
            config_map = kube_api.read_namespaced_config_map('cray-product-catalog', 'services')
            cls.product_catalog_data = config_map.data
        except ApiException as err:
            cls.set_up_errors.append(f'Unable to get product catalog; '
                                     f'failed to read configmap: {err}')
            return

    @classmethod
    def get_branch_name(cls, commit_url):

        git_repo_name = str.split(commit_url, "/")[-1]
        vcs_credentials_command = ("kubectl get secret -n services vcs-user-credentials "
                                   "-o jsonpath='{.data.vcs_password}'")

        try:

            proc = subprocess.run(shlex.split(vcs_credentials_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            vcs_creds_encoded = proc.stdout.decode()
            vcs_creds_decoded = base64.b64decode(vcs_creds_encoded).decode('utf-8')

            git_command = (f'git ls-remote --heads '
                           f'https://crayvcs:{vcs_creds_decoded}@api-gw-service-nmn.local/vcs/cray/{git_repo_name}')

            proc = subprocess.run(shlex.split(git_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)

            branches_unprocessed = proc.stdout.decode().splitlines()
            branches = [line.split("/")[-1] for line in branches_unprocessed]

            if "main" in branches:
                return "main"
            elif "master" in branches:
                return "master"
            else:
                return branches[0]

        except subprocess.CalledProcessError as err:
            cls.set_up_errors.append(f'Failed to get branch names for {git_repo_name} '
                                     f'created by test: {err.stderr} defaulting to main branch')
            return "main"

    @classmethod
    def populate_vcs_repository(cls, repo_name: str):
        """Push test files to a vcs repository for testing

        repo_name: the name of the vcs repo that has been created

        vcs_password: the vcs password from the system
        """
        url = f"https://{cls.vcs_username}:{cls.vcs_password}@api-gw-service-nmn.local/vcs/cray/{repo_name}.git"

        vcs_tmp_path = os.path.join(cls.temp_dir.name, repo_name)

        git_commands = [
            "git init",
            "git branch -m main",
            "git add test.yml",
            "git add test-fail.yml",
            "git commit -am \"Add test playbooks\"",
            f"git remote add origin {url}",
            "git push -u origin main"
        ]
        try:
            os.makedirs(vcs_tmp_path, exist_ok=True)
            cls.copy_to_tmp_dir("test.yml", repo_name)
            cls.copy_to_tmp_dir("test-fail.yml", repo_name)
            for command in git_commands:
                cls.run_shell_command(command, vcs_tmp_path)
        except OSError as e:
            cls.set_up_errors.append(f"Failed with OSError {e}")
        except Exception as e:
            cls.set_up_errors.append(f"Failed to push changes to the branch with error {e}")

    @classmethod
    def get_encoded_vcs_credentials(cls):
        """Get the encoded vcs credentials from the vcs-user-credentials Kubernetes secret

        Returns:
            str: Base64 encoded credentials in the format 'username:password'

        Raises:
            subprocess.CalledProcessError: If the kubectl command fails to retrieve the secret.
            binascii.Error: If there is an issue decoding the base64 encoded credentials.
        """
        # Get the username from the Kubernetes secret
        username_command = 'kubectl get secret -n services vcs-user-credentials -o jsonpath={.data.vcs_username}'
        username_base64 = subprocess.check_output(username_command, shell=True).strip()
        username = base64.b64decode(username_base64).decode('utf-8')
        cls.vcs_username = username

        # Get the password from the Kubernetes secret
        password_command = 'kubectl get secret -n services vcs-user-credentials -o jsonpath={.data.vcs_password}'
        password_base64 = subprocess.check_output(password_command, shell=True).strip()
        password = base64.b64decode(password_base64).decode('utf-8')
        cls.vcs_password = password

        # Encode credentials
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        return encoded_credentials

    @classmethod
    def create_vcs_repository(cls, repo_name) -> str:
        """ Creates a vcs repository and populates it with files to be used for testing

        Returns:
            str: the name of the created repository, or an empty string if creation failed
        """

        # Begin by deleting the vcs repo in case it was not cleaned up
        cls.delete_vcs_repository(repo_name, silent=True)

        try:
            encoded_vcs_creds = cls.get_encoded_vcs_credentials()

            url = "https://api-gw-service-nmn.local/vcs/api/v1/admin/users/cray/repos"
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Basic {encoded_vcs_creds}'
            }

            # Define the data payload
            data = {
                "name": repo_name
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            cls.populate_vcs_repository(repo_name)

        except subprocess.CalledProcessError as err:
            cls.set_up_errors.append(f'Failed to get vcs password with error: {err}')
            return ""
        except requests.exceptions.RequestException as err:
            cls.set_up_errors.append(f'Failed to make vcs api call with error: {err}')
            return ""
        except Exception as err:
            cls.set_up_errors.append(f"Failed to create vcs repo with err {err}")
            return ""

        return repo_name

    @classmethod
    def delete_vcs_repository(cls, repo_name, silent) -> str:
        """ Deletes a vcs repository

        repo_name: the name of the repo to be deleted
        silent: boolean if true method does not output error if unsuccessful
        """
        try:
            encoded_vcs_creds = cls.get_encoded_vcs_credentials()

            # run a curl command with the username and password to delete the repo
            url = f"https://api-gw-service-nmn.local/vcs/api/v1/repos/cray/{repo_name}"
            # Define the data payload
            headers = {
                'accept': 'application/json',
                'Authorization': f'Basic {encoded_vcs_creds}'
            }

            response = requests.delete(url, headers=headers)

            if response.status_code != 204:
                if not silent:
                    cls.set_up_errors.append(f"Failed to delete the repository. "
                                             f"Status code: {response.status_code}, Response: {response.text}")
                return ""

        except subprocess.CalledProcessError as err:
            cls.set_up_errors.append(f'Failed to get vcs password with error: {err}')
            return ""
        except requests.exceptions.RequestException as err:
            cls.set_up_errors.append(f'Failed to make vcs api call with error: {err}')
            return ""
        except Exception as err:
            cls.set_up_errors.append(f"Failed to delete vcs repo with err {err}")
            return ""

        return repo_name

    @classmethod
    def get_csm_vars(cls):
        """Get variables from the product catalog for the CSM product to use in the vars file."""
        cls.csm_vars = {}
        if not cls.product_catalog_data:
            return

        try:
            csm_data = yaml.safe_load(cls.product_catalog_data['csm'])
        except KeyError as err:
            cls.set_up_errors.append(f'Unable to get CSM data from '
                                     f'product catalog; missing "{err}" key')
            return

        good_csm_versions = []
        for version, data in csm_data.items():
            # Ensure that 'configuration' and 'images' keys are present, so that
            # we can find the supplied VCS commit hash and the barebones image ID
            if 'configuration' in data and 'images' in data:
                good_csm_versions.append(version)
        good_csm_versions.sort(key=VersionInfo.parse)

        if not good_csm_versions:
            cls.set_up_errors.append('Unable to get CSM data from product catalog; no versions '
                                     'with both "configuration" and "images" keys')
            return

        cls.csm_vars['version'] = latest_csm_version = good_csm_versions[-1]
        commit_url = ""

        try:
            # Use a different CSM version for the commit hash if possible
            first_csm_version = good_csm_versions[0]
            cls.csm_vars['commit_hash'] = csm_data[first_csm_version]['configuration']['commit']
            commit_url = csm_data[first_csm_version]['configuration']['clone_url']
        except KeyError as err:
            cls.set_up_errors.append(f'Unable to get commit hash from first '
                                     f'CSM version; missing "{err}" key')

        cls.csm_vars['branch_name'] = cls.get_branch_name(commit_url)

        latest_barebones_images = [image_data['id'] for image_name, image_data
                                   in csm_data[latest_csm_version]['images'].items()
                                   if 'barebones' in image_name]
        if latest_barebones_images:
            cls.csm_vars['image_id'] = latest_barebones_images[0]
        else:
            cls.set_up_errors.append('Unable to get barebones image id from latest CSM version')

    def assert_in_log_messages(self, level: str, message_substring: str, stderr: str) -> None:
        """Assert that the given substring appears in a log message prefixed with the given level.

        Args:
            level: The log level to check for the messages.
            message_substring: The expected message
            stderr: The stderr output from running the command

        Returns:
            None
        """
        messages = [line for line in stderr.splitlines() if line.startswith(level)]
        self.assertTrue(any(message_substring in message for message in messages),
                        f'No {level} log message containing "{message_substring}" found in stderr')

    @classmethod
    def run_shell_command(cls, command, path):
        """Run a shell command and return the output."""
        try:
            result = subprocess.run(command, shell=True, cwd=path, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout.decode().strip()
        except subprocess.CalledProcessError as err:
            cls.set_up_errors.append(f"When trying to run {command}\n"
                                     f"an error occurred: {err.stderr.decode()}")
            raise err

    @staticmethod
    def delete_cfs_configuration(cfs_config_name):
        """Delete a CFS configuration using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        delete_command = f'cray cfs configurations delete {cfs_config_name}'
        try:
            subprocess.run(shlex.split(delete_command), check=True)
        except subprocess.CalledProcessError as err:
            logging.warning('Failed to delete CFS configuration "%s" '
                            'created by test: %s', cfs_config_name, err.stderr)

    @staticmethod
    def delete_all_cfs_configurations_matching_prefix(cfs_config_prefix):
        """Find and delete all CFS configurations matching a prefix using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.

        Args:
            cfs_config_prefix (str): cfs configuration prefix to match
        """
        found_configurations = []
        next_id = None

        while True:
            find_command = 'cray cfs v3 configurations list'

            if next_id:
                find_command += f' --after-id {next_id}'

            try:
                proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      check=True)
                configs_json = json.loads(proc.stdout.decode())

                for config in configs_json['configurations']:
                    if config['name'].startswith(cfs_config_prefix):
                        found_configurations.append(config['name'])

                next_obj = configs_json.get('next')
                if next_obj is None:
                    break
                else:
                    next_id = next_obj.get('after_id')

            except subprocess.CalledProcessError as err:
                logging.warning('Failed to find CFS configurations with prefix "%s" '
                                'created by test: %s', cfs_config_prefix, err.stderr)
                break

        for configuration_name in found_configurations:
            BootprepRunTestCase.delete_cfs_configuration(configuration_name)

    @staticmethod
    def delete_all_ims_images_matching_prefix(ims_image_prefix):
        """Find and delete all IMS images matching a prefix using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.

        Args:
            ims_image_prefix (str): ims image prefix to match
        """
        find_command = 'cray ims images list'
        found_image_ids = []
        try:
            proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            images_json = json.loads(proc.stdout.decode())
            for image in images_json:
                if image['name'].startswith(ims_image_prefix):
                    found_image_ids.append(image['id'])

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find IMS images with prefix "%s" '
                            'created by test: %s', ims_image_prefix, err.stderr)

        for image_id in found_image_ids:
            BootprepRunTestCase.delete_ims_image(image_id)

    @staticmethod
    def delete_all_session_templates_matching_prefix(session_template_prefix):
        """Find and delete all BOS session templates matching a prefix using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.

        Args:
            session_template_prefix (str): session template prefix to match
        """
        find_command = 'cray bos v2 sessiontemplates list'
        found_templates = []
        try:
            proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            templates_json = json.loads(proc.stdout.decode())
            for template in templates_json:
                if template['name'].startswith(session_template_prefix):
                    found_templates.append(template['name'])

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find BOS session templates with prefix "%s" '
                            'created by test: %s', session_template_prefix, err.stderr)

        for template_name in found_templates:
            BootprepRunTestCase.delete_bos_session_template(template_name)


    @staticmethod
    def delete_ims_image(ims_image_id, permanent=True):
        """Delete an IMS image using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.

        Args:
            ims_image_id (str): the ID of the IMS image to delete
            permanent (bool): if True, delete from deleted images as well.
                Otherwise, only delete from images.
        """
        def delete_ims_image_helper(deleted=False):
            """Helper function to delete an IMS image or deleted IMS image."""
            delete_command = f'cray ims {"deleted" if deleted else ""} images delete {ims_image_id}'
            try:
                subprocess.run(shlex.split(delete_command), check=True)
            except subprocess.CalledProcessError as err:
                logging.warning('Failed to delete IMS %s with ID "%s": %s',
                                'deleted image' if deleted else 'image',
                                ims_image_id, err.stderr)

        if BootprepRunTestCase.image_exists(ims_image_id):
            delete_ims_image_helper(deleted=False)
        else:
            logging.info('Image with ID "%s" does not exist in IMS images, skipping deletion.',
                         ims_image_id)

        if permanent:
            if BootprepRunTestCase.deleted_image_exists(ims_image_id):
                delete_ims_image_helper(deleted=True)
            else:
                logging.info('Image with ID "%s" does not exist in IMS deleted images, skipping deletion.',
                             ims_image_id)

    @staticmethod
    def delete_bos_session_template(bos_session_template_name):
        """Delete a BOS session template using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        delete_command = f'cray bos sessiontemplates delete {bos_session_template_name}'
        try:
            subprocess.run(shlex.split(delete_command), check=True)
        except subprocess.CalledProcessError as err:
            logging.warning('Failed to delete BOS session template "%s" '
                            'created by test: {%s}', bos_session_template_name, err.stderr)

    def create_empty_ims_image(self, name):
        """Create an empty IMS image. Useful for faster skip/overwrite testing.

        This relies on the cray CLI being configured and authenticated on the system.
        If the image can't be created, it calls `self.fail` to fail the test.

        Args:
            name (str): the name of the image to create

        Returns:
            dict: the created image data

        Raises:
            AssertionError: if the image creation fails, or we can't parse the JSON
                in the response from IMS
        """
        create_command = f'cray ims images create --name {name}'
        try:
            output = subprocess.check_output(shlex.split(create_command)).decode('utf-8')
            return json.loads(output)
        except subprocess.CalledProcessError as err:
            self.fail(f'Failed to create empty IMS image "{name}" required by test: {err.stderr}')
        except json.JSONDecodeError as err:
            self.fail(f'Failed to parse JSON output from image creation command: {err}')

    @staticmethod
    def configuration_exists(name):
        """Check if the given CFS configuration exists in the system.

        Args:
            name (str): the name of the CFS configuration

        Returns:
            bool: True if the configuration exists, False otherwise.
        """
        command = f'cray cfs v3 configurations describe {name} --format json'
        process = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0 and "not found" in process.stderr.decode().lower():
            return False
        return True

    @staticmethod
    def _image_exists_helper(image_id, deleted):
        """Helper function to check if an image or deleted image exists in IMS.

        Args:
            image_id (str): the ID of the image in IMS
            deleted (bool): if True, check the /deleted/images API endpoint
                to see if the image has been deleted but not permanently removed.
                Otherwise, only check the /images API endpoint
        """
        command = f'cray ims {"deleted" if deleted else ""} images describe {image_id} --format json'
        process = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0 and "not found" in process.stderr.decode().lower():
            return False
        return True

    @staticmethod
    def deleted_image_exists(image_id):
        """Check if the given image exists in the deleted images in IMS.

        That is, check if the image exists under the /deleted/images endpoint
        in the IMS API.

        Args:
            image_id (str): the ID of the image in IMS

        Returns:
            bool: True if the deleted image exists, False otherwise.
        """
        return BootprepRunTestCase._image_exists_helper(image_id, deleted=True)

    @staticmethod
    def image_exists(image_id, check_deleted=False):
        """Check if the given image exists in IMS.

        Args:
            image_id (str): the ID of the image in IMS
            check_deleted (bool): if True, also check the /deleted/images API endpoint
                to see if the image has been deleted but not permanently removed.

        Returns:
            bool: True if the image exists, False otherwise.
        """
        return (
            BootprepRunTestCase._image_exists_helper(image_id, deleted=False) or
            (check_deleted and BootprepRunTestCase.deleted_image_exists(image_id))
        )

    @staticmethod
    def session_template_exists(name):
        """Check if the given BOS session template exists in the system.

        Args:
            name (str): the name of the BOS session template

        Returns:
            bool: True if the session template exists, False otherwise.
        """
        command = f'cray bos v2 sessiontemplates describe {name} --format json'
        process = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0 and "not found" in process.stderr.decode().lower():
            return False
        return True

    def run_bootprep(self, bootprep_file: str, bootprep_opts: str = None,
                     check: bool = True) -> subprocess.CompletedProcess:
        """Run the `sat bootprep` command with the given arguments.

        This handles copying the bootprep input file into the temporary directory
        and running the command with that directory as the current working directory.

        Args:
            bootprep_file: The path to the bootprep input file to use. This file
                will first be copied into the temporary directory created in the
                setUpClass method.
            bootprep_opts: The options to pass to the `sat bootprep run` command.
            check: Whether to raise a subprocess.CalledProcessError if the command fails.

        Returns:
            The subprocess.CompletedProcess object.

        Raises:
            subprocess.CalledProcessError: If the command fails and check is True.
        """
        bootprep_opts_str = f'--vars-file {self.vars_file_name}'
        if bootprep_opts:
            bootprep_opts_str += f' {bootprep_opts}'
        self.copy_to_tmp_dir(bootprep_file, "")

        # Since the command is executed in the temporary directory containing
        # the bootprep input file, just use the relative file path
        command = f'sat bootprep run {bootprep_opts_str} {bootprep_file}'
        try:
            result = subprocess.run(shlex.split(command), cwd=self.temp_dir.name, check=check,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except KeyboardInterrupt:
            logging.error("Keyboard interrupt detected, attempting to cleanup bootprep run...")
            self.tearDown()
            raise
        except subprocess.CalledProcessError as err:
            logging.error(f"\nFailed to run command: {' '.join(err.cmd)}\n"
                          f"with error: \n{err.stderr.decode()}")
            raise

        return result

    @classmethod
    def copy_to_tmp_dir(cls, bootprep_file, dest_folder):
        """copy file from data directory to the current tmp directory

        Args:
            bootprep_file: The name of the bootprep input file to use. This file
                will first be copied into the temporary directory created in the
                setUpClass method.
            dest_folder: the destination folder created in the tmp directory or ""
            if target is the tmp directory itself
        """
        # Find the path to the given bootprep_file in the data directory
        src_bootprep_file_path = pkg_resources.resource_filename(
            'csm_testing',
            f'tests/sat_functional/bootprep/data/{bootprep_file}'
        )
        # Copy the bootprep input file into the temporary directory
        tmp_bootprep_file_path = os.path.join(cls.temp_dir.name, dest_folder, os.path.basename(bootprep_file))
        shutil.copy(src_bootprep_file_path, tmp_bootprep_file_path)


class TestBootprepCreateConfigs(BootprepRunTestCase):
    """Tests for creating CFS configurations using `sat bootprep run`"""

    def validate_cfs_config(self, config_name: str):
        """Validate that a cfs configuration has been created on the system
        """
        command = "cray cfs v3 configurations describe " + config_name

        try:
            result = subprocess.run(shlex.split(command), cwd=self.temp_dir.name,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            configuration = result.stdout.decode()

            self.assertIn("clone_url", configuration)
            self.assertIn(".git", configuration)
            self.assertIn("commit", configuration)
            self.assertIn("name", configuration)

        except subprocess.CalledProcessError as err:
            logging.error("Failed to get cfs config %s"
                          "with error: %s", config_name, err)

    def test_no_configs(self):
        """Test that a file with an empty list of configs creates no configs"""
        result = self.run_bootprep('no-configs.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual({}, report)
        self.assert_in_log_messages(
            "INFO",
            "Nothing to create in collection of CFS configurations",
            result.stderr.decode()
        )

    def test_no_layers(self):
        """Test creating a CFS configuration with no layers"""
        result = self.run_bootprep('no-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-no-layers', report['configurations'][0]['name'])

    @skip_test_if_csm_var_missing(['version', 'commit_hash'])
    def test_product_layers(self):
        """Test creating multiple CFS configurations using product-based layers"""
        result = self.run_bootprep('product-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(5, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_git_layers(self):
        """Test creating multiple CFS configurations with git-based layers"""
        result = self.run_bootprep('git-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(3, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_special_parameters(self):
        """Test creating a CFS configuration with special parameters"""
        result = self.run_bootprep('special-parameters-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-special-parameters-layers',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_additional_inventory(self):
        """Test creating CFS configurations with additional inventory"""
        result = self.run_bootprep('additional-inventory-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(2, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-additional-inventory-branch',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_missing_playbook(self):
        """Test creating a CFS configuration with a missing playbook using CFS v3 fails"""
        result = self.run_bootprep('missing-playbook-config.yaml', '--format json', check=False)

        self.assertEqual(1, result.returncode)
        decoded_stderr = result.stderr.decode()
        self.assert_in_log_messages(
            "ERROR",
            "A playbook is required when using the CFS v3 API to create configurations",
            decoded_stderr
        )
        self.assert_in_log_messages(
            "ERROR",
            "The CFS configuration at index 0 is not valid.",
            decoded_stderr
        )

    def test_image_customization(self):
        """Test creating an ims image with a configuration"""
        result = self.run_bootprep('image-customization.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(1, len(report['images']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_image_customization_fail(self):
        """Test creating a failing ims image"""
        result = self.run_bootprep('image-customization-fail.yaml', '--format json', check=False)

        self.assertEqual(1, result.returncode)
        decoded_stderr = result.stderr.decode()

        self.assert_in_log_messages(
            "ERROR",
            f"Creation of image {self.test_prefix}-simple-customized-image failed",
            decoded_stderr
        )
        self.assert_in_log_messages(
            "ERROR",
            "Creation of 1 images failed",
            decoded_stderr
        )

    def test_session_template(self):
        """Test creating a bos session template"""
        result = self.run_bootprep('ims-image-session-template.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(1, len(report['session_templates']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_configs_images_and_session_templates(self):
        """Test creating, skipping and overwriting configurations, images and session templates"""
        bootprep_options = '--format json'
        skip_options = ' '.join([f'--skip-existing-{item}' for item in ('configs', 'images', 'templates')])
        overwrite_options = ' '.join([f'--overwrite-{item}' for item in ('configs', 'images', 'templates')])

        # Speed up the tests by creating an empty IMS image to start with
        empty_image = self.create_empty_ims_image(self.image_name)
        empty_image_id = empty_image['id']
        # Create the configurations and session templates with bootprep
        result = self.run_bootprep('configs-images-and-session-templates.yaml',
                                   f'{bootprep_options} --limit configurations --limit session_templates')
        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(1, len(report['session_templates']))

        # This should skip everything, and the original items should still exist
        skip_result = self.run_bootprep('configs-images-and-session-templates.yaml',
                                        f'{bootprep_options} {skip_options}')
        skip_report = json.loads(skip_result.stdout.decode())
        self.assertNotIn('configurations', skip_report)
        self.assertNotIn('images', skip_report)
        self.assertNotIn('session_templates', skip_report)
        self.assertEqual(1, len(skip_report['skipped_configurations']))
        self.assertEqual(1, len(skip_report['skipped_images']))
        self.assertEqual(1, len(skip_report['skipped_session_templates']))
        self.assertTrue(self.configuration_exists(self.config_name))
        self.assertTrue(self.image_exists(empty_image_id, check_deleted=False))
        self.assertTrue(self.session_template_exists(self.session_template_name))

        # This should overwrite everything, and the original items should be replaced
        overwrite_result = self.run_bootprep('configs-images-and-session-templates.yaml',
                                             f'{bootprep_options} {overwrite_options}')
        overwrite_report = json.loads(overwrite_result.stdout.decode())

        self.assertTrue(self.configuration_exists(self.config_name))
        # The overwritten image is deleted, but not fully
        self.assertFalse(self.image_exists(empty_image_id, check_deleted=False))
        self.assertTrue(self.deleted_image_exists(empty_image_id))
        self.assertTrue(self.session_template_exists(self.session_template_name))
        self.assertEqual(1, len(overwrite_report['configurations']))
        self.assertEqual(1, len(overwrite_report['images']))
        self.assertEqual(1, len(overwrite_report['session_templates']))
        self.assertNotIn('skipped_configurations', overwrite_report)
        self.assertNotIn('skipped_images', overwrite_report)
        self.assertNotIn('skipped_session_templates', overwrite_report)

        for config in overwrite_report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_cfs_version(self):
        """Test running bootprep with cfs v2"""
        # Not adding test for cfs v3 since that is used by default
        bootprep_opts = '--format json --cfs-version v2'
        result = self.run_bootprep('configs-images-and-session-templates.yaml', bootprep_opts)

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(1, len(report['images']))
        self.assertEqual(1, len(report['session_templates']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_dry_run_and_save(self):
        """Test running bootprep in dry-run and saving files"""
        bootprep_opts = ' '.join([
            '--format json',
            '--dry-run',
            '--save-files',
        ])
        result = self.run_bootprep('configs-images-and-session-templates.yaml', bootprep_opts)

        self.assert_in_log_messages(
            "INFO",
            "Would create 1 CFS configuration",
            result.stderr.decode()
        )
        self.assert_in_log_messages(
            "INFO",
            "Would create 1 images",
            result.stderr.decode()
        )
        self.assert_in_log_messages(
            "INFO",
            "Would create 1 BOS session template",
            result.stderr.decode()
        )

        cfs_config_file = f'cfs-configuration-{self.config_name}.json'
        session_template_file = f'bos-session-template-{self.session_template_name}.json'

        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir.name, cfs_config_file)))
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir.name, session_template_file)))

    def test_limit_option(self):
        """Test limit option when creating items"""
        overwrite_options = ' '.join([f'--overwrite-{item}' for item in ('configs', 'images', 'templates')])
        base_bootprep_opts = '--format json'

        limit_configs_result = self.run_bootprep(
            'configs-images-and-session-templates.yaml',
            f'{base_bootprep_opts} --limit configurations'
        )
        limit_images_result = self.run_bootprep(
            'configs-images-and-session-templates.yaml',
            f'{base_bootprep_opts} --limit images'
        )
        limit_session_templates_result = self.run_bootprep(
            'configs-images-and-session-templates.yaml',
            f'{base_bootprep_opts} --limit session_templates'
        )
        # Have to specify overwrite options since the configurations and session templates exist
        limit_two_result = self.run_bootprep(
            'configs-images-and-session-templates.yaml',
            f'{base_bootprep_opts} {overwrite_options} --limit configurations --limit session_templates'
        )

        configs_report = json.loads(limit_configs_result.stdout.decode())
        self.assertEqual(1, len(configs_report['configurations']))
        self.assertNotIn('images', configs_report)
        self.assertNotIn('session_templates', configs_report)

        for config in configs_report['configurations']:
            self.validate_cfs_config(config['name'])

        images_report = json.loads(limit_images_result.stdout.decode())
        self.assertEqual(1, len(images_report['images']))
        self.assertNotIn('configurations', images_report)
        self.assertNotIn('session_templates', images_report)

        session_templates_report = json.loads(limit_session_templates_result.stdout.decode())
        self.assertEqual(1, len(session_templates_report['session_templates']))
        self.assertNotIn('images', session_templates_report)
        self.assertNotIn('configurations', session_templates_report)

        limit_two_report = json.loads(limit_two_result.stdout.decode())
        self.assertEqual(1, len(limit_two_report['configurations']))
        self.assertEqual(1, len(limit_two_report['session_templates']))
        self.assertNotIn('images', limit_two_report)

        for config in limit_two_report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_if_exists_configs(self):
        """Test the 'if_exists' property for CFS configurations"""
        skipped_name = f'{self.config_name}-skip'
        overwritten_name = f'{self.config_name}-overwrite'
        bootprep_options = '--format json'

        # First run should create both configurations because they don't exist yet
        first_result = self.run_bootprep('skip-overwrite-configs.yaml', bootprep_options)
        first_report = json.loads(first_result.stdout.decode())
        created_config_names = [config['name'] for config in first_report['configurations']]
        self.assertEqual([skipped_name, overwritten_name],
                         created_config_names)

        # Second run should skip the configuration that specifies "if_exists: skip" and overwrite
        # the configuration that specifies "if_exists: overwrite"
        second_result = self.run_bootprep('skip-overwrite-configs.yaml', bootprep_options)
        second_report = json.loads(second_result.stdout.decode())
        created_config_names = [config['name'] for config in second_report['configurations']]
        skipped_config_names = [config['name'] for config in second_report['skipped_configurations']]
        self.assertEqual([overwritten_name], created_config_names)
        self.assertEqual([skipped_name], skipped_config_names)

    def test_if_exists_images(self):
        """Test the 'if_exists' property for IMS images"""
        skipped_name = f'{self.image_name}-skip'
        overwritten_name = f'{self.image_name}-overwrite'
        # Create empty images to test skip and overwrite behavior in bootprep
        # This is much faster than actually creating the images in bootprep.
        empty_skip_image = self.create_empty_ims_image(skipped_name)
        empty_overwrite_image = self.create_empty_ims_image(overwritten_name)

        # This should skip the image that specifies "if_exists: skip" and overwrite
        # the image that specifies "if_exists: overwrite"
        result = self.run_bootprep('skip-overwrite-images.yaml', '--format json')
        report = json.loads(result.stdout.decode())
        created_image_names = [image['name'] for image in report['images']]
        skipped_image_names = [image['name'] for image in report['skipped_images']]
        self.assertEqual([overwritten_name], created_image_names)
        self.assertEqual([skipped_name], skipped_image_names)

        # The original empty skip image should still exist
        self.assertTrue(self.image_exists(empty_skip_image['id'], check_deleted=False))
        # The original empty overwrite image should be deleted, but it's still present in deleted images
        self.assertFalse(self.image_exists(empty_overwrite_image['id'], check_deleted=False))
        self.assertTrue(self.deleted_image_exists(empty_overwrite_image['id']))

    def test_if_exists_session_templates(self):
        """Test the 'if_exists' property for BOS session templates"""
        skipped_name = f'{self.session_template_name}-skip'
        overwritten_name = f'{self.session_template_name}-overwrite'

        bootprep_options = '--format json'

        # First run should create both session templates because they don't exist yet
        first_result = self.run_bootprep('skip-overwrite-session-templates.yaml', bootprep_options)
        first_report = json.loads(first_result.stdout.decode())
        created_session_template_names = [template['name'] for template in first_report['session_templates']]
        self.assertEqual([skipped_name, overwritten_name],
                         created_session_template_names)

        # Second run should skip the session template that specifies "if_exists: skip" and overwrite
        # the session template that specifies "if_exists: overwrite"
        second_result = self.run_bootprep('skip-overwrite-session-templates.yaml', bootprep_options)
        second_report = json.loads(second_result.stdout.decode())
        created_session_template_names = [template['name'] for template in second_report['session_templates']]
        skipped_session_template_names = [template['name'] for template in second_report['skipped_session_templates']]
        self.assertEqual([overwritten_name], created_session_template_names)
        self.assertEqual([skipped_name], skipped_session_template_names)


if __name__ == '__main__':
    unittest.main()
