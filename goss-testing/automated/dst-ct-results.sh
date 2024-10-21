#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP
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
# Run CSM goss tests and produce a DST-compatible results.json file.
# 
# 1. Query the cgroups file for the pids of the goss suites/vars that are linked to an http endpoint
# 2. Get the command each PID is running 
# 3. Reformat the command into a goss command that can be run directly instead of with 'goss serve'
# 4. Loop through and run each newly-formatted goss command and save the results to a file
# 5. Aggregate each iteration into an api-results.json file, used by DST (additional formatting is required)
# 6. Save the file, which can then be slurped up by the dst pipeline and sent to the results dashboard
set -euo pipefail

#######################################
# Check for required RPMs, commands, and other prerequisites.
# Globals:
#   None
# Arguments:
#   ostype: the operating system type (default is $OSTYPE)
# Outputs:
#   None
# Returns:
#   0 if reqs are met, non-zero if not.
#######################################
prereqs() {
  local rc=0
  local reqs_rpms reqs_cmds
  local ostype="${1:-${OSTYPE}}"

  if [[ "${ostype}" != "linux"* ]]; then
    echo "This script is only supported on Linux, detected: $ostype" >&2
    return 1
  fi

  reqs_rpms=(
    csm-testing 
    goss-servers
  )
  for req in "${reqs_rpms[@]}"; do
    if ! rpm -q "$req" &>/dev/null; then
      echo "Required RPM is not installed: $req" >&2
      rc=1
    fi
  done

  reqs_cmds=(
    jq
    kubectl
    yq
  )
  for req in "${reqs_cmds[@]}"; do
    if ! command -v "$req" &>/dev/null; then
      echo "Required command is not available: $req" >&2
      rc=1
    fi
  done

  if [[ "${rc:-0}" -ne 0 ]]; then
    echo "Please address the missing prerequisites and try again." >&2
    return $rc
  fi

  return 0
}

usage() {
  # echo the usage in order to use the variable for the script name
  # everything else is in the comments
  echo "Usage: $(basename -- "${0}") [-h] OUTPUT_FILE"
  # Any line startng with with a #/ will show up in the usage line

  #/
  #/    Run CSM goss tests and produce a DST-compatible results.json file.
  #/
  #/    -h      Display this help message
  #/
  grep '^  #/' "$0" | cut -c6-
  return 0
}

#######################################
# Set global variables for the script
# Globals:
#   GOSS_BASE
#   GOSS_CGROUPS
#   CSM_VER
#   DST_RESULTS_FILE
#   GOSS_COMMANDS
#   AGGREGATED_GOSS_RESULTS_FILE
# Arguments:
#   None
# Outputs:
#   None
# Returns:
#   0 when all vars are set or non-zero via set -e.
#######################################
set_vars() {
  if [ -f "/etc/pit-release" ]; then
    export GOSS_BASE="/opt/cray/tests/install/livecd"
  else
    export GOSS_BASE="/opt/cray/tests/install/ncn"
  fi
  # The cgroups file that contains the pids of the goss suites/vars that are linked to an http endpoint
  GOSS_CGROUPS="$(find /sys/fs/cgroup -path '*/goss-servers.service/cgroup.procs' -type f)"
  # The CSM version is needed for the DST pipeline for showing the version of the product the test ran on in the dashboard
  CSM_VER="$(kubectl -n services get cm cray-product-catalog -o jsonpath='{.data.csm}' | yq r -j - | jq -r 'keys[]' | sed '/-/!{s/$/_/}' | sort -V | sed 's/_$//' | head -n1)"
  # The DST-compatible results file (see https://github.hpe.com/hpe/hpc-dst-ct-results-api/blob/master/docs/usage/getting-started.md#quick-start)
  DST_RESULTS_FILE="${TEST_BASE_DIR:-/tmp}/api-results.json"
  # Each goss command to run will be added to this array
  GOSS_COMMANDS=()
  # this new file will be used after the loop to aggregate the results into a single "tests" key with an array of results for DST
  AGGREGATED_GOSS_RESULTS_FILE=$(mktemp)
  # Initialize an empty goss JSON object in a new temporary file
  # By defining the default values, we can append to the results object in the loop
  echo '
  {
    "results": [],
    "summary": {
      "failed-count": 0,
      "summary-line": "Count: 0, Failed: 0, Duration: 0.0s",
      "test-count": 0,
      "total-duration": 0
    }
  }' > "$AGGREGATED_GOSS_RESULTS_FILE"

  return 0
}


