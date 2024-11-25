#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022, 2024 Hewlett Packard Enterprise Development LP
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

# Checks if all expected kyverno pods are running.
# Component label and number of pods in running status should be:
#   admission-controller: 3
#   background-controller: 1
#   cleanup-controller: 1
#   reports-controller: 1

check_running() {
    pod_label=$1
    pod_count=$2
    running_pods=$(kubectl get pods -n kyverno --field-selector=status.phase=Running -l "app.kubernetes.io/component=${pod_label}" --no-headers | wc -l)
    rc=$?
    if [[ ${rc} -ne 0 ]]
    then
        # Split into two echo commands for code readability
        echo -n "ERROR: Command pipeline failed (return code $rc): " 1>&2
        echo "kubectl get pods -n kyverno --field-selector=status.phase=Running -l "app.kubernetes.io/component=${pod_label}" --no-headers | wc -l" 1>&2
        echo "FAIL"
        exit 10
    elif [[ "${running_pods}" != "${pod_count}" ]]
    then
        if [[ ${print_results} -eq 1 ]]
        then
            echo "ERROR: ${running_pods} out of ${pod_count} ${pod_label} pods are running."
            if [[ "${pod_label}" == "admission-controller" ]]
            then
                echo "For high availability the recommended Kyverno ${pod_label} replica count is ${pod_count}."
                echo "Check the logs, restart Kyverno, and ensure that all ${pod_count} Kyverno ${pod_label} pods are running."
            fi
        fi
        echo "FAIL"
        exit 1
    fi

    if [[ ${print_results} -eq 1 ]]
    then
        echo "${pod_label} has ${running_pods} of ${pod_count} pods running."
    fi
}

# Loop through list of pod labels and expected pod count
pod_labels="admission-controller background-controller cleanup-controller reports-controller"

for pod in $pod_labels
do
    num_pods=1
    if [[ "${pod}" == "admission-controller" ]]
    then
        num_pods=3
    fi

    check_running ${pod} ${num_pods}
done

echo "PASS"
exit 0
