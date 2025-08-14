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


def validate_json(json_string: str) -> json:
    """
    Validates a json string and returns the validated json

    Args:
        json_string (str): string containing json

    Returns:
        json: a json object
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as err:
        sys.stderr.write(f'Unable to decode json with error: {err}')
        assert False, f"The provided string is not valid json: {json_string}"


def validate_yaml(yaml_string: str) -> yaml:
    """
    Validates a yaml string and returns the validated yaml

    Args:
        yaml_string (str): string containing yaml.

    Returns:
        yaml: a yaml object.
    """
    try:
        return yaml.safe_load(yaml_string)
    except yaml.YAMLError as err:
        sys.stderr.write(f'Unable to load yaml with error: {err}')
        assert False, f"The provided string is not valid yaml: {yaml_string}"

