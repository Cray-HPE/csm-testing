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

Otherwise, the source is assumed to be a file containing the Goss test results in JSON
format. The node name is assumed to be the local host.

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

from lib.common import err_text,               \
                       fmt_exc,                \
                       get_hostname,           \
                       log_goss_env_variables, \
                       goss_script_log_level,  \
                       log_dir,                \
                       log_values,             \
                       multi_print,            \
                       ok_text,                \
                       ScriptException,        \
                       ScriptUsageException,   \
                       stderr_print,           \
                       stdout_print,           \
                       warn_text

import argparse
import concurrent.futures
import itertools
import json
import logging
import os
import requests
import sys
import threading
import traceback

RC_TESTFAIL = 1
RC_USAGE = 2
RC_ERROR = 3

outfile = None

MY_LOG_DIR = None
MY_LOG_FILE = None

def outfile_print(s):
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

def print_newline():
    multi_print("", outfile_print, stdout_print)

def error(s):
    stderr_print(err_text(f"ERROR: {s}"))
    logging.error(s)
    outfile_print(f"ERROR: {s}")

def warning(s):
    stderr_print(warn_text(f"WARNING: {s}"))
    logging.warning(s)
    outfile_print(f"WARNING: {s}")

def get_node_from_url(url):
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

def print_reading_test_results_message(node, label=None):
    if label:
        stdout_print(f"Reading test results for node {warn_text(node)} ({label})")
        outfile_print(f"Reading test results for node {node} ({label})")
    else:
        stdout_print(f"Reading test results for node {warn_text(node)}")
        outfile_print(f"Reading test results for node {node}")

def read_and_decode_json(input_file, node):
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

# The function name is a bit misleading. This just makes sure that log_values makes a single call to
# the logging method, guaranteeing that the entry will all go in together. That way it won't be interleaved
# with entries from other threads.
def threaded_log_values(log_method, **kwargs):
    log_values(log_method, values=kwargs)

# input_url suffices as a unique name for this function in a multi-threading context, as we do not
# permit duplicate URLs. It is important to include this in all logging calls made in this function,
# in order to identify which thread was making the call. Also, 
def get_json_from_input_url(input_url, lock, json_results_map):
    logging.info(f"Making GET request to {input_url}")
    try:
        resp = requests.get(input_url)
    except Exception as e:
        logging.error(f"Unexpected error attempting GET request to {input_url}: {traceback.format_exc()}")
        with lock:
            json_results_map[input_url] = f"Unexpected error attempting GET request to {input_url}: {fmt_exc(e)}"
        return

    threaded_log_values(logging.debug, input_url=input_url, status_code=resp.status_code, reason=resp.reason, headers=resp.headers, ok=resp.ok)
    # Expected responses are 200 (meaning no tests failed) or 503 (which can mean either that there were test failures OR that there was
    # another Goss issue, like syntax errors in the test files).
    if resp.status_code not in { 200, 503 }:
        err_msg = f"Status code {resp.status_code} received from Goss URL {input_url}: {resp.text}"
        logging.error(err_msg)
        with lock:
            json_results_map[input_url]= err_msg
        return

    logging.info(f"Decoding JSON response body from {input_url}")
    try:
        json_results = resp.json()
    except Exception as e:
        logging.error(f"Unexpected error decoding JSON response from {input_url}: {traceback.format_exc()}")
        threaded_log_values(logging.debug, input_url=input_url, text=resp.text)
        with lock:
            json_results_map[input_url] = f"Unexpected error decoding JSON response from {input_url}: {fmt_exc(e)}"
        return

    threaded_log_values(logging.debug, input_url=input_url, json_results=json_results)
    logging.info(f"Successfully decoded JSON response from {input_url}")
    with lock:
        json_results_map[input_url] = json_results
    return

