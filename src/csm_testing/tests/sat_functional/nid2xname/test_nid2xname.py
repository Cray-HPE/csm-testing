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
import json

from csm_testing.tests.sat_functional.util import SATTestCase


class TestNid2Xname(SATTestCase):

    @classmethod
    def setUpClass(cls):
        """Set up data used by all test methods."""
        cls.components = cls.get_hsm_components()
        cls.first_xname = cls.components[0]['Xname']
        cls.first_nid = cls.components[0]['NID']

    @classmethod
    def get_hsm_components(cls):
        """Get component data from HSM."""
        command = "cray hsm state components list --type Node --format json"
        command_args = command.split()
        result = subprocess.run(command_args, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_data = json.loads(result.stdout.decode().strip())
        components = []

        # Extract just the NID and Xname (ID) fields from each component
        for component in raw_data.get('Components', []):
            if 'NID' in component and 'ID' in component:
                components.append({
                    'NID': component['NID'],
                    'Xname': component['ID']
                })

        # Sort by NID (as integers)
        components.sort(key=lambda c: int(c['NID']) if c['NID'] is not None else float('inf'))

        return components

    @classmethod
    def get_consecutive_components(cls, min_count=3):
        """Return a list of components with at least min_count consecutive NIDs."""
        nids_int = [int(c['NID']) for c in cls.components]
        for i in range(len(nids_int) - (min_count - 1)):
            if all(nids_int[i + j] == nids_int[i] + j for j in range(min_count)):
                indices = list(range(i, i + min_count))
                return [cls.components[idx] for idx in indices]
        raise AssertionError(f"Could not find {min_count} consecutive NIDs in HSM output")

    def run_command(self, command):
        """Run a shell command and return the output."""
        command_args = command.split()
        result = subprocess.run(command_args, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()

    def test_nid_to_xname(self):
        """Test converting nid to xname."""
        # Use the pre-cached data
        xname = self.first_xname
        nid = self.first_nid

        # Convert nid to xname using sat command
        sat_command = f"{self.sat_base_command} nid2xname nid{nid}"
        converted_xname = self.run_command(sat_command)

        self.assertEqual(xname, converted_xname,
                         f"Expected xname {xname} but got {converted_xname} for nid {nid}")

    def test_xname_to_nid(self):
        """Test converting xname to nid."""
        # Use the pre-cached data
        xname = self.first_xname
        nid = self.first_nid

        # Convert xname to nid using sat command
        sat_command_reverse = f"{self.sat_base_command} xname2nid {xname}"
        converted_nid = self.run_command(sat_command_reverse)

        self.assertEqual(f"nid{int(nid):06d}", converted_nid,
                         f"Expected nid {int(nid):06d} but got {converted_nid} for xname {xname}")

    def test_multiple_nid_to_xname(self):
        """Test converting multiple nids to xnames in a single command call."""
        # Use consecutive components for a better test
        consecutive_components = self.get_consecutive_components(min_count=3)
        nids = [str(component['NID']) for component in consecutive_components]
        xnames = [component['Xname'] for component in consecutive_components]

        # Test with space-separated nids
        nid_args = ' '.join([f"nid{nid}" for nid in nids])
        sat_command = f"{self.sat_base_command} nid2xname {nid_args}"
        converted_xnames = self.run_command(sat_command)
        expected_xnames = ','.join(xnames)
        self.assertEqual(expected_xnames, converted_xnames,
                        f"Space-separated test: Expected xnames {expected_xnames} but got {converted_xnames}")

        # Test with comma-separated nids
        nid_list = ','.join([f"nid{nid}" for nid in nids])
        sat_command = f"{self.sat_base_command} nid2xname {nid_list}"
        converted_xnames = self.run_command(sat_command)
        self.assertEqual(expected_xnames, converted_xnames,
                        f"Comma-separated test: Expected xnames {expected_xnames} but got {converted_xnames}")

    def test_multiple_xname_to_nid(self):
        """Test converting multiple xnames to nids in a single command call."""
        # Use consecutive components for a better test
        consecutive_components = self.get_consecutive_components(min_count=3)
        nids = [str(c['NID']) for c in consecutive_components]
        xnames = [c['Xname'] for c in consecutive_components]

        # The default output format is range when multiple xnames are provided
        expected_nid_range = f"nid[{int(nids[0]):06d}-{int(nids[-1]):06d}]"

        # Test with space-separated xnames
        xname_args = ' '.join(xnames)
        sat_command = f"{self.sat_base_command} xname2nid {xname_args}"
        converted_nids = self.run_command(sat_command)
        self.assertEqual(expected_nid_range, converted_nids,
                        f"Space-separated test: Expected nid range {expected_nid_range} but got {converted_nids}")

        # Test with comma-separated xnames
        xname_list = ','.join(xnames)
        sat_command = f"{self.sat_base_command} xname2nid {xname_list}"
        converted_nids = self.run_command(sat_command)
        self.assertEqual(expected_nid_range, converted_nids,
                        f"Comma-separated test: Expected nid range {expected_nid_range} but got {converted_nids}")

    def test_xname2nid_format_range(self):
        """Test xname2nid with -f range option using consecutive nids."""
        consecutive_components = self.get_consecutive_components(min_count=3)
        nids = [str(c['NID']) for c in consecutive_components]
        xnames = [c['Xname'] for c in consecutive_components]
        expected_nid_range = f"nid[{int(nids[0]):06d}-{int(nids[-1]):06d}]"
        sat_command_range = f"{self.sat_base_command} xname2nid -f range {' '.join(xnames)}"
        converted_nid_range = self.run_command(sat_command_range)
        self.assertEqual(expected_nid_range, converted_nid_range, f"Expected nid range {expected_nid_range} but got {converted_nid_range}")

    def test_xname2nid_format_nid(self):
        """Test xname2nid with -f nid option."""
        # Use the first few components from the cached data
        sample_components = self.components[:3]
        nids = [str(component['NID']) for component in sample_components]
        xnames = [component['Xname'] for component in sample_components]

        sat_command_nid = f"{self.sat_base_command} xname2nid -f nid {' '.join(xnames)}"
        converted_nid_list = self.run_command(sat_command_nid)

        expected_nid_list = ','.join([f"nid{int(nid):06d}" for nid in nids])
        self.assertEqual(expected_nid_list, converted_nid_list, f"Expected nid list {expected_nid_list} but got {converted_nid_list}")

    def test_nid_range_to_xname(self):
        """Test converting nid range to xnames using consecutive nids."""
        consecutive_components = self.get_consecutive_components(min_count=3)
        nids = [str(c['NID']) for c in consecutive_components]
        xnames = [c['Xname'] for c in consecutive_components]
        nid_range = f"nid[{int(nids[0]):06d}-{int(nids[-1]):06d}]"
        expected_xnames = ','.join(xnames)
        sat_command = f"{self.sat_base_command} nid2xname {nid_range}"
        converted_xnames = self.run_command(sat_command)
        self.assertEqual(expected_xnames, converted_xnames, f"Expected xnames {expected_xnames} but got {converted_xnames} for nid range {nid_range}")


if __name__ == '__main__':
    unittest.main()