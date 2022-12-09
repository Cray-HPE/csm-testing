#!/usr/bin/env python3
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
Usage: print_goss_json_results <filename|stdin[:label]|url>
                               [<filename|stdin[:label]|url>] ...

One or more sources of Goss test results are passed in.

If the source begins with "http:" or "https:", it is assumed to be a Goss endpoint,
and the GET request will be made to it to get the test results. The node name
will be extracted from the URL to be displayed in the test results.

If the source is "stdin", then the Goss test results are read from standard input.
The node name is assumed to be the local host. A label for the tests will be used
if one is provided after a :

Otherwise, the source is assumed to be a file. The node name is assumed to be the local host.

- If the file begins with "test/" or "suite/" and ends in ".yaml", then it is assumed
to be a Goss test/suite file. It will be executed and its results will be parsed.
- Otherwise, it is assumed to be a file containing Goss test results in JSON
format.

As each source is processed, the failures are displayed, along with a single line summary
of the overall results for that source.

At the end, a final single line summary is printed.

The script creates a log directory when it is executed. The location of this directory is
included at the top of the script output. Two files are generated there. One is a terse log file,
which is mainly intended to help with debugging of the script itself. The other is a verbose output
file, where full test results are written (not just failures).

Exit codes:

All tests passed            0
At least one test failed    1
Usage error                 2
Other error                 3

