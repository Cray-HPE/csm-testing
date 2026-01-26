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
import binascii
import functools
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import List
from datetime import datetime
import unittest

import requests
import requests.exceptions
from kubernetes.client import CoreV1Api
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from kubernetes.config.kube_config import load_kube_config
import pkg_resources
from semver import VersionInfo
import yaml

from csm_testing.tests.sat_functional.util import SATTestCase

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


def skip_test_if_csm_var_missing(var_names: List[str]) -> callable:
    """Decorator to skip a test if given CSM vars are unavailable"""
    def decorator(test_method):
        @functools.wraps(test_method)
        def wrapper(self, *args, **kwargs):
            missing_vars = [var_name for var_name in var_names if var_name not in self.csm_vars]
            if missing_vars:
                missing_vars_str = ', '.join(f'csm.{var_name}' for var_name in missing_vars)
                self.skipTest(f'Unable to get values for variables: {missing_vars_str}')
            return test_method(self, *args, **kwargs)

        return wrapper

    return decorator


def skip_test_if_sle_products_missing(test_method):
    """Decorator to skip a test if required SLE products for barebones recipe builds are unavailable"""
    @functools.wraps(test_method)
    def wrapper(self, *args, **kwargs):
        if not self.sle_products_available:
            self.skipTest('Required SLE products (sle-os-products-15-sp6-x86_64, sle-os-updates-15-sp6-x86_64) '
                         'are not installed on the system. These are required for building images from the '
                         'barebones recipe.')
        return test_method(self, *args, **kwargs)
    return wrapper