#######################################
# Loops through each pid in the cgroups file, inspect its command, and format the goss command to run directly
# Globals:
#   GOSS_COMMANDS (populated with goss command strings)
# Arguments:
#   cgroups_path: the path to the cgroups file for the goss-servers.service
#   format: the format to use for the goss command (default is json)
# Outputs:
#   None
# Returns:
#   0 on success, else non-zero.
#######################################
gather_goss_commands() {
  local cgroups_path="${1:-}"
  local format="${2:-json}"
    # if the goss cgroups file exists, read the pids from it
  if [[ -f "${cgroups_path}" ]]; then
    local goss_pids cmd cmdline regex goss_command goss_file goss_vars_file
    # read the pids from the cgroups file
    goss_pids=$(<"${cgroups_path}")
    # loop through each pid
    for pid in ${goss_pids}; do
      # skip any commands that are not goss
      cmd=$(ps -p "$pid" -o comm=)
      if [[ "${cmd}" != "goss" ]]; then
        continue
      fi
      # get the command line of the pid (this is the full command that is running in the goss-server)
      cmdline=$(ps --no-headers -o args fp "${pid}")
      # regex the command line to gather the pieces needed to run the goss command directly
      regex="^(/usr/bin/goss) -g ([^ ]+) --vars ([^ ]+) "
      if [[ "$cmdline" =~ $regex ]]; then
        # this shouldn't change, but it is also hardcoded in the regex as /usr/bin/goss
        goss_command="${BASH_REMATCH[1]}"
        # the goss file, which is the suite that contains links to all the tests
        goss_file="${BASH_REMATCH[2]}"
        # the vars file, which contains the variables that the tests use
        goss_vars_file="${BASH_REMATCH[3]}"
        # format the goss command to run directly
        # add the goss command to the array of commands to run
        GOSS_COMMANDS+=("${goss_command} -g ${goss_file} --vars ${goss_vars_file} validate -f ${format}")
      fi
    done
  else
    return 1
  fi

  return 0
}

#######################################
# Loop through each goss command and processes it.
# Globals:
#   GOSS_COMMANDS (default)
#   AGGREGATED_GOSS_RESULTS_FILE (default)
# Arguments:
#   aggregated_goss_results_file: the file to save the aggregated results to
#   goss_commands: an array of goss commands to run
# Outputs:
#   Prints total suites found to run
# Returns:
#   0 on success, else non-zero via set -e.
#######################################
run_goss_aggregate_results() {
  # first arg is a file
  local aggregated_goss_results_file="${1:-$AGGREGATED_GOSS_RESULTS_FILE}"
  shift ; local -a goss_commands=("${@:-${GOSS_COMMANDS[@]}}") # anything that follows should be a goss command string into an array
  echo "Found ${#goss_commands[@]} suites to run"
  for goss_command in "${goss_commands[@]}"; do
    process_goss_command "$goss_command" "$aggregated_goss_results_file"
  done
  return 0
}

#######################################
# Loops through each goss command, executes it, and aggregates the results into a single file
# Globals:
#   GOSS_COMMANDS (default)
#   AGGREGATED_GOSS_RESULTS_FILE (default)
# Arguments:
#   aggregated_goss_results_file: the file to save the aggregated results to
#   goss_commands: an array of goss commands to run
# Outputs:
#   Prints total suites found to run
# Returns:
#   0 on success, else non-zero via set -e.
#######################################
process_goss_command() {
  local goss_command="${1:-}"
  local aggregated_goss_results_file="${2:-}"
  
  # get the goss file name for the current suite
  local goss_file
  goss_file=$(echo "$goss_command" | awk '{print $3}')
  goss_file=$(basename -- "${goss_file}")
  printf "%s" "Running ${goss_file}..."
  
  # execute goss validate and save the result
  local result
  result=$($goss_command || echo {}) # || it should not fail since we just aggregate the results at the end
  printf "%s\n" "DONE"
  # aggregate each results to the aggregated_goss_results_file
  # 1. extract the results key from the goss output
  # 2. add the results to the existing array in the aggregated results file
  # 3. save the new results to a temp file
  echo "$result" | jq '.results' | jq -s 'add' | jq --argfile agg "$aggregated_goss_results_file" '. as $new | $agg | .results += $new' > "$aggregated_goss_results_file.tmp"
  # move the temp file to become the new original file
  mv "$aggregated_goss_results_file.tmp" "$aggregated_goss_results_file"
  return 0
}

