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

    def setUp(self):
        self.items_to_delete = {
            'configurations': [],
            'images': [],
            'session_templates': []
        }

    def tearDown(self):
        for cfs_config_name in self.items_to_delete['configurations']:
            self.delete_cfs_configuration(cfs_config_name)

        for ims_image_id in self.items_to_delete['images']:
            self.delete_ims_image(ims_image_id)

        for bos_session_template_name in self.items_to_delete['session_templates']:
            self.delete_bos_session_template(bos_session_template_name)

        self.delete_all_cfs_configurations_matching_prefix(self.test_prefix)

    @classmethod
    def setUpClass(cls):
        """Create a temporary directory for bootprep input files."""
        cls.set_up_errors = []
        cls.temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

        cls.test_prefix = f'sat-bp-testing-{datetime.now().strftime("%Y-%m-%d")}'

        cls.get_product_catalog_data()
        cls.get_csm_vars()

        # Create the vars.yaml file in the temporary directory
        cls.vars_file_name = 'vars.yaml'
        vars_file_path = os.path.join(cls.temp_dir.name, cls.vars_file_name)
        vars_data = {
            'test': {
                'prefix': cls.test_prefix
            },
            'csm': cls.csm_vars
        }
        with open(vars_file_path, 'w', encoding='utf-8') as vars_file:
            yaml.dump(vars_data, vars_file)

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary directory for bootprep input files."""
        cls.temp_dir.cleanup()

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
        vcs_credentials_command = "kubectl get secret -n services vcs-user-credentials -o jsonpath='{.data.vcs_password}'"

        try:

            proc = subprocess.run(shlex.split(vcs_credentials_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            vcs_creds_encoded = proc.stdout.decode()
            vcs_creds_decoded = base64.b64decode(vcs_creds_encoded).decode('utf-8')

            git_command = f'git ls-remote --heads https://crayvcs:{vcs_creds_decoded}@api-gw-service-nmn.local/vcs/cray/' + git_repo_name

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
            cls.set_up_errors.append()
            logging.warning('Failed to get branch names for "%s" '
                            'created by test: %s'
                            'defaulting to main branch', git_repo_name, err.stderr)
            return "main"

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
        """
        find_command = f'cray cfs v3 configurations list'
        found_configurations = []
        try:
            proc = subprocess.run(shlex.split(find_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=True)
            proc_lines = proc.stdout.decode().splitlines()

            filtered_lines = [line for line in proc_lines if cfs_config_prefix in line]

            simplified_values = [re.search(r'"([^"]*)"$', item).group(1) for item in filtered_lines]

            found_configurations = simplified_values

        except subprocess.CalledProcessError as err:
            logging.warning('Failed to find CFS configurations with prefix "%s" '
                            'created by test: %s', cfs_config_prefix, err.stderr)

        for configuration_name in found_configurations:
            delete_command = f'cray cfs configurations delete {configuration_name}'
            try:
                subprocess.run(shlex.split(delete_command), check=True)
            except subprocess.CalledProcessError as err:
                logging.warning('Failed to delete CFS configuration "%s" '
                                'created by test: %s', configuration_name, err.stderr)


    @staticmethod
    def delete_ims_image(ims_image_id, permanent=True):
        """Delete an IMS image using the 'cray' CLI.

        This relies on the cray CLI being configured and authenticated on the system.
        """
        delete_command = f'cray ims images delete {ims_image_id}'
        try:
            subprocess.run(shlex.split(delete_command), check=True)
        except subprocess.CalledProcessError as err:
            logging.warning('Failed to delete IMS image "%s" '
                            'created by test: %s', ims_image_id, err.stderr)
            return

        if permanent:
            delete_command = f'cray ims deleted images delete {ims_image_id}'
            try:
                subprocess.run(shlex.split(delete_command), check=True)
            except subprocess.CalledProcessError as err:
                logging.warning('Failed to permanently delete IMS image "%s" '
                                'created by test: %s', ims_image_id, err.stderr)

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
        # Find the path to the given bootprep_file in the data directory
        src_bootprep_file_path = pkg_resources.resource_filename(
            'csm_testing',
            f'tests/sat_functional/bootprep/data/{bootprep_file}'
        )

        # Copy the bootprep input file into the temporary directory
        tmp_bootprep_file_path = os.path.join(self.temp_dir.name, os.path.basename(bootprep_file))
        shutil.copy(src_bootprep_file_path, tmp_bootprep_file_path)

        # Since the command is executed in the temporary directory containing
        # the bootprep input file, just use the relative file path
        command = f'sat bootprep run {bootprep_opts_str} {bootprep_file}'
        try:
            result = subprocess.run(shlex.split(command), cwd=self.temp_dir.name, check=check,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as err:
            logging.error(f"\nFailed to run command: {' '.join(err.cmd)}\n"
                          f"Exit Status: {err.returncode}\n"
                          f"Standard Output: \n{err.output.decode()}\n"
                          f"Standard Error: \n{err.stderr.decode()}\n")
            raise

        return result


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

        self.items_to_delete['configurations'].append(f'{self.test_prefix}-no-layers')

    @skip_test_if_csm_var_missing(['version', 'commit_hash'])
    def test_product_layers(self):
        """Test creating multiple CFS configurations using product-based layers"""
        result = self.run_bootprep('product-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(5, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

        for config in report['configurations']:
            self.items_to_delete['configurations'].append(config['name'])

    def test_git_layers(self):
        """Test creating multiple CFS configurations with git-based layers"""
        result = self.run_bootprep('git-layers-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(3, len(report['configurations']))

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

        for config in report['configurations']:
            self.items_to_delete['configurations'].append(config['name'])

    def test_special_parameters(self):
        """Test creating a CFS configuration with special parameters"""
        result = self.run_bootprep('special-parameters-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(1, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-special-parameters-layers',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

        for config in report['configurations']:
            self.items_to_delete['configurations'].append(config['name'])

    def test_additional_inventory(self):
        """Test creating CFS configurations with additional inventory"""
        result = self.run_bootprep('additional-inventory-config.yaml', '--format json')

        report = json.loads(result.stdout.decode())
        self.assertEqual(2, len(report['configurations']))
        self.assertEqual(f'{self.test_prefix}-csm-additional-inventory-branch',
                         report['configurations'][0]['name'])

        for config in report['configurations']:
            self.validate_cfs_config(config['name'])

        for config in report['configurations']:
            self.items_to_delete['configurations'].append(config['name'])

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


if __name__ == '__main__':
    unittest.main()
