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
Defines utility functions used across the sat_functional tests
"""
import json
import sys
import yaml


class SatTestingUtils:

    @staticmethod
    def validate_json(json_string: str) -> bool:
        """
        Validates a json string

        Args:
            json_string (str): string containing json

        Returns:
            bool: True if json is valid false otherwise
        """
        try:
            json.loads(json_string)
            return True
        except json.JSONDecodeError as err:
            sys.stderr.write(f'Unable to load json with error: {err}')
            return False

    @staticmethod
    def validate_yaml(yaml_string: str) -> bool:
        """
        Validates a yaml string

        Args:
            yaml_string (str): string containing yaml

        Returns:
            bool: True if yaml is valid false otherwise
        """
        try:
            yaml.safe_load(yaml_string)
            return True
        except yaml.YAMLError as err:
            sys.stderr.write(f'Unable to load yaml with error: {err}')
            return False
