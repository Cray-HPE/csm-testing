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
import subprocess
import os


def validate_manifest_with_podman(manifest_file, cray_nls_image):
    """
    Validate the manifest file using the podman command.
    Args:
        manifest_file (str): Path to the manifest file
        cray_nls_image (str): CRAY_NLS_IMAGE to use for validation
    Returns:
        None
    Raises:
        RuntimeError: If podman command fails
    """
    try:
        # Ensure the manifest file exists
        if not os.path.exists(manifest_file):
            print(f"ERROR: Manifest file '{manifest_file}' not found.")
            sys.exit(1)

        manifest_basename = os.path.basename(manifest_file)

        # Construct the podman command
        cmd = [
            "podman",
            "run",
            "--rm",
            "--userns",
            "keep-id",
            "-v",
            f"{os.path.realpath(manifest_file)}:/{manifest_basename}",
            cray_nls_image,
            "validate",
            f"/{manifest_basename}",
        ]

        print(f"INFO: Running podman command for validation:\n{' '.join(cmd)}")

        # Run the podman command
        subprocess.run(cmd, check=True)
        print("INFO: SUCCESS: IUF product manifest file is valid.")
    except subprocess.CalledProcessError as err:
        raise RuntimeError(f"ERROR: Schema validation failed: {err}") from err


def main():
    """
    Main entry point for the program.
    """
    print("Test Case: validate_iuf_product_manifest")
    if len(sys.argv) != 2:
        print("Usage: validate_product_manifest.py <manifest_file>")
        sys.exit(1)

    manifest_file = sys.argv[1]

    try:
        cray_nls_image = (
            "arti.hpc.amslabs.hpecorp.net/csm-docker-remote/stable/cray-nls:0.10.0"
        )

        # Validate the manifest file using podman
        validate_manifest_with_podman(manifest_file, cray_nls_image)

    except (RuntimeError, ValueError) as err:
        print(err)
        sys.exit(1)


if __name__ == "__main__":
    main()
