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
import unittest
import subprocess
import shlex
import re
import os
import json
import datetime
import uuid
import tempfile
from typing import List

from csm_testing.tests.sat_functional.util import SATTestCase

SAT_FIRMWARE_HEADER = ['xname', 'name', 'target_name', 'version']

def sort_xnames(xnames: List[str]) -> List[str]:
    """sort xnames in custom order: Mountain, Hill, River"""
    mountain_xnames = [ xname for xname in xnames if xname.startswith("x1000") ]
    hill_xnames = [ xname for xname in xnames if xname.startswith("x9000") ]
    other_xnames = [ xname for xname in xnames if xname not in mountain_xnames and xname not in hill_xnames ]

    return mountain_xnames + hill_xnames + other_xnames

def get_xnames() -> List[str]:
    """Get xnames from cray hsm inventory list"""
    command = "sat firmware --format json --filter \"name = BMC\""
    proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True)
    xnames = [item['xname'] for item in json.loads(proc.stdout)]

    # custom sort of xnames Mountain, Hill, River
    # FAS only works with mountain and hill nodes
    # on vhsasta so those need to be sorted to
    # the top
    sorted_xnames = sort_xnames(xnames)

    return sorted_xnames


class TestFirmware(SATTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.test_start_time = datetime.datetime.now()

        cls.xnames = get_xnames()
        # Create smaller snapshots using specific xnames
        cls.snapshot1 = cls.create_firmware_snapshot(cls.xnames[0])
        cls.snapshot2 = cls.create_firmware_snapshot(cls.xnames[1])
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Create the xname_file file in the temporary directory
        cls.xname_file = 'xname.txt'
        cls.xname_file_path = os.path.join(cls.temp_dir.name, cls.xname_file)

        # Write xnames to the file
        with open(cls.xname_file_path, 'w', encoding='utf-8') as xname_file:
            xname_file.write(f"{cls.xnames[0]}\n{cls.xnames[1]}\n")

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up all SAT snapshots created during the test class execution."""
        cls.test_end_time = datetime.datetime.now()
        cls.delete_sat_snapshots_in_time_window(cls.test_start_time, cls.test_end_time)
        cls.temp_dir.cleanup()

    @classmethod
    def create_firmware_snapshot(cls, xname: str) -> str:
        """Test that running `sat firmware` creates a snapshot and return snapshot name"""
        command = f'sat firmware -x {xname}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        info_msg = proc.stderr.decode().strip()

        # Extract the snapshot name from the info message
        pattern = r'INFO: Snapshot (\S+) created successfully\.\n'
        match = re.search(pattern, info_msg)
        if match:
            snapshot_name = match.group(1)
            return snapshot_name
        else:
            raise RuntimeError("Snapshot creation failed. Errors encountered:\n" + info_msg)

    @classmethod
    def delete_sat_snapshots_in_time_window(
        cls, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> None:
        """Find and delete all SAT snapshots created between the start and end times."""
        command = "sat firmware --snapshots"
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        snapshot_list = proc.stdout.decode().strip().splitlines()

        # Filter snapshots with the SAT prefix and within the test execution window
        for snapshot in snapshot_list:
            pattern = r"^SAT-\d{4}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}$"
            if re.match(pattern, snapshot):
                snapshot_time_str = snapshot[4:]  # Extract timestamp portion
                snapshot_time = datetime.datetime.strptime(snapshot_time_str, "%Y-%m-%d-%H-%M-%S")
                if start_time <= snapshot_time <= end_time:  # Check if within time window
                    cls.delete_snapshot(snapshot)

    @staticmethod
    def delete_snapshot(snapshot_name: str) -> None:
        """Delete a single SAT snapshot."""
        command = f'sat firmware --delete-snapshot {snapshot_name}'
        subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True )

    def test_firmware_describe_existing_snapshot(self) -> None:
        """Test that `sat firmware --snapshots SNAPSHOT` describes an existing firmware snapshot."""
        snapshot = self.snapshot1
        command = f'{self.sat_base_command} firmware --snapshots {snapshot}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode().strip()

        self.assertIn(snapshot, output)
        for col in SAT_FIRMWARE_HEADER:
            self.assertIn(col, output)

    def test_firmware_query_multiple_snapshots(self) -> None:
        """Test that `sat firmware --snapshots SNAPSHOT_1 SNAPSHOT_2` prints the details for two snapshots."""
        snap1 = self.snapshot1
        snap2 = self.snapshot2
        command = f'{self.sat_base_command} firmware --snapshots {snap1} {snap2}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode()

        self.assertIn(snap1, output)
        self.assertIn(snap2, output)
        for col in SAT_FIRMWARE_HEADER:
            self.assertIn(col, output)

    def test_firmware_query_nonexistent_snapshot(self) -> None:
        """Test that `sat firmware --snapshots NON_EXISTENT_SNAPSHOT` querying a non-existent firmware snapshot."""
        non_existent_snapshot = str(uuid.uuid4())
        command = f'{self.sat_base_command} firmware --snapshots {non_existent_snapshot}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
        stderr_output = proc.stderr.decode()
        warning_message = f'WARNING: Snapshot {non_existent_snapshot} does not exist.'
        self.assertIn(warning_message, stderr_output, f'Expected warning not found in stderr: {stderr_output}')
        error_message = 'ERROR: Failed to get snapshots: No firmware found.'
        self.assertIn(error_message, stderr_output, f'Expected error not found in stderr: {stderr_output}')

    def test_firmware_query_single_xname(self) -> None:
        """Test that `sat firmware -x <xname>` prints firmware info for a single xname."""
        self.assertGreater(len(self.xnames), 0, "No xnames found in sat firmware output.")
        xname = self.xnames[0]
        command = f'{self.sat_base_command} firmware -x {xname}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        xname_output = proc.stdout.decode().strip()
        self.assertIn(xname, xname_output)
        for col in SAT_FIRMWARE_HEADER:
            self.assertIn(col, xname_output)

    def test_firmware_query_multiple_xnames(self) -> None:
        """Test that `sat firmware -x <xname1>,<xname2>` prints firmware info for multiple xnames."""
        self.assertGreaterEqual(len(self.xnames), 2, "Less than two unique xnames found in sat firmware output.")
        command = f'{self.sat_base_command} firmware -x {self.xnames[0]},{self.xnames[1]}'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        multi_xname_output = proc.stdout.decode().strip()
        self.assertIn(self.xnames[0], multi_xname_output)
        self.assertIn(self.xnames[1], multi_xname_output)
        for col in SAT_FIRMWARE_HEADER:
            self.assertIn(col, multi_xname_output)

    def test_firmware_query_xnames_from_file(self) -> None:
        """Test that `sat firmware --xname-file <file>` prints firmware info for xnames listed in a file."""
        self.assertGreaterEqual(len(self.xnames), 2, "Less than two unique xnames found in sat firmware output.")
        command = f'{self.sat_base_command} firmware --xname-file {self.xname_file}'
        proc = subprocess.run(shlex.split(command), cwd=self.temp_dir.name,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        file_xname_output = proc.stdout.decode().strip()
        self.assertIn(self.xnames[0], file_xname_output)
        self.assertIn(self.xnames[1], file_xname_output)
        for col in SAT_FIRMWARE_HEADER:
            self.assertIn(col, file_xname_output)

    def test_firmware_list_snapshots(self) -> None:
        """Test that `sat firmware --snapshots` prints a list of snapshot names."""
        command = f'{self.sat_base_command} firmware --snapshots'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
        output = proc.stdout.decode().strip()
         # Validate that the snapshots created by this test are listed
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        self.assertGreater(len(lines), 0, "No snapshots listed.")
        self.assertIn(self.snapshot1, lines, f"Snapshot {self.snapshot1} not found in output.")
        self.assertIn(self.snapshot2, lines, f"Snapshot {self.snapshot2} not found in output.")

        # Validate naming convention for the created snapshots
        pattern = r"^SAT-\d{4}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}$"
        self.assertRegex(self.snapshot1, pattern,
                         f"Snapshot name {self.snapshot1} does not match expected format.")
        self.assertRegex(self.snapshot2, pattern,
                         f"Snapshot name {self.snapshot2} does not match expected format.")

if __name__ == '__main__':
    unittest.main()
