#!/bin/bash

failFlag=0
postgresClusters="$(kubectl get postgresql -A | awk '/postgres/ || NR==1' | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"

    for lag in $(kubectl -n $c_ns exec $first_member -- patronictl list --format json 2>/dev/null | jq '.[]."Lag in MB"')
    do
        if [[ $lag != "\"\"" ]] && [[ $lag == "\"unknown"\" || $lag -gt 0 ]]; then failFlag=1; fi
    done
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else exit 1; fi
