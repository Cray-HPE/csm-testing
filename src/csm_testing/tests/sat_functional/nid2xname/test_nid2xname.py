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

class TestNid2Xname(unittest.TestCase):
    
    def run_command(self, command):
        """Run a shell command and return the output."""
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()

    def test_nid_to_xname(self):
        """Test converting nid to xname."""
        # Get the xname and nid from the HSM
        xname_command = "cray hsm state components list --type Node --format json | jq -r '.Components[0].ID'"
        nid_command = "cray hsm state components list --type Node --format json | jq -r '.Components[0].NID'"
        
        xname = self.run_command(xname_command)
        nid = self.run_command(nid_command)
        
        # Convert nid to xname using sat command
        sat_command = f"sat nid2xname nid{nid}"
        converted_xname = self.run_command(sat_command)
        
        self.assertEqual(xname, converted_xname, f"Expected xname {xname} but got {converted_xname} for nid {nid}")

    def test_xname_to_nid(self):
        """Test converting xname to nid."""
        # Get the xname and nid from the HSM
        xname_command = "cray hsm state components list --type Node --format json | jq -r '.Components[0].ID'"
        nid_command = "cray hsm state components list --type Node --format json | jq -r '.Components[0].NID'"

        xname = self.run_command(xname_command)
        nid = self.run_command(nid_command)

        # Convert xname to nid using sat command
        sat_command_reverse = f"sat xname2nid {xname}"
        converted_nid = self.run_command(sat_command_reverse)

        self.assertEqual(f"nid{int(nid):06d}", converted_nid, f"Expected nid {int(nid):06d} but got {converted_nid} for xname {xname}")


    def test_multiple_nid_to_xname(self):
        """Test converting multiple nids to xnames."""
        # Get multiple xnames and nids from the HSM
        command = "cray hsm state components list --type Node --format json | jq -r '.Components | map({NID: .NID, Xname: .ID}) | unique | sort_by(.NID) | .[0:3]'"
        components = json.loads(self.run_command(command))

        nids = [str(component['NID']) for component in components]
        xnames = [component['Xname'] for component in components]

        for nid, expected_xname in zip(nids, xnames):
            # Convert nid to xname using sat command
            sat_command = f"sat nid2xname nid{nid}"
            converted_xname = self.run_command(sat_command)

            self.assertEqual(expected_xname, converted_xname, f"Expected xname {expected_xname} but got {converted_xname} for nid {nid}")

    def test_multiple_xname_to_nid(self):
        """Test converting multiple xnames to nids."""
        # Get multiple xnames and nids from the HSM
        command = "cray hsm state components list --type Node --format json | jq -r '.Components | map({NID: .NID, Xname: .ID}) | unique | sort_by(.NID) | .[0:3]'"
        components = json.loads(self.run_command(command))

        nids = [str(component['NID']) for component in components]
        xnames = [component['Xname'] for component in components]

        for expected_nid, xname in zip(nids, xnames):
            # Convert xname to nid using sat command
            sat_command_reverse = f"sat xname2nid {xname}"
            converted_nid = self.run_command(sat_command_reverse)

            self.assertEqual(f"nid{int(expected_nid):06d}", converted_nid, f"Expected nid {int(expected_nid):06d} but got {converted_nid} for xname {xname}")


    def test_xname2nid_format_range(self):
        """Test xname2nid with -f range option."""
        # Get multiple xnames and nids from the HSM
        command = "cray hsm state components list --type Node --format json | jq -r '.Components | map({NID: .NID, Xname: .ID}) | unique | sort_by(.NID) | .[0:3]'"
        components = json.loads(self.run_command(command))

        nids = [str(component['NID']) for component in components]
        xnames = [component['Xname'] for component in components]

        # Convert xnames to nid range using sat command
        sat_command_range = f"sat xname2nid -f range {' '.join(xnames)}"
        converted_nid_range = self.run_command(sat_command_range)

        # Verify the range conversion
        expected_nid_range = f"nid[{int(nids[0]):06d}-{int(nids[-1]):06d}]"
        self.assertEqual(expected_nid_range, converted_nid_range, f"Expected nid range {expected_nid_range} but got {converted_nid_range}")

    def test_xname2nid_format_nid(self):
        """Test xname2nid with -f nid option."""
        # Get multiple xnames and nids from the HSM
        command = "cray hsm state components list --type Node --format json | jq -r '.Components | map({NID: .NID, Xname: .ID}) | unique | sort_by(.NID) | .[0:3]'"
        components = json.loads(self.run_command(command))

        nids = [str(component['NID']) for component in components]
        xnames = [component['Xname'] for component in components]

        # Convert xnames to individual nids using sat command
        sat_command_nid = f"sat xname2nid -f nid {' '.join(xnames)}"
        converted_nid_list = self.run_command(sat_command_nid)

        # Verify the individual nids conversion
        expected_nid_list = ','.join([f"nid{int(nid):06d}" for nid in nids])
        self.assertEqual(expected_nid_list, converted_nid_list, f"Expected nid list {expected_nid_list} but got {converted_nid_list}")

    def test_nid_range_to_xname(self):
        """Test converting nid range to xnames."""
        # Get multiple xnames and nids from the HSM
        command = "cray hsm state components list --type Node --format json | jq -r '.Components | map({NID: .NID, Xname: .ID}) | unique | sort_by(.NID) | .[0:6]'"
        components = json.loads(self.run_command(command))

        nids = [str(component['NID']) for component in components]
        xnames = [component['Xname'] for component in components]

        # Define the NID range
        nids_int = sorted(int(n) for n in nids)
        ranges = []
        start = prev = nids_int[0]
        for nid in nids_int[1:]:
            if nid == prev + 1:
                prev = nid
            else:
                ranges.append((start, prev))
                start = prev = nid

        ranges.append((start, prev))
        range_strs = ",".join(f"{s:06d}-{e:06d}" for s, e in ranges)
        nid_range = f"nid[{range_strs}]"

        # Expected xnames corresponding to the NID range
        expected_xnames = ','.join(xnames)

        # Convert nid range to xnames using sat command
        sat_command = f"sat nid2xname {nid_range}"
        converted_xnames = self.run_command(sat_command)

        self.assertEqual(expected_xnames, converted_xnames, f"Expected xnames {expected_xnames} but got {converted_xnames} for nid range {nid_range}")


if __name__ == '__main__':
    unittest.main()