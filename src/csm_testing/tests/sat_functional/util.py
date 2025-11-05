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
import hashlib
import json
import logging
import unittest
import os
import sys
import tempfile
import yaml

class SATTestCaseMeta(type):
    """
    Metaclass for SAT test cases that automatically generates a unique
    identifier for each test class based on the MD5 hash of the class name.
    """
    def __new__(mcs, name, bases, namespace):
        # Generate a unique identifier based on the class name
        class_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        namespace['unique_id'] = class_hash
        return super().__new__(mcs, name, bases, namespace)


class SATTestCase(unittest.TestCase, metaclass=SATTestCaseMeta):
    """Base class for SAT test cases.

    Each test class automatically gets a unique unique_id attribute based on
    the MD5 hash of the class name. This can be used to create unique resource
    names for tests to avoid collisions when tests are run in parallel.
    """

    # Class attribute set by SATTestCaseMeta metaclass
    unique_id: str

    def setUp(self):
        """Set up a temporary logging directory and save the path to that directory.

        This will be done per test method, so separate methods log to separate files.
        """
        # Do the generic logging setup steps
        try:
            self.sat_log_dir = tempfile.mkdtemp()
            os.environ['SAT_LOG_DIR'] = self.sat_log_dir
            self.sat_base_command = f'sat --logfile {os.path.join(self.sat_log_dir, "sat.log")}'
        except OSError as err:
            logging.error(f"Failed to create temporary directory for SAT logging : {err}\nUsing default SAT log directory.")
            self.sat_base_command = f'sat'

    def tearDown(self):
        """Print the test-method-specific SAT log file to stderr and clean it up."""
        self.output_and_cleanup_sat_log_dir()

    def output_and_cleanup_sat_log_dir(self):
        """
        Outputs the contents of the SAT log file for debugging purposes, then
        unsets the SAT_LOG_DIR environment variable and removes the temporary directory.
        """
        sat_log_file = os.path.join(self.sat_log_dir, "sat.log")
        if os.path.exists(sat_log_file):
            # output the contents of the log file to help with debugging
            try:
                with open(sat_log_file, 'r', encoding='utf-8') as log_file:
                    # output file contents to stderr
                    sys.stderr.write(f"\n----- Begin SAT log file -----"
                                     f"\n{log_file.read()}"
                                     f"----- End SAT log file -----\n")
            except OSError as err:
                logging.error(f"Failed to read and output the contents of SAT log file {sat_log_file}: {err}")
            try:
                os.remove(sat_log_file)
            except OSError as err:
                logging.error(f"Failed to remove sat log file: {sat_log_file}: {err}")


        del os.environ['SAT_LOG_DIR']

        try:
            if os.path.exists(self.sat_log_dir):
                os.rmdir(self.sat_log_dir)
        except OSError as err:
            logging.error(f"Failed to remove temporary sat logging directory: {self.sat_log_dir}: {err}")

    @staticmethod
    def validate_json(json_string: str) -> dict:
        """Validates a json string and returns the validated json

        Args:
            json_string (str): string containing json

        Returns:
            The parsed JSON data structure from the input string
        """
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as err:
            sys.stderr.write(f'Unable to decode json with error: {err}')
            assert False, f"The provided string is not valid json: {json_string}"


    @staticmethod
    def validate_yaml(yaml_string: str) -> dict:
        """Validates a yaml string and returns the validated yaml

        Args:
            yaml_string (str): string containing yaml.

        Returns:
            The parsed YAML data structure from the input string
        """
        try:
            return yaml.safe_load(yaml_string)
        except yaml.YAMLError as err:
            sys.stderr.write(f'Unable to load yaml with error: {err}')
            assert False, f"The provided string is not valid yaml: {yaml_string}"
