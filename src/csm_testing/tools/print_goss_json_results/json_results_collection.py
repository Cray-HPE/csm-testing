#
# MIT License
#
# (C) Copyright 2022-2024 Hewlett Packard Enterprise Development LP
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
JsonResultsCollection class
"""

import json
import logging
import subprocess
import threading
import traceback
from typing import Callable

import requests

from csm_testing.lib.common import fmt_exc, log_values

from .print_goss_json_results import is_url


class JsonResultsCollection:
    """
    Class to run Goss tests (either locally or via endpoint) and parse
    the JSON results
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.results_map = {}

    # This just makes sure that log_values makes a single call to
    # the logging method, guaranteeing that the entry will all go in together. That way it won't be
    # interleaved with entries from other threads.
    @staticmethod
    def log_values(log_method: Callable, **kwargs) -> None:
        log_values(log_method, values=kwargs)

    # result will either be a string or the decoded JSON results
    def send_result(self, source: str, result) -> None:
        """
        Takes the lock and then sets the json_results_map[source] entry to be result
        """
        with self.lock:
            self.results_map[source] = result

    # input_url suffices as a unique name for this function in a multi-threading context, as we do
    # not permit duplicate URLs. It is important to include this in all logging calls made in this
    # function, in order to identify which thread was making the call.
    def get_json_from_input_url(self, input_url: str) -> None:
        logging.info("Making GET request to %s", input_url)
        try:
            resp = requests.get(input_url)
        except Exception as exc:
            logging.error("Unexpected error attempting GET request to %s: %s",
                          input_url, traceback.format_exc())
            self.send_result(
                input_url, "Unexpected error attempting GET request to "
                f"{input_url}: {fmt_exc(exc)}")
            return

        JsonResultsCollection.log_values(logging.debug,
                                         input_url=input_url,
                                         status_code=resp.status_code,
                                         reason=resp.reason,
                                         headers=resp.headers,
                                         ok=resp.ok)
        # Expected responses are 200 (meaning no tests failed) or 503 (which can mean either that
        # there were test failures OR that there was another Goss issue, like syntax errors in the
        # test files).
        if resp.status_code not in {200, 503}:
            err_msg = (
                f"Status code {resp.status_code} received from Goss URL "
                f"{input_url}: {resp.text}")
            logging.error(err_msg)
            self.send_result(input_url, err_msg)
            return

        logging.info("Decoding JSON response body from %s", input_url)
        try:
            json_results = resp.json()
        except Exception as exc:
            logging.error(
                "Unexpected error decoding JSON response from %s: %s",
                input_url, traceback.format_exc())
            JsonResultsCollection.log_values(logging.debug,
                                             input_url=input_url,
                                             text=resp.text)
            self.send_result(
                input_url, "Unexpected error decoding JSON response from "
                f"{input_url}: {fmt_exc(exc)}")
            return

        JsonResultsCollection.log_values(logging.debug,
                                         input_url=input_url,
                                         json_results=json_results)
        logging.info("Successfully decoded JSON response from %s", input_url)
        self.send_result(input_url, json_results)
        return

    def run_goss_decode_json(self, suite_or_test: str) -> None:
        cmd_list = [
            "/usr/bin/goss", "-g", suite_or_test, "v", "--format", "json"
        ]
        logging.debug("Running: %s", cmd_list)
        cmd_result = subprocess.run(cmd_list,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    check=False)
        cmd_out = cmd_result.stdout
        cmd_err = cmd_result.stderr
        # The goss command will return non-0 both in the case of test failures and in the case of
        # other errors (such as syntax errors in the test files). From what I can tell, it will
        # return 1 in either case.
        # If the output of the command has valid JSON results data, then we're happy.

        # If the stderr is not empty, we log these values as warnings. Otherwise we log them as
        # debug.
        if len(cmd_err) != 0:
            JsonResultsCollection.log_values(logging.warning,
                                             cmd_list=cmd_list,
                                             returncode=cmd_result.returncode,
                                             stderr=cmd_err)
        else:
            JsonResultsCollection.log_values(logging.debug,
                                             cmd_list=cmd_list,
                                             returncode=cmd_result.returncode,
                                             stderr=cmd_err)
        logging.info("Command completed: %s", cmd_list)
        try:
            json_results = json.loads(cmd_out)
        except Exception as exc:
            # This is most likely going to happen if the goss command failed
            JsonResultsCollection.log_values(logging.error,
                                             cmd_list=cmd_list,
                                             returncode=cmd_result.returncode,
                                             stdout=cmd_out,
                                             stderr=cmd_err)
            logging.error("Unexpected error decoding JSON output from %s: %s",
                          cmd_list, traceback.format_exc())
            self.send_result(
                suite_or_test, "Unexpected error decoding JSON output from "
                f"{cmd_list}: {fmt_exc(exc)}")
            return
        JsonResultsCollection.log_values(logging.debug,
                                         cmd_list=cmd_list,
                                         returncode=cmd_result.returncode,
                                         stdout=cmd_out,
                                         stderr=cmd_err)
        logging.info("Successfully decoded JSON output from %s", cmd_list)
        self.send_result(suite_or_test, json_results)
        return

    def run_test_decode_json(self, source: str) -> None:
        if is_url(source):
            self.get_json_from_input_url(input_url=source)
        else:
            self.run_goss_decode_json(suite_or_test=source)
