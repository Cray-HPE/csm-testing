#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
# This file is sourced by the NCN automated testing scripts.

function k8s_local_tests {
  if [[ ! -f "/etc/dnsmasq.d/statics.conf" ]]; then
    # Running on the PIT node -- run the PIT-appropriate suite
    echo "Test Suite: Kubernetes Cluster Checks (on PIT node)"
    /usr/bin/goss -g $GOSS_BASE/suites/common-kubernetes-tests-cluster.yaml v
    echo
  else
    # Not on the PIT node
    echo "Test Suite: Kubernetes Cluster Checks"
    /usr/bin/goss -g $GOSS_BASE/suites/ncn-kubernetes-tests-cluster.yaml v
    echo
  fi
}

function run_ncn_tests {
  export NODE=$1
  port=$2
  endpoint=$3

  echo
  echo Running tests against node $'\e[1;33m'$NODE$'\e[0m'
  url=http://$NODE.hmn:$port/$endpoint

  echo Server URL: $url
  results=`curl -s {$url}`

  if [[ $? == 0 ]]; then
    if ! `echo $results | jq -e > /dev/null 2>&1`; then
      echo $'\e[1;31m'ERROR: Output not valid JSON$'\e[0m'
      return 1
    else
      echo $results | jq -c '.results | sort_by(.result) | .[]' | while read -r test; do
        result=$(echo $test | jq -r '.result')

        if [ -z $result ]; then
          continue
        elif [ $result == 0 ]; then
          result=PASS
          echo $'\e[1;32m'
        else
          result=FAIL
          echo $'\e[1;31m'
        fi

        title=$(echo $test | jq -r '.title')
        description=$(echo $test | jq -r '.meta.desc')
        severity=$(echo $test | jq -r '.meta.sev')
        summary=$(echo $test | jq -r '."summary-line"')
        time=$(echo $test | jq -r '.duration')
        time=$(echo "scale=8; $time/1000000000" | bc | awk '{printf "%.8f\n", $0}')

        echo "Result: $result"
        echo "Test Name: $title"
        echo "Description: $description"
        echo "Severity: $severity"
        echo "Test Summary: $summary"
        echo "Execution Time: $time seconds"
        echo "Node: $NODE"
      done
    fi

    echo $'\e[0m'

    total=$(echo $results | jq -r '.summary."test-count"')
    failed=$(echo $results | jq -r '.summary."failed-count"')
    time=$(echo $results | jq -r '.summary."total-duration"')
    time=$(echo "scale=4; $time/1000000000" | bc | awk '{printf "%.4f\n", $0}')

    echo "Total Tests: $total, Total Passed: $((total-failed)), Total Failed: $failed, Total Execution Time: $time seconds"
  else
    echo $'\e[1;31m'ERROR: Server endpoint could not be reached$'\e[0m'
  fi
  return 0
}

function add_host_var
{
    # $1 - goss variable file
    if [[ $# -ne 1 ]]; then
        echo "ERROR: add_host_var: Function requires exactly 1 argument but received $#: $*"
        return 1
    elif [[ -z $1 ]]; then
        echo "ERROR: add_host_var: Argument may not be blank"
        return 1
    elif [[ ! -e $1 ]]; then
        echo "ERROR: add_host_var: File '$1' does not exist"
        return 1
    elif [[ ! -f $1 ]]; then
        echo "ERROR: add_host_var: File '$1' exists but is not a regular file"
        return 1
    fi

    local myname
    # Add local nodename as variable
    myname=$(hostname -s | grep -Eo '(ncn-[msw][0-9]{3}|.*-pit)$')
    echo -e "\nthisnode: \"$myname\"\n" >> $1
    return $?
}