If multiple exit codes apply, the highest one is used.
"""

from lib.common import err_text,                    \
                       fmt_exc,                     \
                       get_hostname,                \
                       goss_base,                   \
                       goss_script_log_level,       \
                       goss_script_max_threads,     \
                       log_dir,                     \
                       log_goss_env_variables,      \
                       log_values,                  \
                       multi_print,                 \
                       ok_text,                     \
                       ScriptException,             \
                       ScriptUsageException,        \
                       stderr_print,                \
                       stdout_print,                \
                       StringList,                  \
                       strip_path,                  \
                       time_pid_unique_string,      \
                       timestamp_string,            \
                       warn_text

from lib.grok_exporter_logger import grok_exporter_log,      \
                                     GROK_EXPORTER_LOG_DIR,  \
                                     JSONDict

from typing import Callable, Dict, List, Tuple

import argparse
import concurrent.futures
import itertools
import json
import logging
import os
import re
import requests
import subprocess
import sys
import threading
import traceback

RC_TESTFAIL = 1
RC_USAGE = 2
RC_ERROR = 3

outfile = None
grok_exporter_outfile = None

MY_BASENAME = strip_path(__file__)


def log_to_grok_exporter(msg: str, data: JSONDict=None) -> None:
    """
    Add a line to the grok-exporter log file.
    """
    grok_exporter_log(message=msg, script_name=MY_BASENAME, outfile=grok_exporter_outfile,
                      data=data)
        

def outfile_print(s: str) -> None:
    global outfile
    if outfile == None:
        return
    try:
        outfile.write(f"{s}\n")
        outfile.flush()
    except Exception as e:
        msg = f"Error writing to output file. {fmt_exc(e)}"
        logging.error(msg)
        stderr_print(msg)
        outfile = None

def print_newline() -> None:
    multi_print("", outfile_print, stdout_print)

def error(s: str) -> None:
    stderr_print(err_text(f"ERROR: {s}"))
    logging.error(s)
    outfile_print(f"ERROR: {s}")

def warning(s: str) -> None:
    stderr_print(warn_text(f"WARNING: {s}"))
    logging.warning(s)
    outfile_print(f"WARNING: {s}")

def is_url(s: str) -> bool:
    """
    Very basic check to see if string appears to be a URL
    """
    return s.find("http://") == 0 or s.find("https://") == 0

def get_node_from_url(url: str) -> str:
    # The node name we use (as a label for results) is the first string after the //, up until
    # the first period, colon, or / (whichever is first)
    node = url.split("/")[2]

    # The split takes care of any /, so now just need to look for period or colon
    period_index = node.find(".")
    colon_index = node.find(":")
    if 0 <= period_index < colon_index:
        return node[:period_index]
    elif colon_index >= 0:
        return node[:colon_index]
    return node

def print_reading_test_results_message(node: str, label: str = "") -> None:
    if label:
        stdout_print(f"Reading test results for node {warn_text(node)} ({label})")
        outfile_print(f"Reading test results for node {node} ({label})")
    else:
        stdout_print(f"Reading test results for node {warn_text(node)}")
        outfile_print(f"Reading test results for node {node}")

def read_and_decode_json(input_file: str, node: str) -> dict:
    if input_file == "stdin" or input_file[:6] == "stdin:":
        logging.debug("Reading standard input for JSON results")
        if input_file == "stdin":
            print_reading_test_results_message(node)
        else:
            print_reading_test_results_message(node, input_file[6:])
        input = sys.stdin.read()
    else:
        print_reading_test_results_message(node, input_file)
        logging.debug(f"Reading {input_file} for JSON results")
        try:
            with open(input_file, "rt") as infile:
                input = infile.read()
        except Exception as e:
            # Add a newline before printing errors
            print_newline()
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            raise ScriptException(f"Problem reading input file {input_file}. {fmt_exc(e)}")

    try:
        return json.loads(input)
    except Exception as e:
        # Add a newline before printing errors
        print_newline()
        log_values(logging.debug, input=input)
        multi_print(traceback.format_exc(), outfile_print, logging.error)
        raise ScriptException(f"Error decoding JSON from {input_file}. {fmt_exc(e)}")

class JsonResultsCollection:
    def __init__(self):
        self.lock = threading.Lock()
        self.results_map = dict()

    # This just makes sure that log_values makes a single call to
    # the logging method, guaranteeing that the entry will all go in together. That way it won't be interleaved
    # with entries from other threads.
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

    # input_url suffices as a unique name for this function in a multi-threading context, as we do not
    # permit duplicate URLs. It is important to include this in all logging calls made in this function,
    # in order to identify which thread was making the call. Also, 
    def get_json_from_input_url(self, input_url: str) -> None:
        logging.info(f"Making GET request to {input_url}")
        try:
            resp = requests.get(input_url)
        except Exception as e:
            logging.error(f"Unexpected error attempting GET request to {input_url}: {traceback.format_exc()}")
            self.send_result(input_url, f"Unexpected error attempting GET request to {input_url}: {fmt_exc(e)}")
            return

        JsonResultsCollection.log_values(logging.debug, input_url=input_url, status_code=resp.status_code, reason=resp.reason, headers=resp.headers, ok=resp.ok)
        # Expected responses are 200 (meaning no tests failed) or 503 (which can mean either that there were test failures OR that there was
        # another Goss issue, like syntax errors in the test files).
        if resp.status_code not in { 200, 503 }:
            err_msg = f"Status code {resp.status_code} received from Goss URL {input_url}: {resp.text}"
            logging.error(err_msg)
            self.send_result(input_url, err_msg)
            return

        logging.info(f"Decoding JSON response body from {input_url}")
        try:
            json_results = resp.json()
        except Exception as e:
            logging.error(f"Unexpected error decoding JSON response from {input_url}: {traceback.format_exc()}")
            JsonResultsCollection.log_values(logging.debug, input_url=input_url, text=resp.text)
            self.send_result(input_url, f"Unexpected error decoding JSON response from {input_url}: {fmt_exc(e)}")
            return

        JsonResultsCollection.log_values(logging.debug, input_url=input_url, json_results=json_results)
        logging.info(f"Successfully decoded JSON response from {input_url}")
        self.send_result(input_url, json_results)
        return

    def run_goss_decode_json(self, suite_or_test: str) -> None:
        cmd_list = ["/usr/bin/goss", "-g", suite_or_test, "v", "--format", "json"]
        logging.debug(f"Running: {cmd_list}")
        cmd_result = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        cmd_out = cmd_result.stdout
        cmd_err = cmd_result.stderr
        # The goss command will return non-0 both in the case of test failures and in the case of other errors
        # (such as syntax errors in the test files). From what I can tell, it will return 1 in either case.
        # If the output of the command has valid JSON results data, then we're happy.

        # If the stderr is not empty, we log these values as warnings. Otherwise we log them as debug.
        if len(cmd_err) != 0:
            JsonResultsCollection.log_values(logging.warning, cmd_list=cmd_list, returncode=cmd_result.returncode, stderr=cmd_err)
        else:
            JsonResultsCollection.log_values(logging.debug, cmd_list=cmd_list, returncode=cmd_result.returncode, stderr=cmd_err)
        logging.info(f"Command completed: {cmd_list}")
        try:
            json_results = json.loads(cmd_out)
        except Exception as e:
            # This is most likely going to happen if the goss command failed
            JsonResultsCollection.log_values(logging.error, cmd_list=cmd_list, returncode=cmd_result.returncode,
                                stdout=cmd_out, stderr=cmd_err)
            logging.error(f"Unexpected error decoding JSON output from {cmd_list}: {traceback.format_exc()}")
            self.send_result(suite_or_test, f"Unexpected error decoding JSON output from {cmd_list}: {fmt_exc(e)}")
            return
        JsonResultsCollection.log_values(logging.debug, cmd_list=cmd_list, returncode=cmd_result.returncode,
                            stdout=cmd_out, stderr=cmd_err)
        logging.info(f"Successfully decoded JSON output from {cmd_list}")
        self.send_result(suite_or_test, json_results)
        return

    def run_test_decode_json(self, source: str) -> None:
        if is_url(source):
            self.get_json_from_input_url(input_url=source)
        else:
            self.run_goss_decode_json(suite_or_test=source)

class ResultsEntry(object):
    def __init__(self, result_entry_raw: dict):
        self.result_raw = result_entry_raw["result"]
        self.title = result_entry_raw["title"]
        self.summary = result_entry_raw["summary-line"]
        self.duration_raw = result_entry_raw["duration"]
        self.duration = self.duration_raw/1000000000.0
        self.resource = result_entry_raw["resource-id"]
        self.description = result_entry_raw["meta"]["desc"]
        if self.result_raw == 0:
            # Test passed
            self.result_string = "PASS"
        elif self.result_raw == 1:
            # Test failed
            self.result_string = "FAIL"
        elif self.result_raw == 2:
            # Test was skipped (this is not usually due to error)
            self.result_string = "SKIPPED"
        else:
            # This should never happpen
            self.result_string = f"UNKNOWN (Goss result = {self.result_raw})"

    def multiline_string(self, source: str, node_name: str) -> str:
        """
        Return a string of the results formatted as a multi-line string,
        followed by a blank line
        """
        return ( f"Result: {self.result_string}\n"
                 f"Source: {source}\n"
                 f"Test Name: {self.title}\n"
                 f"Description: {self.description}\n"
                 f"Test Summary: {self.summary}\n"
                 f"Execution Time: {self.duration:.8f} seconds\n"
                 f"Node: {node_name}\n\n" )

    def dict(self, source: str, node_name: str) -> dict:
        """
        Return the results in dict format
        """
        return { "Result Code": self.result_raw,
                 "Result String": self.result_string,
                 "Source": source,
                 "Test Name": self.title,
                 "Description": self.description,
                 "Test Summary": self.summary,
                 "Execution Time (raw)": self.duration_raw,
                 "Execution Time (seconds)": self.duration,
                 "Node": node_name }


def extract_results_data(json_results: dict) -> Tuple[List[ResultsEntry], int, float]:
    try:
        results = json_results["results"]
        # Make list of results with a numeric result
        # Convert durations to seconds
        selected_results = [ ResultsEntry(result_entry_raw=result_entry)
                             for result_entry in results
                             if isinstance(result_entry["result"], int) ]

        # Get some of the summary fields
        summary = json_results["summary"]
        failed_count = summary["failed-count"]
        total_duration = summary["total-duration"]/1000000000.0
    except (KeyError, TypeError) as e:
        # Add a newline before printing errors
        print_newline()
        multi_print(traceback.format_exc(), outfile_print, logging.error)
        raise ScriptException(f"Goss test results from have unexpected format. {fmt_exc(e)}")

    if len(selected_results) == 0:
        raise ScriptException("No Goss test results found.")

    # Sort the results
    selected_results.sort(key=lambda r: (r.title, r.result_raw))
    return selected_results, failed_count, total_duration

def show_results(source: str, selected_results: List[ResultsEntry], failed_count: int, total_duration: float, node_name: str) -> Tuple[int, int, int]:
    """
    Prints all results to outfile.
    Prints failures to stderr.
    Prints warnings if no tests executed or the Goss data contains inconsistencies.
    Returns (# of passes, # of failures, # of unknown results)
    """
    manual_unknown_count=0
    manual_pass_count=0
    manual_fail_count=0
    manual_skip_count=0    
    total_count=len(selected_results)
    for res in selected_results:
        bad_result = False
        # Goss result 0 -> pass, 1 -> fail, 2 -> skip
        if res.result_string == "PASS":
            # Test passed
            manual_pass_count+=1
        elif res.result_string == "FAIL":
            # Test failed
            manual_fail_count+=1
            bad_result = True
        elif res.result_string == "SKIPPED":
            # Test was skipped (this is not usually due to error)
            manual_skip_count+=1
        else:
            # This should never happpen
            manual_unknown_count+=1
            bad_result = True

        # Write to output file
        result_lines=res.multiline_string(source=source, node_name=node_name)
        outfile_print(result_lines)

        # Write to grok-exporter log
        log_to_grok_exporter("Test result", data=res.dict(source=source, node_name=node_name))

        # If the test failed or had an unknown result, also print to stderr in red
        if bad_result:
            # If this is the first error for this source, add a newline before it
            if (manual_fail_count + manual_unknown_count) == 1:
                print_newline()
            stderr_print(err_text(result_lines))

    summary_data = {
        "Node": node_name,
        "Source": source,
        "Total Tests": total_count,
        "Total Passed": manual_pass_count,
        "Total Failed": manual_fail_count,
        "Total Skipped": manual_skip_count,
        "Total Unknown": manual_unknown_count,
        "Total Execution Time": f"{total_duration:.8f} seconds" }
    summary = ', '.join([ f"{key}: {value}" for key, value in summary_data.items() ])
    multi_print(summary, logging.info, outfile_print)
    log_to_grok_exporter("Source test results summary", summary_data)
    if failed_count != manual_fail_count:
        # If no errors have been reported yet for this source, add a newline first
        if manual_fail_count == 0:
            print_newline()
        mismatch=f"failed_count in results ({failed_count}) does not match manual tally of test failures ({manual_fail_count})"
        stderr_print(warn_text(f"WARNING: {mismatch}"))
        logging.warning(mismatch)
        multi_print(f"WARNING: {mismatch}", outfile_print, log_to_grok_exporter)
        print_newline()

    return manual_pass_count, manual_fail_count, manual_unknown_count

suite_test_file_pattern = "^(?:suites|tests)/[^/]+[.]yaml$"
suite_test_file_prog = re.compile(suite_test_file_pattern)
def is_suite_test_file(s: str) -> bool:
    if suite_test_file_prog.match(s):
        return True
    return False

def parse_args() -> Dict[str, StringList]:
    parser = argparse.ArgumentParser(description="Summarize JSON-format Goss test results with pretty colors.")
    parser.add_argument("sources", nargs="+", help="Sources for test results.")
    # In Python 3.6, the exit_on_error option to ArgumentParser does not yet exist, so a cruder method is
    # required to control how the script exits in the case of a usage error.
    try:
        args = parser.parse_args()
    except SystemExit:
        # A usage message will already have been printed
        stderr_print(err_text("FAILED (usage)"))
        sys.exit(RC_USAGE)

    input_sources = args.sources
    if len(input_sources) != len(set(input_sources)):
        stderr_print(err_text(f"Duplicate sources are not permitted. Invalid arguments: {' '.join(input_sources)}"))
        stderr_print(err_text("FAILED (usage)"))
        sys.exit(RC_USAGE)

    # Classify the sources by type (stdin counts as a result_file_source)
    # For non-stdin file sources, make sure the file exists

    # Even though we allow only one stdin source, we make it a list just for simplicity
    sources = { "stdin": list(), "goss_file": list(), "results_file": list(), "url": list() }
    for source in input_sources:
        if is_url(source):
            sources["url"].append(source)
            continue
        elif source == "stdin" or source[:6] == "stdin:":
            # Only allow a maximum of one stdin source
            if sources["stdin"]:
                stderr_print(err_text(f"Multiple stdin sources are not permitted. Invalid arguments: {' '.join(input_sources)}"))
                stderr_print(err_text("FAILED (usage)"))
                sys.exit(RC_USAGE)
            sources["stdin"].append(source)
            continue
        elif is_suite_test_file(source):
            source_path = f"{goss_base()}/{source}"
            sources["goss_file"].append(source_path)
        else:
            source_path = source
            sources["results_file"].append(source_path)
        if not os.path.isfile(source_path):
            stderr_print(err_text(f"File source does not exist: {source_path}"))
            stderr_print(err_text("FAILED (usage)"))
            sys.exit(RC_USAGE)

    return sources

def main(input_sources: Dict[str, StringList]) -> int:
    """
    Returns number of failed tests

    Or raises ScriptException
    """

    # This will get updated as needed during execution, in case
    # of failures beyond test failures
    unexpected_error = False
    
    all_results = list()
    url_sources = input_sources["url"]
    goss_file_sources = input_sources["goss_file"]
    results_file_sources = input_sources["results_file"]

    mynode = get_hostname()

    # First handle results files:
    for source in results_file_sources:
        try:
            log_values(logging.debug, source=source)
            json_results = read_and_decode_json(source, mynode)
            log_values(logging.info, source=source, node=mynode, json_results=json_results)
        except ScriptException as e:
            error(e)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
            continue
        except Exception as e:
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            error(f"Skipping {source} due to error: {fmt_exc(e)}\n")
            unexpected_error = True
            continue
        # Extract the results from the JSON
        try:
            selected_results, failed_count, total_duration = extract_results_data(json_results)
        except ScriptException as e:
            error(e)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
            continue
        except Exception as e:
            # Add a newline before printing errors
            print_newline()
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            error(f"Skipping {source} due to error extracting test results from JSON data: {fmt_exc(e)}\n")
            unexpected_error = True
            continue
        all_results.append({
            "source": source,
            "selected_results": selected_results,
            "failed_count": failed_count,
            "total_duration": total_duration,
            "node_name": mynode })

    # Now handle goss files and url sources in parallel
    parallel_sources = goss_file_sources + url_sources
    if parallel_sources:
        json_results_collection = JsonResultsCollection()
        multi_print("Running tests", outfile_print, logging.info, stdout_print)

        max_workers = goss_script_max_threads()
        if max_workers == 0:
            exec_args = dict()
        else:
            exec_args = { "max_workers": max_workers }
        log_values(logging.debug, exec_args=exec_args)
        with concurrent.futures.ThreadPoolExecutor(**exec_args) as executor:
            executor.map(json_results_collection.run_test_decode_json, parallel_sources)
        json_results_map = json_results_collection.results_map
        for source in parallel_sources:
            try:
                json_results = json_results_map[source]
            except KeyError:
                error(f"Internal error. Unable to find results OR error message from request to {source}")
                error(f"Skipping {source} due to error\n")
                unexpected_error = True
                continue
            if isinstance(json_results, str):
                error(f"Error encountered running {source} tests: {json_results}")
                error(f"Skipping {source} due to error\n")
                unexpected_error = True
                continue
            # Extract the results from the JSON
            try:
                selected_results, failed_count, total_duration = extract_results_data(json_results)
            except ScriptException as e:
                error(e)
                error(f"Skipping {source} due to error\n")
                unexpected_error = True
                continue
            except Exception as e:
                multi_print(traceback.format_exc(), outfile_print, logging.error)
                error(f"Skipping {source} due to error extracting test results from JSON data: {fmt_exc(e)}\n")
                unexpected_error = True
                continue
            if source in url_sources:
                node = get_node_from_url(source)
            else:
                node = mynode
            all_results.append({
                "source": source,
                "selected_results": selected_results,
                "failed_count": failed_count,
                "total_duration": total_duration,
                "node_name": node })

    # Finally we handle stdin,
    if input_sources["stdin"]:
        source = input_sources["stdin"][0]
        try:
            log_values(logging.debug, source=source)
            json_results = read_and_decode_json(source, mynode)
            log_values(logging.info, source=source, node=mynode, json_results=json_results)
        except ScriptException as e:
            error(e)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
        except Exception as e:
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            error(f"Skipping {source} due to error: {fmt_exc(e)}\n")
            unexpected_error = True
        else:
            # Extract the results from the JSON
            try:
                selected_results, failed_count, total_duration = extract_results_data(json_results)
            except ScriptException as e:
                error(e)
                error(f"Skipping {source} due to error\n")
                unexpected_error = True
            except Exception as e:
                # Add a newline before printing errors
                print_newline()
                multi_print(traceback.format_exc(), outfile_print, logging.error)
                error(f"Skipping {source} due to error extracting test results from JSON data: {fmt_exc(e)}\n")
                unexpected_error = True
            else:
                all_results.append({
                    "source": source,
                    "selected_results": selected_results,
                    "failed_count": failed_count,
                    "total_duration": total_duration,
                    "node_name": mynode })

    total_passed = 0
    total_failed = 0
    total_unknown = 0
    if all_results:
        multi_print("\nChecking test results", outfile_print, logging.info, stdout_print)
        stdout_print("Only errors will be printed to the screen")
        for results in all_results:
            log_values(logging.debug, results=results)
            passed, failed, unknown = show_results(**results)
            total_passed += passed
            total_failed += failed
            total_unknown += unknown

    print_newline()
    if total_unknown == 0:
        total_summary = f"GRAND TOTAL: {total_passed} passed, {total_failed} failed"
    else:
        total_summary = f"GRAND TOTAL: {total_passed} passed, {total_failed} failed, {total_unknown} unknown results"
    multi_print(total_summary, outfile_print, log_to_grok_exporter)
    if total_passed == 0 and total_failed == 0 and total_unknown == 0:
        stderr_print(warn_text(total_summary))
        logging.warning(total_summary)
        warning("No tests executed")
    elif total_failed > 0 or total_unknown > 0:
        stderr_print(err_text(total_summary))
        logging.error(total_summary)
        if total_failed > 0:
            error("There was at least one test failure")
    else:
        stdout_print(ok_text(total_summary))
        logging.info(total_summary)

    if unexpected_error or total_unknown > 0:
        error("Errors occured during execution beyond just test failures.")
        raise ScriptException()
    return total_failed


def setup_logging() -> Tuple[str, str, str]:
    unique_string = time_pid_unique_string()
    
    MY_LOG_DIR = log_dir(script_name=__file__, sub_directory_basename=unique_string)
    try:
        # create the log directory for the grok-exporter logs; it is ok if it already exists
        os.makedirs(GROK_EXPORTER_LOG_DIR, exist_ok=True)
        
        # create log directory; it is NOT ok if it already exists
        os.makedirs(MY_LOG_DIR, exist_ok=False)
    except Exception as exc:
        stderr_print(err_text(f"Error creating log directory. {fmt_exc(exc)}"))
        sys.exit(RC_ERROR)

    MY_LOG_FILE = f"{MY_LOG_DIR}/log"
    try:
        logging.basicConfig(filename=MY_LOG_FILE, level=goss_script_log_level())
    except Exception as e:
        stderr_print(err_text(f"Error configuring script logging. {fmt_exc(e)}"))    
        sys.exit(RC_ERROR)

    MY_OUTPUT_FILE = f"{MY_LOG_DIR}/out"

    logging.debug(f"Called with {len(sys.argv)} argument(s): {' '.join(sys.argv)}")
    stdout_print(f"Writing full output to {MY_OUTPUT_FILE}\n")
    log_values(logging.info, MY_OUTPUT_FILE=MY_OUTPUT_FILE)
    log_goss_env_variables(logging.debug)

    script_basename = strip_path(__file__)
    GROK_EXPORTER_LOG_FILE = f"{GROK_EXPORTER_LOG_DIR}/{unique_string}.log"

    return MY_LOG_FILE, MY_OUTPUT_FILE, GROK_EXPORTER_LOG_FILE


# Parse command-line arguments
input_sources = parse_args()

# Set up logging
MY_LOG_FILE, MY_OUTPUT_FILE, GROK_EXPORTER_LOG_FILE = setup_logging()

log_values(logging.debug, input_sources=input_sources, sys_argv=sys.argv)


with open(MY_OUTPUT_FILE, "wt") as outfile:
    outfile_print(f"Script debug log file: {MY_LOG_FILE}")
    with open(GROK_EXPORTER_LOG_FILE, "wt") as grok_exporter_outfile:
        outfile_print(f"Script grok-exporter log file: {GROK_EXPORTER_LOG_FILE}")
        log_values(logging.info, GROK_EXPORTER_LOG_FILE=GROK_EXPORTER_LOG_FILE)
        log_to_grok_exporter("Starting", data={ "sys.argv": sys.argv })
        try:
            if main(input_sources) == 0:
                stdout_print(ok_text("\nPASSED"))
                outfile_print("\nPASSED")
                multi_print("PASSED; exiting with return code 0", logging.info, log_to_grok_exporter)
                sys.exit(0)
            stderr_print(err_text("\nFAILED"))
            outfile_print("\nFAILED")
            multi_print(f"FAILED (failed tests); exiting with return code {RC_TESTFAIL}", logging.error, log_to_grok_exporter)
            sys.exit(RC_TESTFAIL)
        except ScriptException:
            stdout_print(f"Full script output: {MY_OUTPUT_FILE}\nScript debug log: {MY_LOG_FILE}")
            stderr_print(err_text("\nFAILED"))
            outfile_print("\nFAILED")
            multi_print(f"FAILED; exiting with return code {RC_ERROR}", logging.error, log_to_grok_exporter)
            sys.exit(RC_ERROR)
        except Exception as e:
            # For any anticipated exceptions, they would have been caught at a lower level and turned into
            # ScriptExceptions. So we should print more information about this exception.
            stdout_print(f"Full script output: {MY_OUTPUT_FILE}\nScript debug log: {MY_LOG_FILE}")
            multi_print(traceback.format_exc(), logging.error, outfile_print, log_to_grok_exporter)
            msg = f"Unexpected error. {fmt_exc(e)}"
            error(msg)
            log_to_grok_exporter(msg)
            stderr_print(err_text("\nFAILED"))
            outfile_print("\nFAILED")
            multi_print(f"FAILED (unexpected error); exiting with return code {RC_ERROR}", logging.error, log_to_grok_exporter)
            sys.exit(RC_ERROR)

outfile = None
grok_exporter_outfile = None
error("\nPROGRAMMING LOGIC ERROR: This line should never be reached")
sys.exit(RC_ERROR)
