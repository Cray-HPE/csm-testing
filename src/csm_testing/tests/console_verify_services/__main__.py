#
# MIT License
#
# (C) Copyright 2021-2022, 2024 Hewlett Packard Enterprise Development LP
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
This script verifies that the services required to monitor and interact with
console logs are up and ready in the k8s cluster.
"""

import os
import logging
import sys

from kubernetes import client, config

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
console_handler.setLevel(os.environ.get("CONSOLE_LOG_LEVEL",
                                        DEFAULT_LOG_LEVEL))
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Service names expected to be found
EXPECTED_SERVICES = {
    "cray-console-operator", "cray-console-node", "cray-console-data"
}

# filter out the postgres pods
POSTGRES_FILTER = "postgres"


class ConsoleException(Exception):
    pass


def check_services_running():
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    found_pods = {}
    k8s_v1 = client.CoreV1Api()
    ret = k8s_v1.list_pod_for_all_namespaces(watch=False)
    for item in ret.items:
        pod_name = item.metadata.name.lower()
        for expected in EXPECTED_SERVICES:
            if expected not in pod_name:
                continue
            if POSTGRES_FILTER in pod_name:
                continue
            # record that we found a pod for the expected service
            logger.debug("Checking %s : %s", item.metadata.name,
                         item.status.phase)
            found_pods[expected] = item.metadata.name

            # need to look at that state of each container - the item.status.phase lies...
            okay = True
            for ctr in item.status.container_statuses:
                # Note: when a container is in back-off state, it may either be in
                #  'waiting' or 'terminated' state - consider either an error and
                #  gather what information we can.
                if ctr.ready is True:
                    continue
                if ctr.state.terminated is not None:
                    logger.error(
                        "Pod: %s Container Terminated: %s, Exit Code: %d, "
                        "Reason: %s, Message: %s", item.metadata.name,
                        ctr.name, ctr.state.terminated.exit_code,
                        ctr.state.terminated.reason,
                        ctr.state.terminated.message)
                    okay = False
                if ctr.state.waiting is not None:
                    logger.error("Pod: %s Container: %s, %s: %s",
                                 item.metadata.name, ctr.name,
                                 ctr.state.waiting.reason,
                                 ctr.state.waiting.message)
                    okay = False

            if not okay:
                raise ConsoleException()

    # check that all expected services have been found
    if len(found_pods) != len(EXPECTED_SERVICES):
        logger.error(
            "The console pods in the services namespace did not match what was expected."
        )
        logger.error("Expected services: %s", EXPECTED_SERVICES)
        logger.error("Found pods: %s", found_pods)
        raise ConsoleException()


def main() -> int:  # pylint: disable=missing-function-docstring
    try:
        logger.info(
            "Beginning verification that all console services are running")

        # Find that all services are present
        check_services_running()

        logger.info("Verification of console services succeeded")
        return 0
    except ConsoleException:
        return 1
    except Exception as exc:
        logger.error("Unexpected error verifying console services.",
                     exc_info=exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
