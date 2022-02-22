#! /usr/bin/env python3
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP.
#
# MIT License
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

"""
This script verifies that the dependent images referenced in the IMS Job templates
are available from the packages.local repository.
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

SKOPEO_IMAGE = "quay.io/skopeo/stable:latest"
DOCKER_REGISTRY = "docker://dtr.dev.cray.com"
VALIDATE_PACKER_IMAGES = False

EXPECTED_CONFIGMAPS = {
    "ims-config",
    "cray-configmap-ims-v2-image-create-kiwi-ng",
    "cray-configmap-ims-v2-image-create-packer",
    "cray-configmap-ims-v2-image-customize"
}


class ImsException(Exception):
    pass


def ims_configmaps():
    configmaps = set()
    try:
        logger.debug("Getting list of configmaps in the services namespace.")
        command_line = ['kubectl', 'get', 'cm', '-n', 'services', '-o', 'name']
        result = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        logger.debug(result)
        for cm in result.splitlines():
            if "ims" in cm.lower():
                # result is prefaced with "configmap/". We want to strip that off.
                configmaps.add(cm[10:])
    except subprocess.CalledProcessError as err:
        logger.error(f"Could not list IMS configmaps. Got exit code {err.returncode}. Msg: {err.output}")
        raise ImsException

    if not configmaps == EXPECTED_CONFIGMAPS:
        logger.error(f"The IMS configmaps in the services namespace did not match what was expected.")
        logger.error(f"Found Configmaps: {configmaps}")
        logger.error(f"Expected Configmaps: {EXPECTED_CONFIGMAPS}")
        raise ImsException

    for configmap in configmaps:
        if configmap.lower().startswith("cray-configmap-ims"):
            if VALIDATE_PACKER_IMAGES or "packer" not in configmap.lower():
                yield configmap


def cm_dependent_images(cm):
    dependent_images = set()
    try:
        logger.info(f"Validating {cm} configmap")
        command_line = ['kubectl', 'get', 'cm', '-n', 'services', '-o', 'yaml', cm]
        response = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        logger.debug(response)
        configmap = yaml.safe_load(response)
        for resource_name in configmap["data"]:
            resource = yaml.safe_load(configmap["data"][resource_name])
            if resource["kind"] == "Job":
                for container_group in ['initContainers', 'containers']:
                    for container in resource["spec"]["template"]["spec"][container_group]:
                        dependent_images.add(container["image"])
    except subprocess.CalledProcessError as err:
        logger.error(f"Could not retrieve IMS configmap {cm}. Got exit code {err.returncode}. Msg: {err.output}")
        raise ImsException

    for dependent_image in dependent_images:
        logger.info(f"  - Configmap references the image {dependent_image}")
        yield dependent_image


def validate_dependent_image_exists(dependent_image):
    try:
        logger.debug(f"Validating that the image {dependent_image} exists in the packages.local repo")
        command_line = ["podman", "run", "--rm", SKOPEO_IMAGE, "inspect", '/'.join([DOCKER_REGISTRY, dependent_image])]
        response = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        logger.info(f"    * Verified that the image {dependent_image} exists in the local docker registry.")
        logger.debug(response)
        return True
    except subprocess.CalledProcessError as err:
        logger.error(f"Could not validate the image {dependent_image}. "
                     f"Got exit code {err.returncode}. Msg: {err.output}")
        return False


def main():
    try:
        return_value = True
        logger.info("Beginning verification that IMS dependent images are available in the local docker registry")
        for cm in ims_configmaps():
            for dependent_image in cm_dependent_images(cm):
                return_value = return_value and validate_dependent_image_exists(dependent_image)

        if not return_value:
            logger.error("Validation of IMS dependent images failed")
            return 1

        logger.info("Validation of IMS dependent images succeeded")
        return 0
    except ImsException:
        return 1
    except Exception as exc:
        logger.error(f"Unexpected error validating dependent IMS images.", exc_info=exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
