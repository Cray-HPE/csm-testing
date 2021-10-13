#!/bin/bash

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
