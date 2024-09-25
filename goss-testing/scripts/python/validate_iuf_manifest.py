#!/usr/bin/env python3
#
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

import yaml
import jsonschema
from jsonschema import validate, ValidationError, SchemaError
import sys

# Constants
SCHEMA_FILE = "/opt/cray/tests/install/dat/iuf/iuf-manifest-schema.yaml"  # Path to your product manifest schema file

# Custom exception for IUF Product Manifest validation errors
class ProductManifestValidationError(Exception):
    """Custom exception for product manifest validation errors."""
    pass

def load_yaml(file_path):
    """Load a YAML file and return the parsed data."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as err:
        raise ProductManifestValidationError(f"ERROR: Error loading YAML file {file_path}: {err}")
    except FileNotFoundError as err:
        raise ProductManifestValidationError(f"ERROR: File not found: {file_path}")
    except Exception as err:
        raise ProductManifestValidationError(f"ERROR: Error reading file {file_path}: {err}")

def validate_instance(instance, schema):
    """Validate the instance data against the schema."""
    try:
        validate(instance=instance, schema=schema)
    except ValidationError as err:
        raise ProductManifestValidationError(f"ERROR: Validation failed: {err.message}")
    except SchemaError as err:
        raise ProductManifestValidationError(f"ERROR: Schema error: {err.message}")

def main(manifest_file):
    # Load the schema
    try:
        schema = load_yaml(SCHEMA_FILE)
        print("INFO: Schema loaded successfully.")
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Load the product manifest file
    try:
        manifest_instance = load_yaml(manifest_file)
        print(f"INFO: IUF product manifest file '{manifest_file}' loaded successfully.")
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)

    # Validate the product manifest file against the schema
    try:
        validate_instance(manifest_instance, schema)
        print(f"SUCCESS: IUF product manifest file '{manifest_file}' is valid against the schema.")
        print("SUCCESS: Passed")
    except ProductManifestValidationError as err:
        print(f"{err}")
        sys.exit(1)

if __name__ == "__main__":
    print("Test Case: validate_iuf_product_manifest")
    if len(sys.argv) != 2:
        print("Usage: validate_product_manifest.py <manifest_file>")
        sys.exit(1)

    manifest_file = sys.argv[1]
    main(manifest_file)
