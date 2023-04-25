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
while getopts c:h stack
do
    case "${stack}" in
          c) cluster_spec=$OPTARG;;
          h) echo "usage: etcd-health-checkup.sh -c <cluster> # Checks a single cluster"
         echo "       etcd-health-checkup.sh # Checks health of all etcd clusters"
         echo "default: when or cluster is selected, the health check will look at all etcd clusters";;
      \?) echo "usage: etcd-health-checkup.sh -c <cluster> # Checks a single cluster"
              echo "       etcd-health-checkup.sh # Checks health of all etcd clusters"
          echo "default: when no cluster is selected, the health check will look at all etcd clusters in all namespaces";;
    esac
done

echo "--- Check that the Correct Number of Pods Running, Check Endpoint Health, Check if Any Alarms are Set ---"

if [[ -z $cluster_spec ]] # check if cluster was specified
then
    etcd_clusters=$(kubectl get statefulsets.apps -A | grep bitnami-etcd | awk '{print $2}' | sed s/-bitnami-etcd//g)
else
    etcd_clusters=$cluster_spec
fi

num_clusters=$( echo $etcd_clusters | wc -w )
echo "### ${num_clusters} etcd cluster(s) being checked"

for cluster in $etcd_clusters
do
    etcd_members_result=0
    members_msg=""
    min_members=3
    act_members=$(kubectl get statefulsets.apps -n services "${cluster}-bitnami-etcd" -o json | jq -r '.status.readyReplicas')
    if [[ $act_members -lt 3 ]]; then
        members_msg="ERROR: Too few ready members. There are $act_members members, should be $min_members ready members."
        etcd_members_result=1
    else
        members_msg="Expected $min_members etcd members, got $act_members members."
    fi

    cluster_end_health=0
    endpoint_msg=""
    result=$(/opt/cray/platform-utils/etcd/etcd-util.sh endpoint_health $cluster)
    num_healthy=$(echo "$result" | grep '"health":true' | wc -l)
    if [[ $num_healthy -ne 3 ]]; then
        endpoint_msg="Error with endpoint health status."
        cluster_end_health=1
    else
        endpoint_msg="Endpoint health check passed."
    fi

    cluster_alarms=0
    alarm_msg=""
    result=$(/opt/cray/platform-utils/etcd/etcd-util.sh list_alarms $cluster)
    alarms=$(echo "$result" | grep -v '###')
    if [ ! -z $alarms ]
    then
        alarm_msg="Alarms for ${cluster}: ${alarms}."
        cluster_alarms=1
    else
        alarm_msg="No alarms set."
    fi

    if [[ $etcd_members_result == 0 && $cluster_end_health == 0 && $cluster_alarms == 0  ]]
    then
        status="PASS"
        exit_code=0
    else
        status="FAIL"
        exit_code=1
    fi
    parent_spaced=$(printf "%23s" $cluster)
    echo "${status} ${parent_spaced}: ${members_msg} ${endpoint_msg} ${alarm_msg}"
done

exit  $exit_code
