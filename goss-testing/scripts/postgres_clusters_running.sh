#!/bin/bash

failFlag=0
postgresStatuses="$(kubectl get postgresql -A -o jsonpath='{.items[*].status.PostgresClusterStatus}')" 
for status in $postgresStatuses
do
    if [[ $status != "Running" ]]; then failFlag=1; fi
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else exit 1
fi
