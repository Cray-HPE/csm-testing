#
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
Simple tests for the functionality of the `sat status` command.
"""
import shlex
import subprocess
import re
import unittest

SAT_STATUS_HEADER = ['xname', 'Aliases', 'Type', 'NID', 'State', 'Flag', 'Enabled', 'Arch', 'Class', 'Role', 'SubRole', 'Net Type', 'Desired Config', 'Configuration Status', 'Error Count', 'Boot Status', 'Most Recent BOS Session', 'Most Recent Session Template', 'Most Recent Image']
SAT_FIELDS_HEADER = ['xname', 'Aliases']
SAT_HSM_FIELDS_HEADER = ['xname', 'Type', 'NID', 'State', 'Flag', 'Enabled', 'Arch', 'Class', 'Role', 'SubRole', 'Net Type']
SAT_SLS_FIELDS_HEADER = ['xname', 'Aliases']
SAT_HSM_AND_SLS_FIELDS_HEADER = ['xname', 'Aliases', 'Type', 'NID', 'State', 'Flag', 'Enabled', 'Arch', 'Class', 'Role', 'SubRole', 'Net Type']
SAT_CFS_FIELDS_HEADER = ['xname', 'Desired Config', 'Configuration Status', 'Error Count']
SAT_BOS_FIELDS_HEADER = ['xname', 'Boot Status', 'Most Recent BOS Session', 'Most Recent Session Template', 'Most Recent Image']


def get_header(command, num_lines_in_header):
    # Use stdout and stderr instead of capture_output=True for Python 3.6 compatibility
    proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True)
    status_output = proc.stdout.decode().strip()
    status_output_header = '\n'.join(status_output.splitlines()[:num_lines_in_header])
    return status_output_header

def get_column_names_list(input_string):
    # Split the input string into lines
    lines = input_string.strip().split('\n')

    # Extract the header line (the second line, which has the column names)
    header_line = lines[1]

    # Get the column names by splitting on the | character and stripping white space
    column_names = [col.strip() for col in header_line.split('|') if col.strip()]

    return column_names


class TestStatus(unittest.TestCase):
    """Test the `sat status` command."""

    def test_status_command(self):
        """Test that `sat status` returns the proper header."""
        command = 'sat status'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_STATUS_HEADER, status_output_header)

    def test_status_fields_command(self):
        """Test that `sat status --fields xname,aliases` returns the proper header."""
        command = 'sat status --fields xname,aliases'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_FIELDS_HEADER, status_output_header)

    def test_status_no_borders_command(self):
        """Test that `sat status --no-borders` returns the proper header."""
        command = 'sat status --no-borders'

        status_output_header = get_header(command, 1)
        column_names = re.split(r'\s{2,}', status_output_header.strip())

        self.assertEqual(SAT_STATUS_HEADER, column_names)

    def test_status_no_headings_command(self):
        """Test that `sat status --no-headings` returns the proper header."""
        command = 'sat status --no-headings'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertNotEquals(SAT_STATUS_HEADER, status_output_header)

    def test_status_hsm_fields_command(self):
        """Test that `sat status --hsm-fields` returns the proper header."""
        command = 'sat status --hsm-fields'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_HSM_FIELDS_HEADER, status_output_header)

    def test_status_sls_fields_command(self):
        """Test that `sat status --sls-fields` returns the proper header."""
        command = 'sat status --sls-fields'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_SLS_FIELDS_HEADER, status_output_header)

    def test_status_hsm_and_sls_fields_command(self):
        """Test that `sat status --sls-fields` returns the proper header."""
        command = 'sat status --hsm-fields --sls-fields'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_HSM_AND_SLS_FIELDS_HEADER, status_output_header)

    def test_status_cfs_fields_command(self):
        """Test that `sat status --cfs-fields` returns the proper header."""
        command = 'sat status --cfs-fields'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_CFS_FIELDS_HEADER, status_output_header)

    def test_status_bos_fields_command(self):
        """Test that `sat status --bos-fields` returns the proper header."""
        command = 'sat status --bos-fields'

        status_output_header = get_column_names_list(get_header(command, 3))

        self.assertEqual(SAT_BOS_FIELDS_HEADER, status_output_header)
