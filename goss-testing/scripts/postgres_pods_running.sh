#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022-2023 Hewlett Packard Enterprise Development LP
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
# How many postgres pods should be running?
#  Do no hard code the number of instances -- determine from postgresql, customizations and/or patronictl list.
#    - Fail if customizations has set sqlCluster.instanceCount, and the postgresql numberOfInstances is not the same as the
#           customizations sqlCluster.instanceCount (no clear source of truth).
#    - Fail if the number of Running pods for the postgres cluster is not the same as the postgresql numberOfInstances.
#    - Fail if the number of running cluster members (as reported by patronictl list) is not the same as the postgresql 
#           numberOfInstances.

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

    # Determine the number of postgres pods based on the numberIfInstances from the postgresql cr and the site-init customizations sqlCluster.instanceCount.
    # If the sqlCluster.instanceCount is set in the customizations and it is not the same as that set in the postgresql cr then fails and continue to the next cluster.
    num_of_instances=$(kubectl get postgresql -n $c_ns ${c_name} -o json | jq -r '.spec.numberOfInstances')
    service_name=$(kubectl get postgresql -n $c_ns ${c_name} -o yaml | grep "meta.helm.sh/release-name:" | awk '{print $2}')
    customization_instance_count=$(kubectl get secrets -n loftsman site-init -o jsonpath='{.data.customizations\.yaml}' | base64 -d | yq read - "spec.kubernetes.services.${service_name}.cray-service*.sqlCluster.instanceCount")

    if [[ ! -z $customization_instance_count ]]; then
        if [[ $num_of_instances -ne $customization_instance_count ]]; then
            failFlag=1;
	    if [[ $print_results -eq 1 ]]
	    then
		echo "$c_name -- Postgresql numOfInstances:$num_of_instances and sqlCluster.instanceCount:$customization_instance_count do not match (fail)"
            fi
            continue
	fi
    fi

    num_pods_running=$(kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}" | grep Running | wc -l)
    if [[ $num_pods_running -ne $num_of_instances ]]; then 
	failFlag=1
        if [[ $print_results -eq 1 ]]
        then
            echo "$c_name -- Does not have the expected number of $num_pods_running pods Running (fail)"
            kubectl get pods -n $c_ns -l "application=spilo,cluster-name=${c_name}"
            echo
	fi
        continue
    fi

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"
    num_patronictl_running=$(kubectl -n $c_ns exec $first_member -c postgres -- patronictl list 2>/dev/null | grep running | wc -l)
    if [[ $num_patronictl_running -ne $num_of_instances ]]; then 
        failFlag=1
        if [[ $print_results -eq 1 ]]
        then
            echo "$c_name -- $num_patronictl_running instances are not running, shown by patronictl command (fail)"
            kubectl -n $c_ns exec $first_member -c postgres -- patronictl list 2>/dev/null
            echo
	fi
        continue
     fi
     if [[ $print_results -eq 1 ]]
     then
  	 echo "$c_name -- Running instances (pass)"
     fi
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; fi
