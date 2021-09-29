#!/bin/bash

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: postgres_clusters_leader.sh           # Only print 'PASS' upon success"
             echo "       postgres_clusters_leader.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: postgres_clusters_leader.sh           # Only print 'PASS' upon success"
             echo "       postgres_clusters_leader.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

failFlag=0
postgresClusters="$(kubectl get postgresql -A | awk '/postgres/ || NR==1' | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"
    leader=$(kubectl -n $c_ns exec $first_member -- patronictl list --format json 2>/dev/null | jq '.[] | select ( .Role=="Leader" ) | .Member' | sed 's/\"//g')
    if [[ -z $leader ]]
    then
        if [[ $print_results -eq 1 ]]; 
        then 
            echo "$c_name has no Leader."
            failFlag=1
            kubectl -n $c_ns exec $first_member -- patronictl list 2>/dev/null 
            echo
        else exit 1; fi
    else
        lock=$(kubectl logs -n $c_ns $leader postgres | awk '{$1="";$2=""; print $line}' | sort -u | grep 'i am the leader with the lock')
        if [[ -z $lock ]]
        then
            if [[ $print_results -eq 1 ]]
            then 
                echo "${c_name}'s leader's logs do not contain 'i am the leader with the lock'."
                failFlag=1
            else exit 2; fi
        fi
    fi
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; fi