#######################################
# Munges the aggregated results file into a format that is compatible with the DST pipeline
# Globals:
#   CSM_VER 
#   AGGREGATED_GOSS_RESULTS_FILE
#   TOTAL_TEST_COUNT
#   TOTAL_FAILED_COUNT
#   TOTAL_DURATION
#   AGGREGATED_EXIT_CODE
#   VERBOSE
# Arguments:
#   None
# Outputs:
#   Prints a summary of the aggregated results
#   Prints the JSON if VERBOSE=1
# Returns:
#   0 on success, else +1 for each failed test suite.
#######################################
format_goss_results_for_dst() {
  local aggregated_goss_results_file="${1:-$AGGREGATED_GOSS_RESULTS_FILE}"
  local dst_results_file="${2:-$DST_RESULTS_FILE}"
  # See https://github.hpe.com/hpe/hpc-dst-ct-results-api/blob/master/docs/usage/getting-started.md#creating-a-payload-for-the-json-endpoint
  # 
  # 1. extract the results key and assigns it to the variable $results
  # 2. map the $results array to a new array of objects called "tests", required by DST
  # 3. for each object in the $results array, create a new object, compatible with DST
  # 4. assign the value of the "product_name" key to "CSM"
  # 5. assign the value of the "product_version" key to the value of the $CSM_VER variable gathered earlier
  # 6. assign the value of the "release_name" key to an empty string
  # 7. assign the value of the "release_version" key to an empty string
  # 8. assign the value of the "status" key to "pass" if the value of the successful key is true, otherwise assign "fail"
  # 9. assign the value of the "label" key to the value of the "resource-id" key
  # 10. assign the value of the "test_name" key to the value of the "meta.desc" key
  # 11. (currently disabled since it only accepts a string) assign the value of the "output" key to the current object (this is the normal goss output)
  #     "output": .,
  # 12. create a new "triage" object, required by DST, with the following keys: slack, jira, spira (default to false)
  # 13. (disabled since DST does not accept extra keys) create a new summary object, which is the aggregated total for this node
  #     "summary": {
  #       "failed-count": $TOTAL_FAILED_COUNT,
  #       "summary-line": $summary_line,
  #       "test-count": $TOTAL_TEST_COUNT,
  #       "total-duration": $TOTAL_DURATION
  #      }
  # 14. save the output to a new file
  jq --arg csm_version "${CSM_VER:-}" \
    '.results as $results |
    {
      run_id: "",
      tests: $results | map({
        "product_name": "CSM",
        "product_version": $csm_version,
        "release_name": "",
        "release_version": "",
        "output": (if .successful then "omitted" else .stderr end),
        "status": (if .successful then "pass" else "fail" end),
        "label": ."resource-id",
        "test_name": .title, 
      }),
      triage: {}
  }' < "${aggregated_goss_results_file}" > "$dst_results_file"

  # Print the summary
  echo "Aggregated goss results have been saved to: $aggregated_goss_results_file"
  echo "DST-and-ct-results-compatible file been saved to: $dst_results_file"
  # Return the aggregated exit code (+1 per failed test suite)
  return 0
}

#######################################
# Loops through each goss command, executes it, and aggregates the results into a single file
# Globals:
#   GOSS_CGROUPS
# Arguments:
#   None
# Outputs:
#   Prints total suites found
#   Prints current suite being executed and if OK or ERR
#   Prints total count and failed count at the end
#   Prints total count and failed count for each suite if VERBOSE=1
# Returns:
#   0 on success, else non-zero via set -e.
#######################################
main() {
  # always run the prereqs function first to fail early
  prereqs "${OSTYPE:=}"
  # if prereqs passes, set the global variables
  set_vars
  
  # parse the options into named variables
  local dst_results_file="${1:-$DST_RESULTS_FILE}"
  # parse the options
  while getopts "h" opt; do
  case ${opt} in
    h)
      shift
      usage
      exit 0
      ;;
    *)
      echo "Invalid option"
      exit 1
      ;;
  esac
  done

  # get the goss commands from the cgroups file and format them
  gather_goss_commands "${GOSS_CGROUPS}"
  # loop through each goss command and run it directly
  run_goss_aggregate_results "${AGGREGATED_GOSS_RESULTS_FILE}"
  # format the aggregated results into a DST-compatible format
  format_goss_results_for_dst "${AGGREGATED_GOSS_RESULTS_FILE}" "${dst_results_file}"
}


if [[ "${BASH_SOURCE[0]}" -ef "${0}" ]]; then
  # if the script is run directly, run the main function
  main "$@"
fi

