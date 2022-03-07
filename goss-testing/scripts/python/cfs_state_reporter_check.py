#! /usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
This script validates that cfs-state-reporter ran and completed successfully.
"""

import os
import logging
import subprocess
import sys
import time

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

myname = sys.argv[0].split('/')[-1]
# Strip off .py, if present
if myname[-3:] == ".py":
    myname = myname[:-3]

# set up logging to file
logFileDir = "/opt/cray/tests"
logFilePath = f"{logFileDir}/{myname}.log"
file_handler = logging.FileHandler(filename=logFilePath)
file_handler.setLevel(os.environ.get("FILE_LOG_LEVEL", logging.DEBUG))
logger.addHandler(file_handler)

# set up logging to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(os.environ.get("CONSOLE_LOG_LEVEL", logging.INFO))
formatter = logging.Formatter(f"{myname}: %(levelname)-8s %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class CfsTestException(Exception):
    pass

def get_systemctl_data():
    # Need to include --all so that empty properties are also listed
    command_line = [ "/usr/bin/systemctl", "--all", "--no-pager", "show", "cfs-state-reporter" ]
    logger.info(f"Running command: {' '.join(command_line)}")
    result = subprocess.run(command_line, stdout=subprocess.PIPE, check=True)
    logger.info(f"Command completed with return code {result.returncode}")
    
    # Each line of output should be of the form FieldName=<value>
    # We will load this into a dictionary, and return that
    # This could be done in fewer lines of code, but clarity is preferable
    output_lines = result.stdout.decode('utf-8').splitlines()
    output_dict = dict()
    for line in output_lines:
        logger.debug(f"output line: {line}")

        # Split the line by = characters into a list of strings
        split_line = line.split("=")

        # The first string is the name of the field
        field_name = split_line[0]

        # I am not certain if the values are permitted to have = characters in them.
        # To be cautious, I will assume that it is possible, as it will not cause any
        # problems.
        value_name = "=".join(split_line[1:])

        # Add this key/value pair to our dictionary
        output_dict[field_name] = value_name
    return output_dict

def get_service_data_fields():
    # This function runs systemctl to obtain data on the cfs-state-reporter service. Provided that service
    # has run and completed, this function returns the following fields from the systemctl output:
    # ExecMainStatus
    # LoadState
    # ActiveState
    # SubState
    # Result

    attempts=0
    # We have this loop on the off chance that the systemctl command is run while the cfs-state-reporter
    # service is still executing. In that case, because we wish to check the results of the service after
    # it has finished executing, we attempt to retry the systemctl command a few times before giving up.
    while attempts < 3:
        if attempts > 0:
            # If this is not the first attempt, sleep 2 seconds before trying
            logger.info("Will retry systemctl command after 2 seconds.")
            time.sleep(2)
        print("")
        service_data = get_systemctl_data()

        def get_field_value(field_name):
            try:
                field_value = service_data[field_name]
                logger.info(f"{field_name} = {field_value}")
                return field_value
            except KeyError:
                logger.error(f"Expected field missing from systemctl output: {field_name}")
                return None

        errors = False
        srv_start_time = get_field_value("ExecMainStartTimestamp")
        if srv_start_time == None:
            errors=True

        srv_exit_time = get_field_value("ExecMainExitTimestamp")
        if srv_exit_time == None:
            errors=True

        srv_exit_status = get_field_value("ExecMainStatus")
        if srv_exit_status == None:
            errors=True

        srv_load_state = get_field_value("LoadState")
        if srv_load_state == None:
            errors=True

        srv_active_state = get_field_value("ActiveState")
        if srv_active_state == None:
            errors=True

        srv_substate = get_field_value("SubState")
        if srv_substate == None:
            errors=True

        srv_result = get_field_value("Result")
        if srv_result == None:
            errors=True

        # If any of our expected fields were missing, that is a problem
        if errors:
            logger.error("One or more expected fields are missing from systemctl output")
            raise CfsTestException

        if srv_exit_time:
            # A non-empty exit time means that the service has run to completion, so we can return the fields to the function
            # caller
            return srv_exit_status, srv_load_state, srv_active_state, srv_substate, srv_result
        elif srv_start_time:
            # A non-empty start time means that the service has started. Combined with the empty exit time, this indicates
            # it is currently running. It usually takes less than 1 second to execute, so waiting for 2 seconds should be
            # sufficient.
            logger.warn("cfs-state-reporter is currently running.")
            attempts+=1
            continue

        # If we reach this point it means that both start time and exit times are empty. This is not good.
        logger.error("According to systemctl, the cfs-state-reporter service has never started")
        raise CfsTestException
    # If we reach here it means we have exceeded our allowed number of retries
    logger.error(f"cfs-state-reporter is still running even after {attempts} attempts to run systemctl")
    raise CfsTestException

def check_cfs_state_reporter_status():
    srv_exit_status, srv_load_state, srv_active_state, srv_substate, srv_result = get_service_data_fields()
    
    errors=False
    if srv_exit_status != "0":
        logger.error(f"ExecMainStatus={srv_exit_status} | expected value=0")
        errors=True
    if srv_load_state != "loaded":
        logger.error(f"LoadState={srv_load_state} | expected value=loaded")
        errors=True
        
    if srv_active_state != "inactive":
        logger.error(f"ActiveState={srv_active_state} | expected value=inactive")
        errors=True
    # We only check the SubState if the ActiveState is what we expect
    elif srv_substate != "dead":
        logger.error(f"SubState={srv_substate} | expected value=dead")
        errors=True

    if srv_result != "success":
        logger.error(f"Result={srv_result} | expected value=success")
        errors=True

    if errors:
        raise CfsTestException

def main():
    print(f"Test log file: {logFilePath}")
    try:
        check_cfs_state_reporter_status()
        print("")
        logger.info("PASS: Validation of cfs-state-reporter service succeeded")
        return 0
    except CfsTestException:
        pass
    except Exception as exc:
        logger.error("Unexpected error validating cfs-state-reporter service", exc_info=exc)
    print("")
    print(f"More details can be found in the test log file: {logFilePath}")
    print("For additional information, try running: /usr/bin/systemctl --no-pager status cfs-state-reporter")
    return 1

if __name__ == "__main__":
    sys.exit(main())
