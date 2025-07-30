#
# MIT License
#
# (C) Copyright 2024-2025 Hewlett Packard Enterprise Development LP
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
Functional tests for the System Admin Toolkit (SAT).

This script is a thin wrapper around the unittest module. This script is used
instead of directly using `python -m unittest` because the build scripts in this
repository install this script in the Python virtual environment in which the
csm_testing module is installed and then create a symlink to the script. This
script will thus be able to automatically find the unittest test cases defined
in the directories within this directory.

This script also prepends the arguments it's given with the parent package name
in order to shorten the calls made in the Goss test files.

For example:

  `python -m unittest csm_testing.tests.sat_functional.version.TestVersion.test_version`

becomes:

  `sat_functional version.TestVersion.test_version`
"""
import argparse
import sys
import unittest
import os


os.environ['CRAY_FORMAT'] = 'json'


def create_parser() -> argparse.ArgumentParser:
    """Create a parser that accepts a list of test identifiers to run.

    Returns:
        The parser object.
    """
    parser = argparse.ArgumentParser(
        description='Run the specified functional tests for the System Admin Toolkit (SAT).')
    parser.add_argument(
        'tests', nargs='+',
        help='The names of the tests to run. These should be the names of the '
             'test modules, test classes, or test methods to run, relative to the '
             'csm_testing.tests.sat_functional package.'
    )
    return parser


def main() -> None:
    """Execute the specified unit tests and exit with the appropriate status code.

    Raises:
        SystemExit: The exit code is set to 0 if all tests pass, 1 otherwise.
    """
    parser = create_parser()
    args = parser.parse_args()

    suite = unittest.TestSuite()

    for test in args.tests:
        # Prefix each test name with the path to the sat_functional package
        tests = unittest.TestLoader().loadTestsFromName(
            f'csm_testing.tests.sat_functional.{test}'
        )
        suite.addTests(tests)

    # Run the test suite with a verbosity of 2 so it will print the name of each
    # test being executed.
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
