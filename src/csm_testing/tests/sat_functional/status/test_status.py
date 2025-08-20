#
# MIT License
#
# (C) Copyright 2024-2025 Hewlett Packard Enterprise Development LP
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
from typing import List, Tuple
import unittest

from csm_testing.tests.sat_functional.sat_testing_utils import validate_json, validate_yaml

SAT_STATUS_HEADER = ['xname', 'Aliases', 'Type', 'NID', 'State', 'Flag', 'Enabled', 'Arch',
                     'Class', 'Role', 'SubRole', 'Net Type', 'Locked', 'Desired Config',
                     'Configuration Status', 'Error Count', 'Boot Status',
                     'Most Recent BOS Session', 'Most Recent Session Template',
                     'Most Recent Image']
SAT_FIELDS_HEADER = ['xname', 'Aliases']
SAT_HSM_FIELDS_HEADER = ['xname', 'Type', 'NID', 'State', 'Flag', 'Enabled', 'Arch', 'Class',
                         'Role', 'SubRole', 'Net Type', 'Locked']
SAT_SLS_FIELDS_HEADER = ['xname', 'Aliases']
SAT_HSM_AND_SLS_FIELDS_HEADER = ['xname', 'Aliases', 'Type', 'NID', 'State', 'Flag', 'Enabled',
                                 'Arch', 'Class', 'Role', 'SubRole', 'Net Type', 'Locked']
SAT_CFS_FIELDS_HEADER = ['xname', 'Desired Config', 'Configuration Status', 'Error Count']
SAT_BOS_FIELDS_HEADER = ['xname', 'Boot Status', 'Most Recent BOS Session',
                         'Most Recent Session Template', 'Most Recent Image']


def get_command_output(command: str) -> Tuple[str, str]:
    """Run the specified command.

    Args:
        command (str): command to be run

    Returns:
        Tuple ([str, str]): standard output and standard error
    """
    # Use stdout and stderr instead of capture_output=True for Python 3.6 compatibility
    proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True)
    std_output = proc.stdout.decode().strip()
    std_err = proc.stderr.decode().strip()

    return std_output, std_err

def get_header(command: str, num_lines_in_header: int) -> Tuple[str, str, str]:
    """ Run the specified command.

    Args:
        command (str): command to be run
        num_lines_in_header (int): number of lines in the output to be returned

    Returns:
         Tuple (str, str, str): the standard output, standard error, and the header (meaning the first
         num_lines_in_header lines in the output)
    """
    status_output, status_err = get_command_output(command)
    status_output_header = '\n'.join(status_output.splitlines()[:num_lines_in_header])
    return status_output, status_err, status_output_header

def adjust_expected_header(header: List[str], sat_output: str) -> List[str]:
    """
    Return a copy of the specified header, removing keys which were omitted in the SAT output
    """
    new_header = header.copy()
    for col in header:
        info_line = f"INFO: All values for '{col}' are 'MISSING', omitting key."
        if info_line in sat_output:
            new_header.remove(col)
    return new_header

def get_column_names_list(input_string: str) -> List[str]:
    """ Return the list of column names specified in the header line of the input string """
    # Split the input string into lines
    lines = input_string.strip().split('\n')

    # Extract the header line (the second line, which has the column names)
    header_line = lines[1]

    # Get the column names by splitting on the | character and stripping white space
    column_names = [col.strip() for col in header_line.split('|') if col.strip()]

    return column_names