def extract_results_data(json_results):
    try:
        results = json_results["results"]
        # Make list of results with a numeric result
        # Convert durations to seconds
        selected_results = [ 
            {   "result":       result_entry["result"],
                "title":        result_entry["title"], 
                "summary-line": result_entry["summary-line"], 
                "duration":     result_entry["duration"]/1000000000.0, 
                "resource-id":  result_entry["resource-id"],
                "desc":         result_entry["meta"]["desc"] }
            for result_entry in results if isinstance(result_entry["result"], int) ]

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
    selected_results.sort(key=lambda r: (r["title"], r["result"]))
    return selected_results, failed_count, total_duration

def show_results(source, selected_results, failed_count, total_duration, node_name):
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
        if res["result"] == 0:
            # Test passed
            result_lines = [ "Result: PASS" ]
            manual_pass_count+=1
        elif res["result"] == 1:
            # Test failed
            result_lines = [ "Result: FAIL" ]
            manual_fail_count+=1
            bad_result = True
        elif res["result"] == 2:
            # Test was skipped (this is not usually due to error)
            manual_skip_count+=1
            result_lines = [ "Result: SKIPPED" ]
        else:
            # This should never happpen
            manual_unknown_count+=1
            result_lines = [ "Result: UNKNOWN (Goss result = {res['result']})" ]
            bad_result = True

        # The blank string at the end is just to add a newline when
        # the join is called
        result_lines.extend([
            f"Source: {source}",
            f"Test Name: {res['title']}",
            f"Description: {res['desc']}",
            f"Test Summary: {res['summary-line']}",
            f"Execution Time: {res['duration']:.8f} seconds",
            f"Node: {node_name}", "" ])

        result_string = '\n'.join(result_lines)

        # Write to output file
        outfile_print(result_string)

        # If the test failed or had an unknown result, also print to stderr in red
        if bad_result:
            # If this is the first error for this source, add a newline before it
            if (manual_fail_count + manual_unknown_count) == 1:
                print_newline()
            stderr_print(err_text(result_string))

    summary = ', '.join([
        f"Node: {node_name}",
        f"Source: {source}",
        f"Total Tests: {total_count}",
        f"Total Passed: {manual_pass_count}",
        f"Total Failed: {manual_fail_count}",
        f"Total Skipped: {manual_skip_count}",
        f"Total Unknown: {manual_unknown_count}",
        f"Total Execution Time: {total_duration:.8f} seconds"])
    multi_print(summary, logging.info, outfile_print)
    if failed_count != manual_fail_count:
        # If no errors have been reported yet for this source, add a newline first
        if manual_fail_count == 0:
            print_newline()
        mismatch=f"failed_count in results ({failed_count}) does not match manual tally of test failures ({manual_fail_count})"
        stderr_print(warn_text(f"WARNING: {mismatch}"))
        logging.warning(mismatch)
        outfile_print(f"WARNING: {mismatch}")
        print_newline()

    return manual_pass_count, manual_fail_count, manual_unknown_count

def is_url(s):
    """
    Very basic check to see if string appears to be a URL
    """
    return s.find("http://") == 0 or s.find("https://") == 0

def parse_args():
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

    # While we're here, make sure the file sources exist
    for source in input_sources:
        if source == "stdin" or source[:6] == "stdin:" or is_url(source):
            continue
        elif not os.path.isfile(source):
            stderr_print(err_text(f"File source does not exist: {source}"))
            stderr_print(err_text("FAILED (usage)"))
            sys.exit(RC_USAGE)

    return input_sources

