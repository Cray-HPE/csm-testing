#!/bin/bash

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: postgres_replication_lag.sh           # Only print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: postgres_replication_lag.sh           # Only print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
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

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"

    for lag in $(kubectl -n $c_ns exec $first_member -- patronictl list --format json 2>/dev/null | jq '.[]."Lag in MB"')
    do
        if [[ $lag != "\"\"" ]] && [[ $lag == "\"unknown"\" || $lag -gt 50 ]]; 
        then 
            if [[ $print_results -eq 1 ]]; 
            then 
                echo "Warning: $c_name has Lag: $lag"; 
                failFlag=1 
                kubectl -n $c_ns exec $first_member -- patronictl list 2>/dev/null
            else exit 1; fi
        fi
    done
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; fi
