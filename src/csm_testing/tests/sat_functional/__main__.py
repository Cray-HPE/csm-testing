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
import json
import os
import sys
from typing import List
import unittest

from yaml import safe_dump

TEST_PACKAGE = 'csm_testing.tests.sat_functional'


def get_test_case_names() -> List[str]:
    """Get a list of all the unittest.TestCase classes in the sat_functional package.

    Returns:
        The sorted list of the unittest.TestCase class names, relative to the TEST_PACKAGE.

    Raises:
        RuntimeError: If a discovered test case does not start with the TEST_PACKAGE name.
    """
    def get_test_cases_from_suite(suite: unittest.TestSuite) -> List[str]:
        """Recursively get all test ids from a TestSuite"""
        test_cases = []
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                test_cases.extend(get_test_cases_from_suite(item))
            elif isinstance(item, unittest.TestCase):
                test_cases.append(item.id())
        return test_cases

    loader = unittest.TestLoader()
    main_suite = loader.discover(TEST_PACKAGE)
    full_test_names = get_test_cases_from_suite(main_suite)

    rel_test_names = set()
    for test_name in full_test_names:
        if test_name.startswith(TEST_PACKAGE + '.'):
            # Strip off the TEST_PACKAGE name from the beginning and the test method name from the end
            rel_test_names.add(test_name[len(TEST_PACKAGE) + 1:].rsplit('.', maxsplit=1)[0])
        else:
            raise RuntimeError(f'Discovered test case "{test_name}" does not start with "{TEST_PACKAGE}"')

    return sorted(list(rel_test_names))


def list_tests(parsed_args: argparse.Namespace) -> None:
    """Print the names of all available test cases.

    Args:
        parsed_args (argparse.Namespace): The parsed arguments from the command line.
    """
    test_case_names = get_test_case_names()
    if parsed_args.format == 'json':
        print(json.dumps({'sat_tests': test_case_names}))
    elif parsed_args.format == 'yaml':
        print(safe_dump({'sat_tests': test_case_names}, default_flow_style=False, sort_keys=False))
    else:
        for name in test_case_names:
            print(name)


def run_tests(parsed_args: argparse.Namespace) -> None:
    """Run the specified tests or all tests if none are specified.

    Args:
        parsed_args (argparse.Namespace): The parsed arguments from the command line.

    Raises:
        SystemExit: The exit code is set to 0 if all tests pass, 1 otherwise.
    """
    if not parsed_args.tests:
        # If no tests are specified, run all tests.
        suite = unittest.TestLoader().discover(TEST_PACKAGE)
    else:
        # Load the specified tests.
        suite = unittest.TestSuite()
        for test in parsed_args.tests:
            tests = unittest.TestLoader().loadTestsFromName('.'.join([TEST_PACKAGE, test]))
            suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create a parser that accepts a list of test identifiers to run.

    Returns:
        The parser object.
    """
    parser = argparse.ArgumentParser(
        description='Functional tests for the System Admin Toolkit (SAT).')
    subparsers = parser.add_subparsers(
        title='action', description='Action to perform.'
    )

    list_parser = subparsers.add_parser('list', help='List all available test cases.')
    list_parser.add_argument(
        '--format', choices=['text', 'json', 'yaml'], default='text',
        help='Format to display the list of test cases. The "text" format prints one '
             'test case name per line, while the "json" format outputs a JSON array of '
             'test case names. Defaults to "text".'
    )
    list_parser.set_defaults(func=list_tests)

    run_parser = subparsers.add_parser('run', help='Run the specified tests.')
    run_parser.add_argument(
        'tests', nargs='*',
        help='The names of the tests to run. These should be the names of the '
             'test modules, test classes, or test methods to run, relative to the '
             f'{TEST_PACKAGE} package. If omitted, all tests will be run.'
    )
    run_parser.set_defaults(func=run_tests)

    return parser


def main() -> None:
    """Execute the specified unit tests and exit with the appropriate status code.

    Raises:
        SystemExit: The exit code is set to 0 if all tests pass, 1 otherwise.
    """
    parser = create_parser()
    parsed_args = parser.parse_args()

    # Ensure that all `cray` CLI commands default to JSON output. This is even important
    # for the `list` command, which is used to list available tests because when it discovers
    # the tests, it runs any `setUpClass` methods in the test cases, which may use the `cray` CLI.
    os.environ['CRAY_FORMAT'] = 'json'

    if not hasattr(parsed_args, 'func'):
        # Needed because required=True is not supported for subparsers in argparse in Python 3.6
        parser.print_help()
        sys.exit(1)

    parsed_args.func(parsed_args)


if __name__ == '__main__':
    main()