class BootprepTestCase(SATTestCase):
    """Base test class for `sat bootprep run` tests.

    This base class provides comprehensive setup and teardown for testing the
    `sat bootprep run` command. It automatically does the following:

    - Creates a temporary directory for bootprep input files. It runs bootprep with
      this directory as the current working directory.
    - Generates a unique test prefix based on the test class name for resource naming
    - Sets up a VCS repository with simple playbooks
    - Creates a vars.yaml file with test configuration and CSM product catalog data
    - Provides cleanup of CFS configurations, IMS images, IMS jobs, BOS session templates,
      and all other resource created during tests

    Test classes that test `sat bootprep run` should inherit from this class. The unique
    test prefix can be used in the names of CFS configurations, IMS images, and BOS session
    templates to ensure that multiple test classes can run concurrently without conflicts.

    Key attributes available to subclasses:
    - test_prefix: Unique identifier for naming test resources (e.g., "sat-bp-test-a1b2c3d4")
    - temp_dir: Temporary directory in which bootprep commands are run
    - config_name, image_name, session_template_name: Pre-formatted resource names
    - vcs_repo_name: VCS repository for customization tests
    - csm_vars: CSM product catalog data for use in bootprep files
    """

    # Default to using CFS v3 for everything. Subclasses can override this.
    cfs_version = 'v3'

    # Whether this test class needs a VCS repository set up. Subclasses can override this.
    needs_vcs_repo = False
    needs_cfs_source = False

    @classmethod
    def setUpClass(cls):
        """Create a temporary directory for bootprep input files."""
        cls.set_up_errors = []
        cls.temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        cls.vcs_repo_name = None  # Initialize to None to handle cases where VCS repo isn't needed
        cls.cfs_source_name = None  # Initialize to None to handle cases where cfs source isn't needed

        # Use the unique id based on the class name to create a unique test prefix
        if cls.cfs_version != 'v3':
            cls.test_prefix = f'sat-test-cfs-{cls.cfs_version}-{cls.unique_id}'
        else:
            cls.test_prefix = f'sat-test-{cls.unique_id}'
        logging.info(f'Test class {cls.__name__} using resource prefix: {cls.test_prefix}')

        cls.config_name = f'{cls.test_prefix}-simple-configuration'
        cls.image_name = f'{cls.test_prefix}-simple-image'
        cls.session_template_name = f'{cls.test_prefix}-simple-session-template'

        cls.get_product_catalog_data()
        cls.get_csm_vars()
        # This method depends on data saved by get_csm_vars
        cls.check_sle_products_availability()

        vars_data = {
            'test': {
                'prefix': cls.test_prefix,
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

        if cls.needs_cfs_source and not cls.needs_vcs_repo:
            cls.needs_vcs_repo = True

        if cls.needs_vcs_repo:
            cls.vcs_repo_name = cls.test_prefix
            # Let RuntimeError bubble up if VCS repo creation fails
            cls.create_vcs_repository(cls.vcs_repo_name)
            vars_data['test']['vcs_repo_name'] = cls.vcs_repo_name

        if cls.needs_cfs_source:
            cls.cfs_source_name = f"{cls.test_prefix}-source"
            # Let RuntimeError bubble up if cfs source creation fails
            cls.create_cfs_source(cls.cfs_source_name)
            vars_data['test']['cfs_source_name'] = cls.cfs_source_name

        # Create the vars.yaml file in the temporary directory
        cls.vars_file_name = 'vars.yaml'
        vars_file_path = os.path.join(cls.temp_dir.name, cls.vars_file_name)
        with open(vars_file_path, 'w', encoding='utf-8') as vars_file:
            yaml.dump(vars_data, vars_file)

        for error in cls.set_up_errors:
            logging.warning(f"{error}")

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary directory for bootprep input files."""
        cls.temp_dir.cleanup()
        # Only try to delete VCS repo if one was created
        if cls.vcs_repo_name is not None:
            try:
                cls.delete_vcs_repository(cls.vcs_repo_name)
            except RuntimeError as err:
                logging.warning(f'Failed to delete VCS repository {cls.vcs_repo_name}: {err}')
        if cls.cfs_source_name is not None:
            try:
                cls.delete_cfs_source()
            except RuntimeError as err:
                logging.warning(f'Failed to delete cfs source {cls.cfs_source_name}: {err}')

    def setUp(self):
        # Ensure resources from past tests are deleted to start with a clean slate
        super().setUp()
        type(self).delete_matching_resources()

    def tearDown(self):
        type(self).delete_matching_resources()
        super().tearDown()

    @classmethod
    def delete_matching_resources(cls):
        cls.delete_all_cfs_configurations_matching_prefix()
        cls.delete_all_ims_images_matching_prefix()
        cls.delete_all_session_templates_matching_prefix()
        cls.delete_all_ims_jobs_matching_prefix()

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
    def get_branch_name(cls, clone_url):

        git_repo_name = str.split(clone_url, "/")[-1]
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

        Args:
            repo_name: the name of the vcs repo that has been created

        Raises:
            RuntimeError: if there is an error during repository population
        """
        url = f"https://{cls.vcs_username}:{cls.vcs_password}@api-gw-service-nmn.local/vcs/cray/{repo_name}.git"

        vcs_tmp_path = os.path.join(cls.temp_dir.name, repo_name)

        try:
            os.makedirs(vcs_tmp_path, exist_ok=True)
            cls.copy_to_tmp_dir("test.yml", repo_name)
            cls.copy_to_tmp_dir("test-fail.yml", repo_name)
        except OSError as err:
            raise RuntimeError(f'Failed to create temporary directory {vcs_tmp_path} with error: {err}')

        git_commands = [
            "git init",
            "git branch -m main",
            "git add test.yml",
            "git add test-fail.yml",
            "git commit -am \"Add test playbooks\"",
            f"git remote add origin {url}",
            "git push -u origin main"
        ]
        command = "" # Addresses PyCharm warning
        try:
            for command in git_commands:
                cls.run_shell_command(command, vcs_tmp_path)
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f'Failed to execute "{command}" with error: {err}')

    @classmethod
    def get_encoded_vcs_credentials(cls):
        """Get the encoded vcs credentials from the vcs-user-credentials Kubernetes secret

        Returns:
            str: Base64 encoded credentials in the format 'username:password'

        Raises:
            RuntimeError: If a "kubectl get secret" command fails or there is
                an issue decoding the base64 encoded credentials
        """
        try:
            # Get the username from the Kubernetes secret
            username_command = 'kubectl get secret -n services vcs-user-credentials -o jsonpath={.data.vcs_username}'
            username_base64 = subprocess.check_output(username_command, shell=True).strip()
            username = base64.b64decode(username_base64).decode('utf-8')
            cls.vcs_username = username
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f'Failed to get vcs username with error: {err}')
        except binascii.Error as err:
            raise RuntimeError(f'Failed to decode base64 encoded vcs username: {err}')

        try:
            # Get the password from the Kubernetes secret
            password_command = 'kubectl get secret -n services vcs-user-credentials -o jsonpath={.data.vcs_password}'
            password_base64 = subprocess.check_output(password_command, shell=True).strip()
            password = base64.b64decode(password_base64).decode('utf-8')
            cls.vcs_password = password
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f'Failed to get vcs password with error: {err}')
        except binascii.Error as err:
            raise RuntimeError(f'Failed to decode base64 encoded vcs password: {err}')

        # Encode credentials
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        return encoded_credentials

    @classmethod
    def create_vcs_repository(cls, repo_name) -> None:
        """ Creates a vcs repository and populates it with files to be used for testing

        Raises:
            RuntimeError: if there is an error during repository creation or population
        """
        # Begin by deleting the vcs repo in case it was not cleaned up
        cls.delete_vcs_repository(repo_name)
        try:
            encoded_vcs_creds = cls.get_encoded_vcs_credentials()
            url = "https://api-gw-service-nmn.local/vcs/api/v1/admin/users/cray/repos"
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Basic {encoded_vcs_creds}'
            }
            response = requests.post(url, headers=headers, json={"name": repo_name})
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            raise RuntimeError(f'Failed to make vcs api call with error: {err}')

        # This raises RuntimeError if there is an error during population
        cls.populate_vcs_repository(repo_name)

    @classmethod
    def delete_vcs_repository(cls, repo_name) -> None:
        """Deletes a vcs repository.

        If the repo already does not exist, it logs an info message and returns.

        Args:
            repo_name: the name of the repo to be deleted

        Raises:
            RuntimeError: if there is an error (other than 404) during repository deletion
        """
        # This raises RuntimeError if there is an error getting the credentials
        encoded_vcs_creds = cls.get_encoded_vcs_credentials()
        try:
            # Make a DELETE request to the VCS API to delete the repository
            url = f"https://api-gw-service-nmn.local/vcs/api/v1/repos/cray/{repo_name}"
            # Define the data payload
            headers = {
                'accept': 'application/json',
                'Authorization': f'Basic {encoded_vcs_creds}'
            }

            response = requests.delete(url, headers=headers)

            if not response.ok:
                if response.status_code == 404:
                    logging.info(f"Repository {repo_name} does not exist, nothing to delete")
                else:
                    raise RuntimeError(f"Failed to delete VCS repository {repo_name}. "
                                       f"Status code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.RequestException as err:
            raise RuntimeError(f'Failed to make vcs api call with error: {err}')

    @classmethod
    def create_cfs_source(cls, source_name):
        """Creates a cfs source.

        Args
            source_name: name of the cfs source
        Raises:
            RuntimeError: if the source cannot be created
        """
        vcs_url = f"https://api-gw-service-nmn.local/vcs/cray/{cls.vcs_repo_name}.git"
        command = (f"cray cfs v3 sources create "
                   f"--name {source_name} "
                   f"--clone-url {vcs_url} "
                   f"--credentials-username {cls.vcs_username} "
                   f"--credentials-password {cls.vcs_password}")

        try:
            subprocess.run(shlex.split(command), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f'Failed to create cfs source with error: {err}')

    @classmethod
    def delete_cfs_source(cls):
        """Deletes a cfs source.

        Raises:
            RuntimeError: if there is an error during source deletion
        """
        delete_command = f'cray cfs v3 sources delete {cls.cfs_source_name}'
        try:
            subprocess.run(shlex.split(delete_command), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            logging.warning(f'failed to run {delete_command} with error: {err}')

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
        required_keys = ('configuration', 'images', 'recipes')
        for version, data in csm_data.items():
            # Ensure that 'configuration', 'images', and 'recipes' keys are present, so
            # we can hopefully find the barebones image and recipe and the VCS repo info
            if all(key in data for key in required_keys):
                good_csm_versions.append(version)
        good_csm_versions.sort(key=VersionInfo.parse)

        if not good_csm_versions:
            cls.set_up_errors.append('Unable to get CSM data from product catalog; no versions '
                                     f'with {", ".join(required_keys)}.')
            return

        cls.csm_vars['version'] = latest_csm_version = good_csm_versions[-1]

        clone_url = ""
        try:
            # Use a different CSM version for the commit hash if possible
            first_csm_version = good_csm_versions[0]
            cls.csm_vars['commit_hash'] = csm_data[first_csm_version]['configuration']['commit']
            clone_url = csm_data[first_csm_version]['configuration']['clone_url']
        except KeyError as err:
            cls.set_up_errors.append(f'Unable to get commit hash from first '
                                     f'CSM version; missing "{err}" key')

        cls.csm_vars['branch_name'] = cls.get_branch_name(clone_url)

        # Find barebones recipe and save both ID and name
        barebones_recipe_found = False
        for recipe_name, recipe_data in csm_data[latest_csm_version]['recipes'].items():
            if 'barebones' in recipe_name and 'x86' in recipe_name:
                cls.csm_vars['recipe_id'] = recipe_data['id']
                cls.csm_vars['recipe_name'] = recipe_name
                barebones_recipe_found = True
                break

        if not barebones_recipe_found:
            cls.set_up_errors.append(f'Unable to get barebones recipe ID from latest CSM version')

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

    def assert_not_in_log_messages(self, level: str, message_substring: str, stderr: str) -> None:
        """Assert that the given substring does not appear in a log message prefixed with the given level.

        Args:
            level: The log level to check for the messages.
            message_substring: The message to look for
            stderr: The stderr output from running the command

        Returns:
            None
        """
        messages = [line for line in stderr.splitlines() if line.startswith(level)]
        self.assertFalse(any(message_substring in message for message in messages),
                         f'{level} log message containing "{message_substring}" found in stderr')

    def assert_info_messages(self, expected_present: List[str], expected_absent: List[str], stderr: str):
        """Assert that the expected present and absent info messages are in the stderr

        Args:
            expected_present: List of expected present info messages
            expected_absent: List of expected absent info messages
            stderr: The stderr output from running the command

        Returns:
            None
        """
        for message in expected_present:
            self.assert_in_log_messages("INFO", message, stderr)
        for message in expected_absent:
            self.assert_not_in_log_messages("INFO", message, stderr)

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

    @classmethod
    def delete_cfs_configuration(cls, cfs_config_name):
        """Delete a CFS configuration using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        delete_command = f'cray cfs {cls.cfs_version} configurations delete {cfs_config_name}'
        try:
            subprocess.run(shlex.split(delete_command), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            logging.warning('Failed to delete CFS configuration "%s" '
                            'created by test: %s', cfs_config_name, err.stderr)

    @classmethod
    def delete_all_cfs_configurations_matching_prefix(cls):
        """Find and delete all CFS configurations matching `cls.test_prefix` using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        found_configurations = []
        next_id = None

        try:
            if cls.cfs_version != 'v3':
                find_command = f'cray cfs {cls.cfs_version} configurations list'
                proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      check=True)
                configs_json = json.loads(proc.stdout.decode())

                found_configurations = [config['name'] for config in configs_json
                                        if config is not None and
                                        config['name'].startswith(cls.test_prefix)]
            else:
                while True:
                    find_command = f'cray cfs {cls.cfs_version} configurations list'

                    if next_id:
                        find_command += f' --after-id {next_id}'

                    proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          check=True)
                    configs_json = json.loads(proc.stdout.decode())

                    for config in configs_json['configurations']:
                        if config is not None and config['name'].startswith(cls.test_prefix):
                            found_configurations.append(config['name'])

                    next_obj = configs_json.get('next')
                    if next_obj is None:
                        break
                    else:
                        next_id = next_obj.get('after_id')

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find CFS configurations with prefix "%s" '
                            'created by test: %s', cls.test_prefix, err.stderr)

        for configuration_name in found_configurations:
            cls.delete_cfs_configuration(configuration_name)

    @classmethod
    def delete_all_ims_images_matching_prefix(cls):
        """Find and delete all IMS images matching `cls.test_prefix` using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        resource_types = ('images', 'deleted images')
        found_image_ids = []
        for resource_type in resource_types:
            find_command = f'cray ims {resource_type} list --format json'
            try:
                proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      check=True)
                images_json = json.loads(proc.stdout.decode())
                for image in images_json:
                    if image['name'].startswith(cls.test_prefix):
                        found_image_ids.append(image['id'])

            except subprocess.CalledProcessError as err:
                logging.warning('Failed to find IMS %s with prefix "%s" '
                                'created by test: %s', resource_type, cls.test_prefix, err.stderr)

        for image_id in found_image_ids:
            BootprepTestCase.delete_ims_image(image_id)

    @classmethod
    def delete_all_session_templates_matching_prefix(cls):
        """Find and delete all BOS session templates matching `cls.test_prefix` using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        find_command = 'cray bos v2 sessiontemplates list'
        found_templates = []
        try:
            proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            templates_json = json.loads(proc.stdout.decode())
            for template in templates_json:
                if template['name'].startswith(cls.test_prefix):
                    found_templates.append(template['name'])

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find BOS session templates with prefix "%s" '
                            'created by test: %s', cls.test_prefix, err.stderr)

        for template_name in found_templates:
            BootprepTestCase.delete_bos_session_template(template_name)

    @classmethod
    def delete_all_ims_jobs_matching_prefix(cls):
        """Find and delete all IMS jobs matching `cls.test_prefix` using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        Looks for jobs created by bootprep tests by checking if the image_root_archive_name
        starts with the test prefix (which follows the pattern 'sat-test-*').
        """
        found_job_ids = []
        try:
            # Get all IMS jobs
            find_command = 'cray ims jobs list --format json'
            proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            jobs_json = json.loads(proc.stdout.decode())

            # Filter jobs by image_root_archive_name starting with test prefix
            for job in jobs_json:
                archive_name = job.get('image_root_archive_name', '')
                if archive_name.startswith(cls.test_prefix):
                    if job.get('status') == 'error' and cls.days_since(job.get('created')) <= 7:
                        logging.warning('Skipping deletion of IMS job with ID %s, to allow for potential debugging, this job will be cleaned up by a subequent test run after 7 days.', job.get('id'))
                        continue
                    try:
                        found_job_ids.append(job['id'])
                    except KeyError:
                        logging.warning('Found IMS job with matching prefix but missing ID field: %s',
                                       json.dumps(job))

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find IMS jobs with prefix "%s" '
                            'created by test: %s', cls.test_prefix, err.stderr)
        except json.JSONDecodeError as err:
            logging.warning('Failed to parse IMS jobs response: %s', err)

        for job_id in found_job_ids:
            cls.delete_ims_job(job_id)

    @staticmethod
    def delete_ims_job(job_id):
        """Delete an IMS job using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.

        Args:
            job_id (str): the ID of the IMS job to delete
        """
        delete_command = f'cray ims jobs delete {job_id}'
        try:
            subprocess.run(shlex.split(delete_command), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.info('Successfully deleted IMS job with ID "%s"', job_id)
        except subprocess.CalledProcessError as err:
            logging.warning('Failed to delete IMS job with ID "%s": %s',
                            job_id, err.stderr.decode() if err.stderr else 'Unknown error')

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
                subprocess.run(shlex.split(delete_command), check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as err:
                logging.warning('Failed to delete IMS %s with ID "%s": %s',
                                'deleted image' if deleted else 'image',
                                ims_image_id, err.stderr)

        if BootprepTestCase.image_exists(ims_image_id):
            delete_ims_image_helper(deleted=False)
        else:
            logging.info('Image with ID "%s" does not exist in IMS images, skipping deletion.',
                         ims_image_id)

        if permanent:
            if BootprepTestCase.deleted_image_exists(ims_image_id):
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
            subprocess.run(shlex.split(delete_command), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    @classmethod
    def configuration_exists(cls, name):
        """Check if the given CFS configuration exists in the system.

        Args:
            name (str): the name of the CFS configuration

        Returns:
            bool: True if the configuration exists, False otherwise.
        """
        command = f'cray cfs {cls.cfs_version} configurations describe {name} --format json'
        process = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0 and "not found" in process.stderr.decode().lower():
            return False
        return True

    def validate_cfs_config(self, config_name: str, branch_expectations: List[bool] = None):
        """Validate that a cfs configuration has been created on the system

        Args:
            config_name: the name of the configuration to validate
            branch_expectations: Optional list of booleans indicating whether
                each layer is expected to have a 'branch' field. If None,
                no checks are done for the presence of 'branch' fields.
        """
        command = f'cray cfs {self.cfs_version} configurations describe {config_name} --format json'

        try:
            result = subprocess.run(shlex.split(command), cwd=self.temp_dir.name,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            configuration = json.loads(result.stdout.decode())

            self.assertIn('layers', configuration)
            self.assertGreater(len(configuration.get('layers')), 0)
            layers = configuration.get('layers')
            for idx, layer in enumerate(layers):
                self.assertIn('name', layer)
                self.assertIn('commit', layer)
                if self.cfs_version == 'v3':
                    self.assertTrue('clone_url' in layer or 'source' in layer,
                                    'Layer must contain either clone_url or source')
                else:
                    self.assertIn('cloneUrl', layer)

                if branch_expectations is not None and idx < len(branch_expectations):
                    if branch_expectations[idx]:
                        self.assertIn('branch', layer, f"Layer {idx} expected to have branch")
                    else:
                        self.assertNotIn('branch', layer, f"Layer {idx} expected NOT to have branch")

        except subprocess.CalledProcessError as err:
            # Fail the test if the command to get the configuration fails
            self.fail(f'Failed to get cfs config {config_name} with error: {err.stderr.decode()}')
        except json.JSONDecodeError as err:
            # Fail the test if we can't parse the JSON in the response
            self.fail(f'Failed to parse JSON output from cfs config {config_name} with error: {err}')

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
        return BootprepTestCase._image_exists_helper(image_id, deleted=True)

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
                BootprepTestCase._image_exists_helper(image_id, deleted=False) or
                (check_deleted and BootprepTestCase.deleted_image_exists(image_id))
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
                     check: bool = True, delete_ims_jobs: bool = True) -> subprocess.CompletedProcess:
        """Run the `sat bootprep` command with the given arguments.

        This handles copying the bootprep input file into the temporary directory
        and running the command with that directory as the current working directory.
        Automatically includes --delete-ims-jobs option unless explicitly disabled.

        Args:
            bootprep_file: The path to the bootprep input file to use. This file
                will first be copied into the temporary directory created in the
                setUpClass method.
            bootprep_opts: The options to pass to the `sat bootprep run` command.
            check: Whether to raise a subprocess.CalledProcessError if the command fails.
            delete_ims_jobs: Whether to include the --delete-ims-jobs option. Defaults to True
                for automated testing to ensure cleanup of IMS jobs.

        Returns:
            The subprocess.CompletedProcess object.

        Raises:
            subprocess.CalledProcessError: If the command fails and check is True.
        """
        bootprep_opts_str = f'--vars-file {self.vars_file_name} --cfs-version {self.cfs_version}'

        # Add --delete-ims-jobs option if requested
        if delete_ims_jobs:
            bootprep_opts_str += ' --delete-ims-jobs'

        if bootprep_opts:
            bootprep_opts_str += f' {bootprep_opts}'

        self.copy_to_tmp_dir(bootprep_file, "")

        # Since the command is executed in the temporary directory containing
        # the bootprep input file, just use the relative file path
        command = f'{self.sat_base_command} bootprep run {bootprep_opts_str} {bootprep_file}'
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

    @staticmethod
    def days_since(date_str):
        """Returns number of days since a given date string

        Args:
            date_str: date string in the format "2025-12-13T23:37:58.357683"

        Returns:
            int: number of days since the given date_str or 0 if unable to parse.
        """

        try:
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f').date()
            current_date = datetime.today().date()
        except ValueError as e:
            logging.warning("Unable to parse date string: %s, with error %s returning 0", date_str, e)
            return 0

        return (current_date - date).days

    @classmethod
    def check_sle_products_availability(cls):
        """Check if the required SLE products are available in the product catalog.

        Extracts the SLE version from the barebones recipe name that will be used
        in tests and uses it to construct the required SLE product names. Sets the
        sle_products_available class attribute to True if both required SLE products
        are present in the product catalog, False otherwise.
        """
        cls.sle_products_available = True

        if not cls.product_catalog_data:
            cls.sle_products_available = False
            cls.set_up_errors.append('Product catalog data not available, cannot check for SLE products')
            return

        # Extract SLE version from the barebones recipe that will be used in tests
        sle_version = cls._extract_sle_version_from_recipe()
        if not sle_version:
            cls.sle_products_available = False
            cls.set_up_errors.append('Could not extract SLE version from barebones recipe name')
            return

        required_sle_products = [
            f'sle-os-products-{sle_version}-x86_64',
            f'sle-os-updates-{sle_version}-x86_64'
        ]

        missing_products = []
        for product in required_sle_products:
            if product not in cls.product_catalog_data:
                missing_products.append(product)

        if missing_products:
            cls.sle_products_available = False
            logging.info(f'SLE products not available for barebones recipe builds: {", ".join(missing_products)}')
        else:
            logging.info(f'Required SLE products are available for barebones recipe builds (version {sle_version})')

    @classmethod
    def _extract_sle_version_from_recipe(cls):
        """Extract the SLE version from the barebones recipe name that will be used in tests.

        Uses the recipe name saved in cls.csm_vars['recipe_name'] and looks for patterns
        like 'sles15sp6' in the recipe name, converting them to the format used in
        SLE product names (e.g., '15-sp6').

        Returns:
            str: The SLE version in the format expected by SLE product names (e.g., '15-sp6'),
                 or None if no SLE version could be extracted.
        """
        if not hasattr(cls, 'csm_vars') or 'recipe_name' not in cls.csm_vars:
            return None

        recipe_name = cls.csm_vars['recipe_name']

        # Look for pattern like 'sles15sp6' in the recipe name
        match = re.search(r'sles(\d+)sp(\d+)', recipe_name, re.IGNORECASE)
        if match:
            major_version = match.group(1)
            sp_version = match.group(2)
            return f'{major_version}-sp{sp_version}'

        return None

class TestBootprepCreateConfigsCFSV3(BootprepTestCase):
    """Tests for creating CFS configurations using `sat bootprep run` using CFS v3"""

    needs_cfs_source = True

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

    @skip_test_if_csm_var_missing(['branch_name', 'commit_hash', 'version'])
    def test_product_layers(self):
        """Test creating multiple CFS configurations using product-based layers"""
        result = self.run_bootprep('product-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(5, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    @skip_test_if_csm_var_missing(['branch_name', 'commit_hash'])
    def test_git_layers(self):
        """Test creating multiple CFS configurations with git-based layers"""
        result = self.run_bootprep('git-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(3, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    @skip_test_if_csm_var_missing(['branch_name'])
    def test_no_resolve_branches(self):
        """Test that branch is present in the layer when --no-resolve-branches is used."""
        result = self.run_bootprep('resolve-branches-config.yaml', '--format json --no-resolve-branches')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))

        self.validate_cfs_config(report['configurations'][0]['name'], branch_expectations=[True])

    @skip_test_if_csm_var_missing(['branch_name'])
    def test_resolve_branches(self):
        """Test that branch is NOT present in the layer when --no-resolve-branches is NOT used."""
        result = self.run_bootprep('resolve-branches-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))

        self.validate_cfs_config(report['configurations'][0]['name'], branch_expectations=[False])

    @skip_test_if_csm_var_missing(['branch_name', 'version'])
    def test_special_parameters(self):
        """Test creating a CFS configuration with special parameters"""
        result = self.run_bootprep('special-parameters-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-special-parameters-layers',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    @skip_test_if_csm_var_missing(['branch_name', 'commit_hash', 'version'])
    def test_additional_inventory(self):
        """Test creating CFS configurations with additional inventory"""
        result = self.run_bootprep('additional-inventory-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(2, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-additional-inventory-branch',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_source_configs(self):
        """Test creating CFS configurations with source and clone url properties"""
        result = self.run_bootprep('source-configs.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    @skip_test_if_csm_var_missing(['version'])
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


class TestBootprepCreateConfigsCFSV2(TestBootprepCreateConfigsCFSV3):
    """Tests for creating CFS configurations using `sat bootprep run` with CFS v2"""
    cfs_version = 'v2'

    # All tests are inherited from TestBootprepCreateConfigsCFSV3, except for test_missing_playbook,
    # which has a different expected result with CFS v2.

    @skip_test_if_csm_var_missing(['version'])
    def test_missing_playbook(self):
        """Test creating a CFS configuration with a missing playbook using CFS v2 succeeds"""
        result = self.run_bootprep('missing-playbook-config.yaml', '--format json', check=True)

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-no-playbook',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

    def test_source_configs(self):
        """Test creating CFS configurations with source and clone url properties"""
        result = self.run_bootprep('source-configs.yaml', '--format json', check=False)

        self.assertEqual(1, result.returncode)
        decoded_stderr = result.stderr.decode()
        self.assert_in_log_messages(
            "ERROR",
            "The source property is not supported in CFS v2.",
            decoded_stderr
        )


class TestBootprepImageCustomizationCFSV3(BootprepTestCase):
    """Test for customizing an existing IMS image using CFS v3."""

    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id', 'version'])
    def test_image_customization(self):
        """Test creating an ims image with a configuration"""
        result = self.run_bootprep('image-customization.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.validate_cfs_config(report['configurations'][0]['name'])
        self.assertEqual(1, len(report['images']))
        self.assertTrue(self.image_exists(report['images'][0]['final_image_id']))


class TestBootprepImageCustomizationCFSV2(TestBootprepImageCustomizationCFSV3):
    """Test for customizing an existing IMS image using CFS v2."""
    cfs_version = 'v2'


class TestBootprepImageCustomizationFailure(BootprepTestCase):
    """Test for customizing an existing IMS image that fails"""
    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id', 'version'])
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

class TestBootprepSessionTemplates(BootprepTestCase):
    """Test for creating BOS session templates using `sat bootprep run`"""
    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id'])
    def test_session_template(self):
        """Test creating a bos session template"""
        result = self.run_bootprep('ims-image-session-template.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(1, len(report['session_templates']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])


class TestBootprepConfigsImagesAndSessionTemplates(BootprepTestCase):
    """Test for creating CFS configurations, IMS images and BOS session templates using `sat bootprep run`"""
    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id', 'version'])
    @skip_test_if_sle_products_missing
    def test_configs_images_and_session_templates(self):
        """Test creating, skipping and overwriting configurations, images and session templates"""
        bootprep_options = '--format json'
        skip_options = ' '.join([f'--skip-existing-{item}' for item in ('configs', 'images', 'templates')])
        overwrite_options = ' '.join([f'--overwrite-{item}' for item in ('configs', 'images', 'templates')])

        # Speed up the tests by creating empty IMS images to start with
        empty_barebones_image = self.create_empty_ims_image(self.image_name)
        empty_barebones_image_id = empty_barebones_image['id']
        empty_configured_image = self.create_empty_ims_image(f'{self.image_name}-configured')
        empty_configured_image_id = empty_configured_image['id']

        # Create the configurations and session templates with bootprep using another simpler bootprep
        # file that contains only a configuration named self.config_name and a session template named
        # self.session_template_name.
        result = self.run_bootprep('ims-image-session-template.yaml',
                                   f'{bootprep_options}')
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
        self.assertEqual(2, len(skip_report['skipped_images']))
        self.assertEqual(1, len(skip_report['skipped_session_templates']))
        self.assertTrue(self.configuration_exists(self.config_name))
        self.assertTrue(self.image_exists(empty_barebones_image_id, check_deleted=False))
        self.assertTrue(self.image_exists(empty_configured_image_id, check_deleted=False))
        self.assertTrue(self.session_template_exists(self.session_template_name))

        # This should overwrite everything, and the original items should be replaced
        overwrite_result = self.run_bootprep('configs-images-and-session-templates.yaml',
                                             f'{bootprep_options} {overwrite_options}')
        overwrite_report = json.loads(overwrite_result.stdout.decode())

        self.assertTrue(self.configuration_exists(self.config_name))
        # The overwritten images are deleted, but not fully
        self.assertFalse(self.image_exists(empty_barebones_image_id, check_deleted=False))
        self.assertTrue(self.deleted_image_exists(empty_barebones_image_id))
        self.assertFalse(self.image_exists(empty_configured_image_id, check_deleted=False))
        self.assertTrue(self.deleted_image_exists(empty_configured_image_id))
        self.assertTrue(self.session_template_exists(self.session_template_name))
        self.assertEqual(1, len(overwrite_report['configurations']))
        self.assertEqual(2, len(overwrite_report['images']))
        self.assertEqual(1, len(overwrite_report['session_templates']))
        self.assertNotIn('skipped_configurations', overwrite_report)
        self.assertNotIn('skipped_images', overwrite_report)
        self.assertNotIn('skipped_session_templates', overwrite_report)


class TestBootprepDryRun(BootprepTestCase):
    """Test for running `sat bootprep run` in dry-run mode"""
    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id', 'version'])
    def test_dry_run_and_save(self):
        """Test running bootprep in dry-run and saving files"""
        bootprep_opts = ' '.join([
            '--format json',
            '--dry-run',
            '--save-files',
        ])
        result = self.run_bootprep('configs-images-and-session-templates.yaml', bootprep_opts)

        self.assert_info_messages(
            [
                "Would create 1 CFS configuration",
                "Would create 2 images",
                "Would create 1 BOS session template",
            ],
            [],
            result.stderr.decode()
        )

        cfs_config_file = f'cfs-configuration-{self.config_name}.json'
        session_template_file = f'bos-session-template-{self.session_template_name}.json'

        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir.name, cfs_config_file)))
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir.name, session_template_file)))


class TestBootprepLimitOption(BootprepTestCase):
    """Test for the limit option in `sat bootprep run`"""
    needs_vcs_repo = True

    @skip_test_if_csm_var_missing(['image_id', 'version'])
    def test_limit_option(self):
        """Test limit option when creating items. Use dry-run for images to speed up the test"""
        base_bootprep_opts = '--format json'
        overwrite_options = ' '.join([f'--overwrite-{item}' for item in ('configs', 'images', 'templates')])

        limit_configs_result = self.run_bootprep(
            'limit-test.yaml',
            f'{base_bootprep_opts} --limit configurations'
        )
        configs_report = json.loads(limit_configs_result.stdout.decode())
        self.assertEqual(1, len(configs_report['configurations']))
        self.assertNotIn('images', configs_report)
        self.assertNotIn('session_templates', configs_report)

        limit_images_result = self.run_bootprep(
            'limit-test.yaml',
            f'{base_bootprep_opts} --dry-run --limit images'
        )
        self.assert_info_messages(
            [
                "Would create 1 images",
                "Skipping creation of CFS configurations based on value of --limit option",
                "Skipping creation of BOS session templates based on value of --limit option",
            ],
            [
                "Would create 1 CFS configuration",
                "Would create 1 BOS session template",
            ],
            limit_images_result.stderr.decode()
        )

        limit_session_templates_result = self.run_bootprep(
            'limit-test.yaml',
            f'{base_bootprep_opts} --limit session_templates'
        )
        session_templates_report = json.loads(limit_session_templates_result.stdout.decode())
        self.assertEqual(1, len(session_templates_report['session_templates']))
        self.assertNotIn('configurations', session_templates_report)
        self.assertNotIn('images', session_templates_report)

        limit_two_result = self.run_bootprep(
            'limit-test.yaml',
            f'{base_bootprep_opts} {overwrite_options} --limit configurations --limit session_templates'
        )
        limit_two_report = json.loads(limit_two_result.stdout.decode())
        self.assertEqual(1, len(limit_two_report['configurations']))
        self.assertEqual(1, len(limit_two_report['session_templates']))
        self.assertNotIn('images', limit_two_report)


class TestBootprepIfExistsProperty(BootprepTestCase):
    """Test for the 'if_exists' property of bootprep input files in `sat bootprep run`"""
    needs_vcs_repo = True

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

    @skip_test_if_csm_var_missing(['recipe_id', 'version'])
    @skip_test_if_sle_products_missing
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

    @skip_test_if_csm_var_missing(['image_id'])
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
