#! /usr/bin/env python3
#  Copyright 2021 Hewlett Packard Enterprise Development LP

"""
This script verifies that the services required to monitor and interact with
console logs are up and ready in the k8s cluster.
"""

import os
import logging
import subprocess
import sys

import yaml

DEFAULT_LOG_LEVEL = os.environ.get("LOG_LEVEL", logging.INFO)
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

# set up logging to file
logFilePath = '/tmp/' + sys.argv[0].split('/')[-1] + '.log'
file_handler = logging.FileHandler(filename=logFilePath)
file_handler.setLevel(os.environ.get("FILE_LOG_LEVEL", DEFAULT_LOG_LEVEL))
logger.addHandler(file_handler)

# set up logging to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(os.environ.get("CONSOLE_LOG_LEVEL", DEFAULT_LOG_LEVEL))
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Service names expected to be found
EXPECTED_SERVICES = {
    "cray-console-operator",
    "cray-console-node-0",
    "cray-console-data"
}

# filter out the postgres pods
POSTGRES_FILTER = "postgres"

class ConsoleException(Exception):
    pass

# Make sure all required pods are present
def get_console_pods():
    # create a mapping of expected services to an actual running pod
    foundPods = dict()
    try:
        logger.debug("Getting list of pods in the services namespace.")
        command_line = ['kubectl', 'get', 'pods', '-n', 'services', '-o', 'name']
        result = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        for pod in result.splitlines():
            for expected in EXPECTED_SERVICES:
                if expected in pod.lower() and not POSTGRES_FILTER in pod.lower():
                    # result is prefaced with "pod/". We want to strip that off.
                    foundPods[expected] = pod[4:]
                    break
    except subprocess.CalledProcessError as err:
        logger.error(f"Could not list service pods. Got exit code {err.returncode}. Msg: {err.output}")
        raise ConsoleException

    # verify all expected services have a pod running
    if not len(foundPods) == len(EXPECTED_SERVICES):
        logger.error(f"The console pods in the services namespace did not match what was expected.")
        logger.error(f"Expected services: {EXPECTED_SERVICES}")
        logger.error(f"Found pods: {foundPods}")
        raise ConsoleException

    return foundPods

def check_pod_status(pods):
    # Make sure that each pod is running
    try:
        logger.debug("Checking status of console pods")
        for k,v in pods.items():
            # Get the current status of the pod
            command_line = ['kubectl', 'get', 'pods', v, '-n', 'services', '--no-headers', '-o' ,'custom-columns=:status.phase']
            result = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8").strip()

            # check that it is running
            if result.lower() != "running":
                logger.error(f"Service not Ready: {k}:{v} - ,{result}")
                raise ConsoleException
    except subprocess.CalledProcessError as err:
        logger.error(f"Could not list service pods. Got exit code {err.returncode}. Msg: {err.output}")
        raise ConsoleException

def main():
    try:
        return_value = True
        logger.info("Beginning verification that all console services are running")

        # Find that all services are present
        pods = get_console_pods()

        # Check the status of the pods
        check_pod_status(pods)

        logger.info("Verification of console services succeeded")
        return 0
    except ConsoleException:
        return 1
    except Exception as exc:
        logger.error(f"Unexpected error verifying console services.", exc_info=exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
