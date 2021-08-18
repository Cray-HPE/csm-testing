#!/bin/bash

failFlag=0
postgresClusters="$(kubectl get postgresql -A | awk '/postgres/ || NR==1' | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    num_pods=$(kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}" | grep Running | wc -l)
    if [[ $c_name == "sma-postgres-cluster" ]]; then
        if [[ $num_pods -ne 2 ]]; then failFlag=1; fi
    else
        if [[ $num_pods -ne 3 ]]; then failFlag=1; fi
    fi
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else exit 1; fi
