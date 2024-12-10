#
# MIT License
#
# (C) Copyright 2022-2024 Hewlett Packard Enterprise Development LP
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
ResultsEntry class
"""

from typing import Dict

from .duration_seconds import DurationSeconds


class ResultsEntry:
    """
    An entry in the test results list
    """

    def __init__(self, result_entry_raw: Dict):
        self.result_raw = result_entry_raw["result"]
        self.title = result_entry_raw["title"]
        self.summary = result_entry_raw["summary-line"]
        self.duration_seconds = DurationSeconds(result_entry_raw["duration"])
        self.resource = result_entry_raw["resource-id"]
        self.description = result_entry_raw["meta"]["desc"]
        if self.result_raw == 0:
            # Test passed
            self.result_string = "PASS"
        elif self.result_raw == 1:
            # Test failed
            self.result_string = "FAIL"
        elif self.result_raw == 2:
            # Test was skipped (this is not usually due to error)
            self.result_string = "SKIPPED"
        else:
            # This should never happpen
            self.result_string = f"UNKNOWN (Goss result = {self.result_raw})"

    def multiline_string(self, source: str, node_name: str) -> str:
        """
        Return a string of the results formatted as a multi-line string,
        followed by a blank line
        """
        return (f"Result: {self.result_string}\n"
                f"Source: {source}\n"
                f"Test Name: {self.title}\n"
                f"Description: {self.description}\n"
                f"Test Summary: {self.summary}\n"
                f"Execution Time: {self.duration_seconds} seconds\n"
                f"Node: {node_name}\n\n")

    def dict(self, source: str, node_name: str) -> dict:
        """
        Return the results in dict format.

        To avoid JSON printing the seconds duration in scientific notation (which causes problems
        for the grok exporter that parses the log), we record it here as a string in the
        non-scientific format.
        """
        return {
            "Result Code": self.result_raw,
            "Result String": self.result_string,
            "Source": source,
            "Test Name": self.title,
            "Description": self.description,
            "Test Summary": self.summary,
            "Execution Time (seconds)": self.duration_seconds,
            "Execution Time (nanoseconds)":
            self.duration_seconds.to_nanoseconds(),
            "Node": node_name
        }
