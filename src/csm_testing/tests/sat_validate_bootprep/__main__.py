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
import os
from csm_testing.lib.iuf_common import load_yaml, validate_instance

SCHEMA_FILE = "/opt/cray/tests/install/ncn/scripts/iuf_schemas/bootprep-schema.yaml"


class BootPrepValidationError(Exception):
    """Custom exception for BootPrep validation errors."""


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
    try:
        schema = load_yaml(SCHEMA_FILE)
        print("INFO: Schema loaded successfully.")
    except BootPrepValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Load the bootprep file
    try:
        if os.path.exists(bootprep_file):
            bootprep_instance = load_yaml(bootprep_file)
            print(
                f"INFO: Bootprep file '{bootprep_file}' loaded successfully.")
        else:
            print(f"{bootprep_file} : FileNotFoundError")
            sys.exit(1)
    except BootPrepValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Validate the bootprep file against the schema
    try:
        validate_instance(bootprep_instance, schema)
        print(
            f"INFO: SUCCESS: Bootprep file '{bootprep_file}' is valid against the schema."
        )
        print("INFO: SUCCESS: Passed")
    except BootPrepValidationError as err:
        print(f"{err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