def main(input_sources):
    """
    Returns number of failed tests

    Or raises ScriptException
    """

    # This will get updated as needed during execution, in case
    # of failures beyond test failures
    unexpected_error = False
    
    all_results = list()
    url_sources = list()
    for source in input_sources:
        try:
            log_values(logging.debug, source=source)
            if is_url(source):
                # These will be processed concurrently after we process the non-URL sources
                url_sources.append(source)
                continue
            else:
                node = get_hostname()
                json_results = read_and_decode_json(source, node)
            log_values(logging.info, source=source, node=node, json_results=json_results)
        except ScriptException as e:
            error(e)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
            continue
        except Exception as e:
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
            continue
        # Extract the results from the JSON
        try:
            selected_results, failed_count, total_duration = extract_results_data(json_results)
        except ScriptException:
            error(e)
            error(f"Skipping {source} due to error\n")
            unexpected_error = True
            continue
        except Exception as e:
            # Add a newline before printing errors
            print_newline()
            multi_print(traceback.format_exc(), outfile_print, logging.error)
            error(f"Skipping {source} due to error extracting test results from JSON data\n")
            unexpected_error = True
            continue
        all_results.append({
            "source": source,
            "selected_results": selected_results,
            "failed_count": failed_count,
            "total_duration": total_duration,
            "node_name": node })

    # Now handle URL sources in parallel
    num_urls = len(url_sources)
    if num_urls > 0:
        multi_print("Running remote tests", outfile_print, logging.info, stdout_print)
        mylock = threading.Lock()
        json_results_map = dict()

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            executor.map(get_json_from_input_url, url_sources, itertools.repeat(mylock, num_urls), itertools.repeat(json_results_map, num_urls))

        for source in url_sources:
            node = get_node_from_url(source)
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
            except ScriptException:
                error(e)
                error(f"Skipping {source} due to error\n")
                unexpected_error = True
                continue
            except Exception as e:
                multi_print(traceback.format_exc(), outfile_print, logging.error)
                error(f"Skipping {source} due to error extracting test results from JSON data\n")
                unexpected_error = True
                continue
            all_results.append({
                "source": source,
                "selected_results": selected_results,
                "failed_count": failed_count,
                "total_duration": total_duration,
                "node_name": node })

    total_passed = 0
    total_failed = 0
    total_unknown = 0
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
    outfile_print(total_summary)
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

def setup_logging():
    MY_LOG_DIR = log_dir(__file__)
    try:
        # create log directory; it is NOT ok if it already exists
        os.makedirs(MY_LOG_DIR, exist_ok=False)
    except Exception as e:
        stderr_print(err_text(f"Error creating log directory. {fmt_exc(e)}"))
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

    return MY_LOG_FILE, MY_OUTPUT_FILE

# Parse command-line arguments
input_sources = parse_args()

# Set up logging
MY_LOG_FILE, MY_OUTPUT_FILE = setup_logging()

log_values(logging.debug, input_sources=input_sources)

with open(MY_OUTPUT_FILE, "wt") as outfile:
    outfile_print(f"Script debug log file: {MY_LOG_FILE}")
    try:
        if main(input_sources) == 0:
            stdout_print(ok_text("\nPASSED"))
            outfile_print("\nPASSED")
            logging.info("PASSED; exiting with return code 0")
            sys.exit(0)
        stderr_print(err_text("\nFAILED"))
        outfile_print("\nFAILED")
        logging.error(f"FAILED (failed tests); exiting with return code {RC_TESTFAIL}")
        sys.exit(RC_TESTFAIL)
    except ScriptException:
        stdout_print(f"Full script output: {MY_OUTPUT_FILE}\nScript debug log: {MY_LOG_FILE}")
        stderr_print(err_text("\nFAILED"))
        outfile_print("\nFAILED")
        logging.error(f"FAILED; exiting with return code {RC_ERROR}")
        sys.exit(RC_ERROR)
    except Exception as e:
        # For any anticipated exceptions, they would have been caught at a lower level and turned into
        # ScriptExceptions. So we should print more information about this exception.
        stdout_print(f"Full script output: {MY_OUTPUT_FILE}\nScript debug log: {MY_LOG_FILE}")
        multi_print(traceback.format_exc(), logging.error, outfile_print)
        error(f"Unexpected error. {fmt_exc(e)}")
        stderr_print(err_text("\nFAILED"))
        outfile_print("\nFAILED")
        logging.error(f"FAILED (unexpected error); exiting with return code {RC_ERROR}")
        sys.exit(RC_ERROR)

outfile = None
error("\nPROGRAMMING LOGIC ERROR: This line should never be reached")
sys.exit(RC_ERROR)
