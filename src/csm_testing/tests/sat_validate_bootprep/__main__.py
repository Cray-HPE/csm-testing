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
This script validates bootprep file.
"""

import sys
import subprocess
import os
import yaml
from jsonschema import validate, ValidationError, SchemaError


class BootPrepValidationError(Exception):
    """Custom exception for BootPrep validation errors."""


class ManifestValidationError(Exception):
    """Custom exception for validation errors."""


def load_yaml(file_path):
    """Load a YAML file and return the parsed data."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except yaml.YAMLError as err:
        raise ManifestValidationError(
            f"ERROR: Error loading YAML file {file_path}: {err}"
        ) from err
    except FileNotFoundError as err:
        raise ManifestValidationError(
            f"ERROR: File not found: {file_path}: {err}"
        ) from err
    except Exception as err:
        raise ManifestValidationError(
            f"ERROR: Error reading file {file_path}: {err}"
        ) from err


def validate_instance(instance, schema):
    """Validate the instance data against the schema."""
    try:
        validate(instance=instance, schema=schema)
    except ValidationError as err:
        raise ManifestValidationError(f"ERROR: Validation failed: {err}") from err
    except SchemaError as err:
        raise ManifestValidationError(f"ERROR: Schema error: {err}") from err


def get_bootprep_schema():
    """
    Retrieve the bootprep schema using the 'sat bootprep view-schema' command.
    Returns:
        dict: Parsed schema YAML as a dictionary.
    Raises:
        BootPrepValidationError: If the command fails or returns invalid YAML.
    """
    try:
        result = subprocess.run(
            ["sat", "bootprep", "view-schema"],
            check=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("INFO: Schema retrieved successfully using 'sat bootprep view-schema'.")
        yaml_output = yaml.safe_load(result.stdout)
        return yaml_output
    except subprocess.CalledProcessError as err:
        raise BootPrepValidationError(
            f"ERROR: Failed to execute 'sat bootprep view-schema'. {err.stderr}"
        ) from err
    except Exception as err:
        raise BootPrepValidationError(f"ERROR: Failed to parse schema. {err}") from err


def main():
    """
    The main entry point of the program.
    Args:
        None
    Return:
        None
    """
    if len(sys.argv) != 2:
        print("Usage: validate_bootprep.py <bootprep_file>")
        sys.exit(1)

    bootprep_file = sys.argv[1]
    # Fetch the schema
    try:
        schema = get_bootprep_schema()
    except BootPrepValidationError as err:
        print(err)
        sys.exit(1)

    # Load the bootprep file
    try:
        if os.path.exists(bootprep_file):
            bootprep_instance = load_yaml(bootprep_file)
            print(f"INFO: Bootprep file '{bootprep_file}' loaded successfully.")
        else:
            print(f"{bootprep_file} : FileNotFoundError")
            sys.exit(1)
    except BootPrepValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Validate the bootprep file against the schema
    try:
        validate_instance(bootprep_instance, schema)
        print(f"SUCCESS: Bootprep file '{bootprep_file}' is valid against the schema.")
        print("SUCCESS: Test Case Passed")
    except BootPrepValidationError as err:
        print(f"{err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
