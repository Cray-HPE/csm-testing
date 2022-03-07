#!/bin/bash
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: etcd_cluster_balance.sh           # Only print 'PASS' upon success"
             echo "       etcd_cluster_balance.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: etcd_cluster_balance.sh           # Only print 'PASS' upon success"
             echo "       etcd_cluster_balance.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

failFlag=0
for ns in services
do
    for cluster in $(kubectl get etcdclusters.etcd.database.coreos.com \
                            -n $ns | grep -v NAME | awk '{print $1}')
    do
        # check each cluster contains the correct number of pods
        num_pods=$(kubectl get pod -n $ns -o wide | grep $cluster | wc -l)
        expected_num_pods=$(kubectl get etcd $cluster -n $ns -o jsonpath='{.spec.size}')
        if [[ $num_pods -ne $expected_num_pods ]]
        then 
            if [[ $print_results -eq 1 ]]; 
            then 
                echo "Error: $cluster does not have the expected number of pods."
                kubectl get pod -n $ns -o wide | grep $cluster
                echo
                failFlag=1;
            else exit 1; fi
        fi

        # check that no two pods are on the same worker node
        wnodes=$(kubectl get pod -n $ns -o wide | grep $cluster | awk '{print $7}')
        for node in $wnodes
        do
            num_pods_per_node=$(echo $wnodes | grep -o $node | wc -l)
            if [[ $num_pods_per_node -gt 1 ]]
            then 
                if [[ $print_results -eq 1 ]]; 
                then 
                    echo "Error: $cluster has more than 1 pod per node."
                    kubectl get pod -n $ns -o wide | grep $cluster
                    echo
                    failFlag=1;
                else exit 2; fi 
            fi
        done
    done
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; fi
