#!/usr/bin/env python3

# MIT License
#
# (C) Copyright [2024] Hewlett Packard Enterprise Development LP
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

import argparse
import datetime
import logging
import os.path

import subprocess
import sys
import yaml

from typing import List
from typing import AnyStr

from collections import namedtuple


def run_cmd(command: List[str], stdin=None, wait=True) -> subprocess.CompletedProcess:
    if stdin:
        cmd = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        cmd = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if wait:
        cmd.wait()
    return cmd


def write_config(out_dir: str, src_dir: str, xname: str) -> str:
    log_dir = get_log_dir(out_dir)
    data = dict(
        out_dir=out_dir,
        src_dir=src_dir,
        log_dir=log_dir,
        node=xname,
        is_vshasta=False, # todo
    )

    config_filename = os.path.join(out_dir, "config.yaml")
    with open(config_filename, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)

    return config_filename


def list_tests(src_dir: str) -> tuple[list[str], list[str]]:
    test_dir = os.path.join(src_dir, "tests")
    tests = []
    if os.path.isdir(test_dir):
        tests = os.listdir(test_dir)
        tests = [t.removesuffix('.yaml') for t in tests if not t.endswith(('-setup.yaml', '-teardown.yaml', '-config.yaml'))]
    else:
        logger.debug(f"Tests directory not present: {test_dir}")

    suites_dir = os.path.join(src_dir, "suites")
    suites = []
    if os.path.isdir(suites_dir):
        suites = os.listdir(suites_dir)
        suites = [s.removesuffix('.yaml') for s in suites if not s.endswith(('-setup.yaml', '-teardown.yaml', '-config.yaml'))]
    else:
        logger.debug(f"Suites directory not present: {suites_dir}")

    return tests, suites


# tuple with two file paths.
# setup - path to the setup file. This can be empty.
# test - path to the goss test file
TestFiles = namedtuple('TestFiles', 'config setup test teardown')


def run_test(commands: list[list[str]]) -> None:
    for command in commands:
        logger.info(f"run: {' '.join(command)}")
        result = run_cmd(command)
        output = result.communicate()
        logger.info(output[0].decode("utf-8"))
        logger.info(output[1].decode("utf-8"))


def get_test_files(src_dir: str, test_name: str) -> TestFiles:
    test_dir = os.path.join(src_dir, "tests")
    tests = os.listdir(test_dir)

    config_file = ""
    setup_file = ""
    test_file = ""
    teardown_file = ""
    for test in tests:
        if test.startswith(test_name):
            if test.endswith("-config.yaml"):
                config_file = os.path.join(test_dir, test)
            elif test.endswith("-setup.yaml"):
                setup_file = os.path.join(test_dir, test)
            elif test.endswith("-teardown.yaml"):
                teardown_file = os.path.join(test_dir, test)
            elif test.endswith(".yaml"):  # this must be the last check
                test_file = os.path.join(test_dir, test)
    return TestFiles(config_file, setup_file, test_file, teardown_file)


def get_src_dir() -> AnyStr:
    return os.path.dirname(os.path.abspath(__file__))


def get_out_dir(out_dir="") -> AnyStr:
    if out_dir:
        return out_dir
    else:
        return os.path.join("/var/log/csm-ct")


def get_log_dir(out_dir: str) -> str:
    t = datetime.datetime.now()
    timestamp = t.strftime('%Y%m%d-%H%M%S')
    return os.path.join(out_dir, timestamp)


def create_commands(test_files: TestFiles, config_file: str) -> list[list[str]]:
    commands = []
    if test_files.setup:
        if '-ansible' in test_files.setup:
            commands.append(["ansible-playbook", test_files.setup])
        else:
            commands.append(["goss", "--vars", config_file, "-g", test_files.setup, "validate"])
    if test_files.test:
        if '-ansible' in test_files.test:
            commands.append(["ansible-playbook", test_files.test])
        else:
            commands.append(["goss", "--vars", config_file, "-g", test_files.test, "validate"])
    if test_files.teardown:
        if '-ansible' in test_files.teardown:
            commands.append(["ansible-playbook", test_files.teardown])
        else:
            commands.append(["goss", "--vars", config_file, "-g", test_files.teardown, "validate"])

    return commands


def setup_logger(level: int =logging.INFO) -> None:
    logger.setLevel(level)

    standard_out = logging.StreamHandler(sys.stdout)
    standard_out.setLevel(level)
    logger.addHandler(standard_out)


def exec_list_option(args: argparse.Namespace) -> None:
    print(f"TRACE {type(args)}")
    src_dir = get_src_dir()
    tests, suites = list_tests(src_dir)

    if tests:
        logger.info("Tests:")
        for test in tests:
            logger.info(f"    {test}")
    else:
        logger.info("Tests: None")

    if suites:
        logger.info("Suites:")
        for suite in suites:
            logger.info(f"    {suite}")
    else:
        logger.info("Suites: None")


def exec_create_config_option(args: argparse.Namespace) -> None:
    src_dir = get_src_dir()
    out_dir = get_out_dir(args.out_dir)
    config_file = write_config(out_dir, src_dir, args.xname)
    logger.info(f"config: {config_file}")

    logger.info("")
    logger.info("test commands:")
    tests, suites = list_tests(src_dir)
    for test in tests:
        test_files = get_test_files(src_dir, test)
        commands = create_commands(test_files, config_file)
        for command in commands:
            logger.info(' '.join(command))


def exec_run_option(args: argparse.Namespace) -> None:

    src_dir = get_src_dir()
    if args.config:
        config_file = args.config
    else:
        out_dir = get_out_dir(args.out_dir)
        config_file = write_config(out_dir, src_dir, args.xname)
    logger.debug(f"config: {config_file}")

    if args.test:
        test_files = get_test_files(src_dir, args.test)
        logger.debug(f"test setup file: {test_files.setup}")
        logger.debug(f"test file: {test_files.test}")
        commands = create_commands(test_files, config_file)
        run_test(commands)
    # else
    # todo raise exception


def exec_prune_option(args: argparse.Namespace) -> None:
    logger.info("prune is not implemented yet")


def main(argslist=None):
    """ main function """

    parser = argparse.ArgumentParser(description='CSM CT Tests.')
    parser.add_argument("command", help="The command to run", choices=["list", "create-config", "run", "prune"], nargs="?")
    parser.add_argument("--xname", help="Node xname")
    parser.add_argument("-a", "--all", help="All tests")
    parser.add_argument("-t", "--test", help="Name of the test to run")
    parser.add_argument("-o", "--out-dir", help="Base directory where the logs and test output is placed", default="/opt/cray/tests/install/logs")
    parser.add_argument("-c", "--config", help="The config file for the tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument("-s", "--simulator", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argslist)

    if args.verbose:
        setup_logger(logging.DEBUG)
    else:
        setup_logger(logging.INFO)

    if args.command == "list":
        exec_list_option(args)
    elif args.command == "create-config":
        exec_create_config_option(args)
    elif args.command == "run":
        exec_run_option(args)
    elif args.command == "prune":
        exec_prune_option(args)

    return 0


# Entry code

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    r = main()
    sys.exit(r)

