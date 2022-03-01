#!/bin/bash

# (C) Copyright 2022 Hewlett Packard Enterprise Development LP.
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

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: postgres_pods_running.sh           # Only print 'PASS' upon success"
             echo "       postgres_pods_running.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: postgres_pods_running.sh           # Only print 'PASS' upon success"
             echo "       postgres_pods_running.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

failFlag=0
postgresClusters="$(kubectl get postgresql -A | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    num_pods_running=$(kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}" | grep Running | wc -l)
    clusterFailFlag=0
    if [[ $c_name == "sma-postgres-cluster" ]]; then
        if [[ $num_pods_running -ne 2 ]]; then clusterFailFlag=1; fi
    else
        if [[ $num_pods_running -ne 3 ]]; then clusterFailFlag=1; fi
    fi

    if [[ $clusterFailFlag -eq 1 ]]
    then
        if [[ $print_results -eq 1 ]]
        then
            echo "Error: $c_name does not have the expected number of pods Running."
            kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}"
            echo
            failFlag=1;
        else exit 1; fi
    fi

    clusterFailFlag=0
    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"
    num_patronictl_running=$(kubectl -n $c_ns exec $first_member -- patronictl list 2>/dev/null | grep running | wc -l)
    if [[ $c_name == "sma-postgres-cluster" ]]; then
        if [[ $num_patronictl_running -ne 2 ]]; then clusterFailFlag=1; fi
    else
        if [[ $num_patronictl_running -ne 3 ]]; then clusterFailFlag=1; fi
    fi

    if [[ $clusterFailFlag -eq 1 ]]
    then
        if [[ $print_results -eq 1 ]]
        then
            echo "Error: $c_name instances are not running, shown by patronictl command."
            kubectl -n $c_ns exec $first_member -- patronictl list 2>/dev/null
            echo
            failFlag=1;
        else exit 1; fi
    fi
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; fi