class TestStatus(unittest.TestCase):
    """Test the `sat status` command."""

    def test_status_command(self) -> None:
        """Test that `sat status` returns the proper header."""
        command = 'sat status'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_formatting_json(self) -> None:
        """Test that `sat status --format json` returns the properly formatted response"""
        json_command = 'sat status --format json'

        json_std_out, json_std_err = get_command_output(json_command)
        json_response = validate_json(json_std_out)

        self.assertTrue(json_response)

        json_header_keys = list(json_response[0].keys())

        expected_header = adjust_expected_header(SAT_STATUS_HEADER, json_std_err)

        self.assertEqual(expected_header, json_header_keys)

    def test_status_formatting_yaml(self) -> None:
        """Test that `sat status --format yaml` returns the properly formatted response"""
        yaml_command = 'sat status --format yaml'

        yaml_std_out, yaml_std_err = get_command_output(yaml_command)
        yaml_response = validate_yaml(yaml_std_out)

        self.assertTrue(yaml_response)

        yaml_header_keys = list(yaml_response[0].keys())

        expected_header = adjust_expected_header(SAT_STATUS_HEADER, yaml_std_err)

        self.assertEqual(expected_header, yaml_header_keys)

    def test_status_fields_command(self) -> None:
        """Test that `sat status --fields xname,aliases` returns the proper header."""
        command = 'sat status --fields xname,aliases'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_no_borders_command(self) -> None:
        """Test that `sat status --no-borders` returns the proper header."""
        command = 'sat status --no-borders'

        status_output, status_err, status_output_header = get_header(command, 1)
        column_names = re.split(r'\s{2,}', status_output_header.strip())

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(expected_header, column_names)

    def test_status_no_headings_command(self) -> None:
        """Test that `sat status --no-headings` returns the proper header."""
        command = 'sat status --no-headings'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertNotEqual(expected_header, status_output_header)

    def test_status_hsm_fields_command(self) -> None:
        """Test that `sat status --hsm-fields` returns the proper header."""
        command = 'sat status --hsm-fields'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_HSM_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_sls_fields_command(self) -> None:
        """Test that `sat status --sls-fields` returns the proper header."""
        command = 'sat status --sls-fields'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_SLS_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_hsm_and_sls_fields_command(self) -> None:
        """Test that `sat status --sls-fields` returns the proper header."""
        command = 'sat status --hsm-fields --sls-fields'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_HSM_AND_SLS_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_cfs_fields_command(self) -> None:
        """Test that `sat status --cfs-fields` returns the proper header."""
        command = 'sat status --cfs-fields'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_CFS_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_bos_fields_command(self) -> None:
        """Test that `sat status --bos-fields` returns the proper header."""
        command = 'sat status --bos-fields'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_BOS_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_unambiguous_fields_command(self) -> None:
        """Test that `sat status --fields xna,alia` returns the proper header unambiguosly"""
        command = 'sat status --fields xna,alia'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_ambiguous_field_rol(self) -> None:
        """Test that `sat status --fields rol` warns about ambiguity and outputs the first match."""
        command = 'sat status --fields rol'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)
        status_all_output = status_output + '\n' + status_err

        # Check for the ambiguity warning
        self.assertIn(
            "WARNING: Heading 'rol' is ambiguous.",
            status_all_output,
            msg="Ambiguous field warning not found in output."
        )
        self.assertIn(
            "Using first match: 'Role' from",
            status_all_output,
            msg="First match warning not found in output."
        )

        # Check that the header is just 'Role'
        self.assertEqual(status_output_header, ['Role'], "Expected only 'Role' column in table header.")

    def test_status_unambiguous_filter_command(self) -> None:
        """Test that `sat status --filter NID="1000*"` returns the proper header unambiguosly"""
        command = 'sat status --filter NID="1000*"'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_ambiguous_filter_command(self) -> None:
        """Test that `sat status --filter srol=storage` warns about ambiguity and outputs the first match."""
        command = 'sat status --filter srol=storage'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)
        status_all_output = status_output + '\n' + status_err

        # Check for the ambiguity warning
        self.assertIn(
            "WARNING: Heading 'srol' is ambiguous.",
            status_all_output,
            msg="Ambiguous field warning not found in output."
        )
        self.assertIn(
            "Using first match: 'SubRole' from",
            status_all_output,
            msg="First match warning not found in output."
        )
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(status_output_header, expected_header)

    def test_status_operator_filter_command(self) -> None:
        """Test that `sat status --filter Role!=Management` returns the output which are not Management"""
        command = 'sat status --filter Role!=Management'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_boolean_filter_command(self) -> None:
        """Test that `sat status --filter "xname = x* and Aliases = nid??????"` returns proper header after filtering"""
        command = 'sat status --filter "xname = x* and Aliases = nid??????"'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_STATUS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

    def test_status_multiple_filter_command(self) -> None:
        """Test that `sat status --hsm-fields --filter Role=Management --filter SubRole=Master` returns proper header after multiple filtering"""
        command = 'sat status --hsm-fields --filter Role=Management --filter SubRole=Master'

        status_output, status_err, status_output_header_str = get_header(command, 3)
        status_output_header = get_column_names_list(status_output_header_str)

        # Combine status_output and status_err for searching INFO lines
        status_all_output = status_output + '\n' + status_err
        expected_header = adjust_expected_header(SAT_HSM_FIELDS_HEADER, status_all_output)

        self.assertEqual(expected_header, status_output_header)

