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
This script validates IUF manifest.
"""

import sys
import os
from csm_testing.lib.iuf_common import load_yaml, validate_instance

# Constants
# Path to your product manifest schema file
SCHEMA_FILE = "/opt/cray/tests/install/ncn/scripts/iuf_schemas/iuf-manifest-schema.yaml"


# Custom exception for IUF Product Manifest validation errors
class ProductManifestValidationError(Exception):
    """Custom exception for product manifest validation errors."""

def main():
    """
    The main entry point for the program
    Args:
        None
    Returns:
        None
    """
    print("Test Case: validate_iuf_product_manifest")
    if len(sys.argv) != 2:
        print("Usage: validate_product_manifest.py <manifest_file>")
        sys.exit(1)

    manifest_file = sys.argv[1]
    # Load the schema
    try:
        schema = load_yaml(SCHEMA_FILE)
        print("INFO: Schema loaded successfully.")
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Load the product manifest file
    try:
        if os.path.exists(manifest_file):
            manifest_instance = load_yaml(manifest_file)
            print(
                f"INFO: IUF product manifest file '{manifest_file}' loaded successfully."
            )
        else:
            print(f"{manifest_file} : FileNotFoundError")
            sys.exit(1)
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Validate the product manifest file against the schema
    try:
        validate_instance(manifest_instance, schema)
        print(
            f"INFO: SUCCESS: IUF product manifest file \
'{manifest_file}' is valid against the schema."
        )
        print("INFO: SUCCESS: Passed")
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
