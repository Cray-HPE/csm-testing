#!/bin/bash

postgresClusters="$(kubectl get postgresql -A | awk '/postgres/ || NR==1' | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"
    leader=$(kubectl -n $c_ns exec $first_member -- patronictl list --format json 2>/dev/null | jq '.[] | select ( .Role=="Leader" ) | .Member' | sed 's/\"//g')
    if [[ -z $leader ]]; then exit 1; fi

    lock=$(kubectl logs -n $c_ns $leader postgres | awk '{$1="";$2=""; print $line}' | egrep "INFO|ERROR" | egrep -v "NewConnection|bootstrapping" | sort -u | grep 'i am the leader with the lock')
    if [[ -z $lock ]]; then exit 1; fi
done

echo "PASS"
exit 0
