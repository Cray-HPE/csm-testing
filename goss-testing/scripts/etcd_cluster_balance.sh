#!/bin/bash

for ns in services
do
    for cluster in $(kubectl get etcdclusters.etcd.database.coreos.com \
                            -n $ns | grep -v NAME | awk '{print $1}')
    do
        # check each cluster contains the correct number of pods
        num_pods=$(kubectl get pod -n $ns -o wide | grep $cluster | wc -l)
        expected_num_pods=$(kubectl get etcd $cluster -n $ns -o jsonpath='{.spec.size}')
        if [[ $num_pods -ne $expected_num_pods ]]; then exit 1; fi

        # check that no two pods are on the same worker node
        wnodes=$(kubectl get pod -n $ns -o wide | grep $cluster | awk '{print $7}')
        for node in $wnodes
        do
            num_pods_per_node=$(echo $wnodes | grep -o $node | wc -l)
            if [[ $num_pods_per_node -gt 1 ]]; then exit 2; fi
        done
    done
done

echo "PASS"
exit 0
