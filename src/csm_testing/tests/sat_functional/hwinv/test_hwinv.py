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
Simple tests for the functionality of the `sat hwinv` command.
"""
import shlex
import subprocess
import unittest
import re
import json
from typing import List

from csm_testing.tests.sat_functional.util import SATTestCase


HWINV_HEADERS = {
    "nodes": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Cabinet Type', 'Memory Type', 'Memory Device Type', 'Memory Manufacturer',
        'Memory Model', 'Memory Size (GiB)', 'Memory Module Count', 'Processor Count',
        'Processor Manufacturer', 'Processor Model', 'Accelerator Count',
        'Accelerator Riser Count', 'HSN NIC Count', 'Drive Count',
        'Total Drive Capacity (GiB)', 'BIOS Version'
    ],
    "chassis": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "HSN boards": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "compute modules": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "router modules": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "node enclosures": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "node enclosure power supplies": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "processors": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Total Cores', 'Total Threads', 'Max Speed (MHz)'
    ],
    "node accelerators": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Location Name'
    ],
    "node accelerator risers": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Board Serial Number', 'Producer', 'Engineering Change Level'
    ],
    "node HSN NICS": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number'
    ],
    "memory modules": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Memory Type', 'Device Type', 'Capacity (MiB)', 'Operating Speed (MHz)'
    ],
    "drives": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Media Type', 'Capacity (GiB)', 'Percent Life Left'
    ],
    "CMM rectifiers": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Power Input Watts', 'Power Output Watts', 'Power Supply Type', 'Firmware Version'
    ],
    "node bmcs": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Manager Type', 'Firmware Version'
    ],
    "router bmcs": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Manager Type', 'Firmware Version'
    ],
    "mgmt switches": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Chassis Type'
    ],
    "cabinet pdus": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Equipment Type', 'Firmware Version'
    ],
    "cabinet pdu power connectors": [
        'xname', 'FRUID', 'Manufacturer', 'Model', 'Part Number', 'SKU', 'Serial Number',
        'Nominal Voltage', 'Outlet Type', 'Phase Wiring Type', 'Power Enabled',
        'Rated Current Amps', 'Voltage Type'
    ]
}


SECTION_TO_TYPE = {
    "nodes": "Node",
    "chassis": "Chassis",
    "HSN boards": "HSNBoard",
    "compute modules": "ComputeModule",
    "router modules": "RouterModule",
    "node enclosures": "NodeEnclosure",
    "node enclosure power supplies": "NodeEnclosurePowerSupply",
    "processors": "Processor",
    "node accelerators": "NodeAccel",
    "node accelerator risers": "NodeAccelRiser",
    "node HSN NICS": "NodeHsnNic",
    "memory modules": "Memory",
    "drives": "Drive",
    "CMM rectifiers": "CMMRectifier",
    "node bmcs": "NodeBMC",
    "router bmcs": "RouterBMC",
    "mgmt switches": "MgmtSwitch",
    "cabinet pdus": "CabinetPDU",
    "cabinet pdu power connectors": "CabinetPDUPowerConnector"
}


def get_present_components() -> List[str]:
    """Retrieve the list of components present in the system using HSM.
    
    Returns:
        The list of unique component types present in the system.
    """
    command = "cray hsm inventory hardware list --format json"
    proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    hsm_output = proc.stdout.decode()
    components = json.loads(hsm_output)
    return list(set([component["Type"] for component in components]))


def adjust_expected_header(header: List[str], sat_output: str) -> List[str]:
    """Return a copy of the specified header, removing keys which were omitted in the output"""
    new_header = header.copy()
    for col in header:
        info_miss = f"INFO: All values for '{col}' are 'MISSING', omitting key."
        info_empty = f"INFO: All values for '{col}' are 'EMPTY', omitting key."
        if any(msg in sat_output for msg in (info_miss, info_empty)):
            new_header.remove(col)
    return new_header


def get_column_names_list(input_string: str) -> List[str]:
    """Return the list of column names specified in the header line of the input string."""
    lines = input_string.strip().split('\n')
    for line in lines:
        if line.strip().startswith('| xname'):
            header_line = line
            return [col.strip() for col in header_line.split('|') if col.strip()]
    return []


class TestHwinvList(SATTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.present_components = get_present_components()

    def run_hwinv_list_test(self, command: str, expected_key: str, adjust_headers: bool = True) -> None:
        """Helper function to run an hwinv command test."""
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        stderr = proc.stderr.decode()
        self.assertIn(f"Listing of all {expected_key}", stdout)
        actual_header = get_column_names_list(stdout)
        if adjust_headers:
            expected_header = adjust_expected_header(HWINV_HEADERS[expected_key], stderr)
        else:
            expected_header = HWINV_HEADERS[expected_key]

        hsm_type = SECTION_TO_TYPE[expected_key]
        if not actual_header:
            if hsm_type in self.present_components:
                self.fail(f'The table for {expected_key} is empty, but there are components of '
                          f'{hsm_type} type present in the system.')
            else:
                # If there are not components of this type, the table is expected to be empty
                return
        self.assertEqual(expected_header, actual_header)

    def test_hwinv_list_nodes(self) -> None:
        """Test that `sat hwinv --list-nodes` returns the proper header."""
        command = f'{self.sat_base_command} hwinv --list-nodes'
        self.run_hwinv_list_test(command, 'nodes')

    def test_hwinv_list_nodes_include_miss_and_empty(self) -> None:
        """Test that `sat hwinv --list-nodes --show-missing --show-empty` returns all the header."""
        command = f'{self.sat_base_command} hwinv --list-nodes --show-missing --show-empty'
        self.run_hwinv_list_test(command, 'nodes', adjust_headers=False)

    def test_hwinv_list_drives_include_miss_and_empty(self) -> None:
        """Test that `sat hwinv --list-drives --show-missing --show-empty` returns all the header."""
        command = f'{self.sat_base_command} hwinv --list-drives --show-missing --show-empty'
        self.run_hwinv_list_test(command, 'drives', adjust_headers=False)

    def test_hwinv_list_chassis(self) -> None:
        """Test that `sat hwinv --list-chassis` returns proper header."""
        command = f'{self.sat_base_command} hwinv --list-chassis'
        self.run_hwinv_list_test(command, 'chassis')

    def test_hwinv_list_hsnboards(self) -> None:
        """Test that `sat hwinv --list-hsn-boards` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-hsn-boards'
        self.run_hwinv_list_test(command, 'HSN boards')

    def test_hwinv_list_compute_modules(self) -> None:
        """Test that `sat hwinv --list-compute-modules` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-compute-modules'
        self.run_hwinv_list_test(command, 'compute modules')

    def test_hwinv_list_router_modules(self) -> None:
        """Test that `sat hwinv --list-router-modules` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-router-modules'
        self.run_hwinv_list_test(command, 'router modules')

    def test_hwinv_list_node_enclosures(self) -> None:
        """Test that `sat hwinv --list-node-enclosures` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-enclosures'
        self.run_hwinv_list_test(command, 'node enclosures')

    def test_hwinv_list_node_enclosure_power_supplies(self) -> None:
        """Test that `sat hwinv --list-node-enclosure-power-supplies` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-enclosure-power-supplies'
        self.run_hwinv_list_test(command, 'node enclosure power supplies')

    def test_hwinv_list_procs(self) -> None:
        """Test that `sat hwinv --list-procs` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-procs'
        self.run_hwinv_list_test(command, 'processors')

    def test_hwinv_list_node_accels(self) -> None:
        """Test that `sat hwinv --list-node-accels` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-accels'
        self.run_hwinv_list_test(command, 'node accelerators')

    def test_hwinv_list_node_accel_risers(self) -> None:
        """Test that `sat hwinv --list-node-accel-risers` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-accel-risers'
        self.run_hwinv_list_test(command, 'node accelerator risers')

    def test_hwinv_list_node_hsn_nics(self) -> None:
        """Test that `sat hwinv --list-node-hsn-nics` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-hsn-nics'
        self.run_hwinv_list_test(command, 'node HSN NICS')

    def test_hwinv_list_mems(self) -> None:
        """Test that `sat hwinv --list-mems` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-mems'
        self.run_hwinv_list_test(command, 'memory modules')

    def test_hwinv_list_drives(self) -> None:
        """Test that `sat hwinv --list-drives` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-drives'
        self.run_hwinv_list_test(command, 'drives')

    def test_hwinv_list_cmm_rectifiers(self) -> None:
        """Test that `sat hwinv --list-cmm-rectifiers` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-cmm-rectifiers'
        self.run_hwinv_list_test(command, 'CMM rectifiers')

    def test_hwinv_list_node_bmcs(self) -> None:
        """Test that `sat hwinv --list-node-bmcs` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-node-bmcs'
        self.run_hwinv_list_test(command, 'node bmcs')

    def test_hwinv_list_router_bmcs(self) -> None:
        """Test that `sat hwinv --list-router-bmcs` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-router-bmcs'
        self.run_hwinv_list_test(command, 'router bmcs')

    def test_hwinv_list_mgmt_switches(self) -> None:
        """Test that `sat hwinv --list-mgmt-switches` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-mgmt-switches'
        self.run_hwinv_list_test(command, 'mgmt switches')

    def test_hwinv_list_cabinet_pdus(self) -> None:
        """Test that `sat hwinv --list-cabinet-pdus` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-cabinet-pdus'
        self.run_hwinv_list_test(command, 'cabinet pdus')

    def test_hwinv_list_cabinet_pdu_power_connectors(self) -> None:
        """Test that `sat hwinv --list-cabinet-pdu-power-connectors` returns proper header"""
        command = f'{self.sat_base_command} hwinv --list-cabinet-pdu-power-connectors'
        self.run_hwinv_list_test(command, 'cabinet pdu power connectors')

    def test_hwinv_list_all(self) -> None:
        """Test that `sat hwinv --list-all --show-missing --show-empty` validates only the components present in the system."""
        command = f'{self.sat_base_command} hwinv --list-all --show-missing --show-empty'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        stdout_lines = stdout.splitlines()

        # Iterate through the lines to find sections and validate headers
        for i, line in enumerate(stdout_lines):
            # Match section titles like "Listing of all <SOME COMPONENT TYPE>"
            match = re.match(r"Listing of all (.+)", line.strip())
            if match:
                section_name = match.group(1)
                component_type = SECTION_TO_TYPE.get(section_name)

                # If the section doesn't correspond to any present component, skip it
                if component_type not in self.present_components:
                    continue

                self.assertIn(section_name, HWINV_HEADERS,
                    f"Unexpected section '{section_name}' found in output."
                )

                expected_headers = HWINV_HEADERS[section_name]

                # Get the header line (3 lines below the section title)
                header_line_index = i + 3
                if header_line_index >= len(stdout_lines):
                    self.fail(f"Header row for section '{section_name}' not found in output.")
                header_line = stdout_lines[header_line_index].strip()

                # Parse the actual header
                actual_header = [col.strip() for col in header_line.split("|") if col.strip()]

                # Validate the actual header against the adjusted expected header
                self.assertEqual(expected_headers, actual_header,
                    f"Header for section '{section_name}' does not match the expected fields. "
                    f"Expected: {expected_headers}, Actual: {actual_header}"
                )

    def test_hwinv_list_node_fields(self) -> None:
        """Test that `sat hwinv --list-nodes --node-fields 'xname, FRUID, Serial Number, SKU'` returns the proper header."""
        expected_header = ['xname', 'FRUID', 'Serial Number', 'SKU']
        command = f"{self.sat_base_command} hwinv --list-nodes --node-fields '{','.join(expected_header)}'"
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()

        self.assertIn("Listing of all nodes", stdout)
        actual_header = get_column_names_list(stdout)
        if not actual_header:
            return

        self.assertEqual(expected_header, actual_header)

    def test_hwinv_list_proc_fields(self) -> None:
        """Test that `sat hwinv --list-procs --proc-field 'xname, FRUID, Manufacturer, Model'` returns proper header"""
        expected_header = ['xname', 'FRUID', 'Manufacturer', 'Model']
        command = f"{self.sat_base_command} hwinv --list-procs --proc-fields '{','.join(expected_header)}'"
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()

        self.assertIn("Listing of all processors", stdout)
        actual_header = get_column_names_list(stdout)
        if not actual_header:
            return

        self.assertEqual(expected_header, actual_header)

    def test_hwinv_field_limiting(self) -> None:
        """Test that `sat hwinv --fields 'xname, FRUID, Part Number, SKU'` limits fields for all printed reports."""
        expected_header = ['xname', 'FRUID', 'Part Number', 'SKU']
        command = f"{self.sat_base_command} hwinv --fields '{','.join(expected_header)}'"
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        stdout_lines = stdout.splitlines()

        # Iterate through the lines to find sections and validate headers
        for i, line in enumerate(stdout_lines):
            # Match section titles like "Listing of all <SOME COMPONENT TYPE>"
            match = re.match(r"Listing of all (.+)", line.strip())
            if match:
                section_name = match.group(1)
                component_type = SECTION_TO_TYPE.get(section_name)
                # If the section doesn't correspond to any present component, skip it
                if component_type not in self.present_components:
                    continue

                self.assertIn(section_name, HWINV_HEADERS,
                    f"Unexpected section '{section_name}' found in output."
                )

                # Get the header line (3 lines below the section title)
                header_line_index = i + 3
                if header_line_index >= len(stdout_lines):
                    self.fail(f"Header row for section '{section_name}' not found in output.")
                header_line = stdout_lines[header_line_index].strip()

                # Parse the actual header
                actual_header = [col.strip() for col in header_line.split("|") if col.strip()]

                # Validate the actual header against the adjusted expected header
                self.assertEqual( expected_header, actual_header,
                    f"Header for section '{section_name}' does not match the expected fields. "
                    f"Expected: {expected_header}, Actual: {actual_header}"
                )


class TestHwinvSummarize(SATTestCase):
    """Tests for the `sat hwinv --summarize-<component>` commands"""

    def setUp(self):
        """Save some lists of expected summary keys for each component type."""
        super().setUp()
        # This is a mapping from the human-readable component type to the keys by which it is summarized
        self.summary_keys = {
            "nodes": [
                "Cabinet Type", "Memory Type", "Memory Device Type", "Memory Manufacturer",
                "Memory Model", "Memory Size (GiB)", "Memory Module Count",
                "Processor Manufacturer", "Processor Model", "Accelerator Count",
                "Accelerator Riser Count", "HSN NIC Count", "Drive Count",
                "Total Drive Capacity (GiB)"
            ],
            "processors": [
                "Manufacturer", "Model", "Total Cores", "Total Threads", "Max Speed (MHz)"
            ],
            "memory modules": [
                "Manufacturer", "Model", "Memory Type", "Device Type",
                "Capacity (MiB)", "Operating Speed (MHz)"
            ]
        }

    def assert_summary_sections(self, output: str, component_type: str,
                                summary_keys: List[str] = None,
                                expect_listing: bool = False):
        """Assert that the expected summary sections are present in the output.

        Args:
            output: the output string to check.
            component_type: the human-readable component type being summarized
            summary_keys: optional list of fields components should be summarized by.
                If omitted, the default summary keys for the component type will be used.
            expect_listing: whether to expect a listing section for the component type
        """
        if summary_keys is None:
            try:
                summary_keys = self.summary_keys[component_type]
            except KeyError:
                self.fail(f'No summary keys defined for component type: {component_type}')

        self.assertIn(f"Summary of all {component_type} in the system", output)
        for key in summary_keys:
            # Counts of <component_type> by <key>
            self.assertRegex(output, rf"Counts of {component_type} by {re.escape(key)}")
            # Table header in the form "| <Key> | Count |"
            header_pattern = rf"\|\s*{re.escape(key)}\s*\|\s*Count\s*\|"
            self.assertRegex(output, header_pattern)
            if expect_listing:
                # Verify at least one listing section for the component type
                list_pattern = rf"Listings of {component_type} by {re.escape(key)}"
                self.assertRegex(output, list_pattern)

    def test_hwinv_summarize_nodes(self) -> None:
        """Test that `sat hwinv --summarize-nodes` outputs summary tables and listings for node attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-nodes'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'nodes', expect_listing=True)

    def test_hwinv_summarize_procs(self) -> None:
        """Test that `sat hwinv --summarize-procs` outputs summary tables for processors attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-procs'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'processors')

    def test_hwinv_summarize_mems(self) -> None:
        """Test that `sat hwinv --summarize-mems` outputs summary tables for memory modules attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-mems'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'memory modules')

    def test_hwinv_summarize_all(self) -> None:
        """Test that `sat hwinv --summarize-all` outputs summary tables for nodes and processors."""
        command = f'{self.sat_base_command} hwinv --summarize-all'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'nodes', expect_listing=True)
        self.assert_summary_sections(stdout, 'processors')
        self.assert_summary_sections(stdout, 'memory modules')

    def test_hwinv_summarize_nodes_fields(self) -> None:
        """Test that `sat hwinv --summarize-nodes --node-summary-fields drivecount,hsnniccount` outputs summary tables and listings for specified node attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-nodes --node-summary-fields drivecount,hsnniccount'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        counts_keys = [
            "Drive Count", "HSN NIC Count"
        ]
        self.assert_summary_sections(stdout, 'nodes', summary_keys=counts_keys, expect_listing=True)

    def test_hwinv_summarize_nodes_count_only(self) -> None:
        """Test that `sat hwinv --summarize-nodes --show-node-xnames off` outputs summary tables for node attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-nodes --show-node-xnames off'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'nodes', expect_listing=False)

    def test_hwinv_summarize_procs_show_xnames(self) -> None:
        """Test that `sat hwinv --summarize-procs --show-proc-xnames` outputs summary tables and listings for processors attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-procs --show-proc-xnames'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'processors', expect_listing=True)

    def test_hwinv_summarize_mems_show_xnames(self) -> None:
        """Test that `sat hwinv --summarize-mems --show-mem-xnames` outputs summary tables and listings for memory modules attributes."""
        command = f'{self.sat_base_command} hwinv --summarize-mems --show-mem-xnames'
        proc = subprocess.run(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        stdout = proc.stdout.decode()
        self.assert_summary_sections(stdout, 'memory modules', expect_listing=True)


if __name__ == "__main__":
    unittest.main()

