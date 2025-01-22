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
import json
import shlex
import subprocess
import unittest
import os
import configparser

SAT_SHOWREV_HEADER = ['product_name', 'product_version', 'images', 'image_recipes']

def get_sles_version():
    """Gets SLES version info found in /opt/cray/sat/etc/os-release.

    If that path does not exist, then use /etc/os-release instead.

    Returns:
        A string containing the NAME and VERSION field as found in the file
        /etc/os-release.
    """
    osrel_path = '/opt/cray/sat/etc/os-release'
    if not os.path.isfile(osrel_path):
        osrel_path = '/etc/os-release'

    try:
        with open(osrel_path, 'r') as f:
            config_string = '[default]\n' + f.read()
    except (FileNotFoundError, AttributeError, PermissionError):
        return 'ERROR'

    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(config_string)

    try:
        slesname = cp.get('default', 'NAME').replace('"', '')
        slesvers = cp.get('default', 'VERSION').replace('"', '')
        if slesname == '' or slesvers == '':
            return 'ERROR'
        else:
            return '{} {}'.format(slesname, slesvers)
    except configparser.NoOptionError:
        return 'ERROR'

def get_kernel_version():
    """Return the Kernel version as reported by `uname`"""
    return os.uname().release

def get_local_os_information():
    """Gets local OS information

    Returns:
        A list of tuples that contains version information about the
        local host Kernel version and OS distribution.
    """
    return [
        ('Kernel', get_kernel_version()),
        ('SLES', get_sles_version())
    ]

def get_column_names_list(input_string):
    # Split the input string into lines
    lines = input_string.strip().split('\n')

    # Extract the header line (the second line, which has the column names)
    header_line = None
    for line in lines:
        if '|' in line:
            header_line = line
            break

    # Get the column names by splitting on the | character and stripping white space
    column_names = [col.strip() for col in header_line.split('|') if col.strip()]

    return column_names


class TestShowRev(unittest.TestCase):
    """Test the `sat showrev` command."""

    def test_showrev_local_command(self):
        """Test that `sat showrev --local` returns the expected output."""
        command = 'sat showrev --local'

        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True)
        output = proc.stdout.decode().strip()
        lines = output.split('\n')

        # Check for the presence of expected fields
        self.assertIn("Local Host Operating System", output)
        self.assertIn("component", output)
        self.assertIn("version", output)

        # Extract the actual versions from the command output
        actual_versions = {}
        for line in lines:
            if '|' in line and 'component' not in line:
                parts = line.split('|')
                component = parts[1].strip()
                version = parts[2].strip()
                actual_versions[component] = version

        # Get the expected versions
        expected_versions = dict(get_local_os_information())

        # Compare the actual and expected versions
        for component, expected_version in expected_versions.items():
            self.assertIn(component, actual_versions)
            self.assertEqual(expected_version, actual_versions[component])

    def test_showrev_products_header(self):
        """Test that `sat showrev --products` returns the proper header."""
        command = 'sat showrev --products'

        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode().strip()
        lines = output.split('\n')

        # Extract the header line (the second line after the separator)
        header_line = None
        for i, line in enumerate(lines):
            if '|' in line:
                header_line = lines[i]
                break

        # Get the column names by splitting on the | character and stripping white space
        showrev_output_header = [col.strip() for col in header_line.split('|') if col.strip()]

        self.assertEqual(SAT_SHOWREV_HEADER, showrev_output_header)

    def test_showrev_products_command(self):
        """Test that `sat showrev --products --no-borders --no-headings` returns the expected number of products."""
        sat_command = 'sat showrev --products --no-borders --no-headings --fields product_name'
        sat_proc = subprocess.run(shlex.split(sat_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        sat_output = sat_proc.stdout.decode().strip()

        # Extract unique product names from the command output
        sat_product_names = set()
        for line in sat_output.splitlines():
            parts = line.split()
            if len(parts) >= 1:  # Ensure there is at least one part
                product_name = parts[0].strip()
                sat_product_names.add(product_name)

        sat_product_count = len(sat_product_names)

        # Command to get the unique product names from kubectl
        kubectl_command = 'kubectl get configmap -n services cray-product-catalog -o json'
        kubectl_proc = subprocess.run(shlex.split(kubectl_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        kubectl_output = kubectl_proc.stdout.decode().strip()

        # Parse the JSON output and extract unique product names
        kubectl_data = json.loads(kubectl_output)
        kubectl_product_names = set()
        for key, value in kubectl_data['data'].items():
            # Clean up the value and check if it's not an empty JSON object
            cleaned_value = value.strip().replace('\n', '')  # Remove newlines and whitespace
            if cleaned_value != "{}":
                kubectl_product_names.add(key)

        kubectl_product_count = len(kubectl_product_names)
        self.assertEqual(sat_product_count, kubectl_product_count)

    def test_showrev_system_headings(self):
        """Test that `sat showrev --system` returns the proper headings."""
        command = 'sat showrev --system'

        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode().strip()
        lines = output.split('\n')

        # Extract the header line (the line after the separator)
        header_line = None
        for i, line in enumerate(lines):
            if '|' in line and 'component' in line:
                header_line = lines[i]
                break

        # Get the column names by splitting on the | character and stripping white space
        showrev_output_header = [col.strip() for col in header_line.split('|') if col.strip()]

        expected_header = ['component', 'data']

        # Assert that the headers match
        self.assertEqual(expected_header, showrev_output_header)

    def test_showrev_all_command(self):
        """Test that `sat showrev --all` returns the expected output."""
        command = 'sat showrev --all'

        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode().strip()

        # Split the output into sections
        sections = output.split('#########################################################################')

        # Verify the presence of section titles
        self.assertIn("System Revision Information", sections[1])
        self.assertIn("Product Revision Information", sections[3])
        self.assertIn("Local Host Operating System", sections[5])

        # Extract headers from each section
        system_header = get_column_names_list(sections[2])
        product_header = get_column_names_list(sections[4])
        os_header = get_column_names_list(sections[6])

        # Check for the presence of expected headers in each section
        expected_system_headers = ["component", "data"]
        expected_product_headers = ["product_name", "product_version", "images"]
        expected_os_headers = ["component", "version"]

        for header in expected_system_headers:
            self.assertIn(header, system_header)
        for header in expected_product_headers:
            self.assertIn(header, product_header)
        for header in expected_os_headers:
            self.assertIn(header, os_header)

    def test_showrev_release_files(self):
        """Test that `sat showrev --release-files` returns the expected warning and error messages."""
        command = 'sat showrev --release-files'

        try:
            proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as e:
            output = e.stdout.decode().strip()  # Capture combined stdout and stderr
            expected_output = (
                "WARNING: The --release-files option is no longer supported. Use --products to see installed product versions instead.\n"
                "ERROR: No data collected"
            )
            # Assert that the output matches the expected output
            self.assertEqual(output, expected_output)


if __name__ == '__main__':
    unittest.main()
