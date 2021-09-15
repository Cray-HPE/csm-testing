#!/bin/bash

postgresClusters="$(kubectl get postgresql -A | awk '/postgres/ || NR==1' | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    num_pods_running=$(kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}" | grep Running | wc -l)
    if [[ $c_name == "sma-postgres-cluster" ]]; then
        if [[ $num_pods_running -ne 2 ]]; then exit 1; fi
    else
        if [[ $num_pods_running -ne 3 ]]; then exit 1; fi
    fi

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"
    num_patronictl_running=$(kubectl -n $c_ns exec $first_member -- patronictl list 2>/dev/null | grep running | wc -l)
    if [[ $c_name == "sma-postgres-cluster" ]]; then
        if [[ $num_patronictl_running -ne 2 ]]; then exit 2; fi
    else
        if [[ $num_patronictl_running -ne 3 ]]; then exit 2; fi
    fi
done

echo "PASS"; exit 0
