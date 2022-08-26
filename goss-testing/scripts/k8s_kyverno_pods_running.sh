#!/usr/bin/env bash
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

set -o pipefail

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: k8s_kyverno_pods_running.sh           # Only print 'PASS' upon success"
             echo "       k8s_kyverno_pods_running.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: k8s_kyverno_pods_running.sh           # Only print 'PASS' upon success"
             echo "       k8s_kyverno_pods_running.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

# Checks if all kyverno pods are running. There should be a total of 3 running pods.

running_pods=$(kubectl get poda -n kyverno -o json | jq '[.items[] | select(.metadata.labels.app == "kyverno").status.containerStatuses[0].state.running] | length')
rc=$?
if [[ ${rc} -ne 0 ]]
then
    # Split into two echo commands for code readability
    echo -n "ERROR: Command pipeline failed (return code $?): " 1>&2
    echo "kubectl get pods -n kyverno -o json | jq '[.items[] | select(.metadata.labels.app == \"kyverno\").status.containerStatuses[0].state.running] | length'" 1>&2
    echo "FAIL"
    exit 10
elif [[ ${running_pods} != 3 ]]
then
    if [[ ${print_results} -eq 1 ]]
    then
        echo "ERROR: ${running_pods} out of 3 pods are running."
        echo "For high availability the recommended Kyverno pod replica count is 3."
        echo "Check the logs, restart Kyverno, and ensure that all 3 Kyverno pods are running."
    fi
    echo "FAIL"
    exit 1
fi

echo "PASS"
exit 0
