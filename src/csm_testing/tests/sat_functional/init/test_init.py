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
Simple tests for the functionality of the `sat init` command.
"""
import shlex
import subprocess
import tempfile
import os
import shutil
import unittest

TOML_HEADINGS = ['api_gateway', 'bos', 'cfs', 'bootsys', 'format', 'general', 'logging', 's3']


def get_success_output(path):
    return f"INFO: Configuration file \"{path}\" generated."

def get_failure_output(path):
    return f"WARNING: Configuration file \"{path}\" already exists. Not generating configuration file."


class TestInit(unittest.TestCase):
    """Test the `sat init` command."""

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()
        os.environ["SAT_CONFIG_DIR"] = self.temp_dir_path

    def tearDown(self):
        del os.environ["SAT_CONFIG_DIR"]
        shutil.rmtree(self.temp_dir_path)

    def execute_command(self, command):
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True)
        command_output = proc.stdout.decode().strip()
        return command_output

    def validate_toml_headings(self, path, headers_to_validate):
        with open(path, 'r') as file:
            config = file.read()

        for header in headers_to_validate:
            self.assertIn(header, config)

    def test_init_command_empty_dir(self):
        """Test that `sat init` outputs the correct value when no sat
        configuration files exist in SAT_CONFIG_DIR"""
        command = 'sat init'

        command_output = self.execute_command(command)

        self.assertEqual(get_success_output(self.temp_dir_path + "/sat.toml"), command_output)
        self.assertTrue(os.path.isfile(self.temp_dir_path + "/sat.toml"))
        self.assertTrue(os.path.isdir(self.temp_dir_path + "/tokens"))
        self.validate_toml_headings(self.temp_dir_path + "/sat.toml", TOML_HEADINGS)

    def test_init_command_non_empty_dir(self):
        """Test that `sat init` returns the proper error when it has already been run."""
        command = 'sat init'

        self.execute_command(command)
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True)
        command_error = proc.stderr.decode().strip()

        self.assertEqual(get_failure_output(self.temp_dir_path + "sat.toml"), command_error)

    def test_init_command_force(self):
        """Test that `sat init -f` overwrites the original file"""
        first_command = 'sat init'
        second_command = 'sat init -f'

        sat_toml_file_path = self.temp_dir_path + "/sat.toml"
        # run sat init
        subprocess.run(shlex.split(first_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True)
        # append a new header to the file
        text_to_append = "[temporary_header]"
        with open(sat_toml_file_path, 'a') as file:
            file.write(text_to_append)

        # validate that header is in the file
        self.validate_toml_headings(sat_toml_file_path, [text_to_append])

        command_output = self.execute_command(second_command)

        # validate that the file has been overwritten
        with open(sat_toml_file_path, 'r') as file:
            config = file.read()
        self.assertNotIn(text_to_append, config)

        self.assertEqual(get_success_output(sat_toml_file_path), command_output)
        self.assertTrue(os.path.isfile(self.temp_dir_path + "/sat.toml"))
        self.assertTrue(os.path.isdir(self.temp_dir_path + "/tokens"))
        self.validate_toml_headings(self.temp_dir_path + "/sat.toml", TOML_HEADINGS)

    def test_init_command_alternate_output(self):
        """Test that `sat init -o` outputs to the specified directory"""
        command = 'sat init -o'
        file_name = "/test_sat.toml"

        output_dir = self.temp_dir_path + "/output_dir"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        command += " " + output_dir + file_name

        command_output = self.execute_command(command)

        self.assertEqual(get_success_output(output_dir + file_name), command_output)

        # TODO: add back this test in CRAYSAT-1978
        # self.assertTrue(os.path.isfile(output_dir + file_name))

    def test_set_sat_config_file(self):
        """Test that `sat init` outputs to the path in the SAT_CONFIG_FILE variable"""
        command = 'sat init'
        file_name = "/test_sat.toml"

        output_dir = self.temp_dir_path + "/output_dir"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        os.environ["SAT_CONFIG_FILE"] = output_dir + file_name

        self.assertEqual(os.environ["SAT_CONFIG_FILE"], output_dir + file_name)

        command_output = self.execute_command(command)

        self.assertEqual(get_success_output(output_dir + file_name), command_output)
        # TODO: add back this test in CRAYSAT-1978
        self.assertTrue(os.path.isfile(output_dir + file_name))

        # Cleanup
        del os.environ["SAT_CONFIG_FILE"]
