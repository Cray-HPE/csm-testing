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
Simple test for the functionality of the `sat --version` command. This should
just print the semantic version of the `sat` command.
"""
import shlex
import subprocess
from typing import Optional
import unittest

SAT_VERSION_FILE = '/opt/cray/etc/sat/version'


def get_version_file_contents() -> Optional[str]:
    """Get the contents of the file /opt/cray/etc/sat/version if it exists

    Returns:
        The version string from the file, or None if the file does not exist
    """
    try:
        with open(SAT_VERSION_FILE, 'r', encoding='utf-8') as version_file:
            return version_file.read().strip()
    except FileNotFoundError:
        return None


class TestVersion(unittest.TestCase):
    """Test the `sat --version` command."""

    def test_version_command(self):
        """Test that `sat --version` returns the semantic version."""
        command = 'sat --version'

        # Use stdout and stderr instead of capture_output=True for Python 3.6 compatibility
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True)
        version_output = proc.stdout.decode().strip()

        expected_version = get_version_file_contents()
        if expected_version:
            # The output is of the form "sat x.y.z"
            self.assertEqual(f'sat {expected_version}', version_output)
        else:
            # If the file does not exist, the `sat` podman wrapper script uses a csm-latest
            # tag from the registry. We don't know what the version is, but we can check the
            # format of the output at least.
            self.assertRegex(version_output, r'^sat \d+\.\d+\.\d+$')
