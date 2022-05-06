#!/usr/bin/env bash
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
while getopts n:c:h stack
do
    case "${stack}" in
          n) namespaces=$OPTARG;;
          c) cluster_spec=$OPTARG;;
          h) echo "usage: etcd-health-checkup.sh -n <namespace> -c <cluster> #Checks a single cluster in a namespace"
         echo "       etcd-health-checkup.sh -n <namespace> #Checks health of all etcd clusters in a single namespace"
         echo "default: when no namespace or cluster is selected, the health check will look at all etcd clusters in all namespaces";;
      \?) echo "usage: etcd-health-checkup.sh -n <namespace> -c <cluster> #Checks a single cluster in a namespace"
              echo "       etcd-health-checkup.sh -n <namespace> #Checks health of all etcd clusters in a single namespace"
          echo "default: when no namespace or cluster is selected, the health check will look at all etcd clusters in all namespaces";;
    esac
done

if [[ -z $namespaces && ! -z $cluster_spec ]]
then
    echo "Error. Need to specify namespace '-n <namespace>' when specifying a cluster. -h for help"
    exit 5
fi

if [[ -z $namespaces ]]
then
    namespaces=$(kubectl get namespace -o jsonpath='{.items[*].metadata.name}')
fi

echo "--- Check that the Correct Number of Pods Running, Check Endpoint Health, Check if Any Alarms are Set ---"
for namespace in $namespaces
do
    if [[ -z $cluster_spec ]] # check if cluster was specified
    then
        etcd_clusters=$(kubectl get etcd -n $namespace -o jsonpath='{.items[*].metadata.name}')
    else
        etcd_clusters=$cluster_spec
    fi

    #shellcheck disable=SC2046
    #shellcheck disable=SC2086
    echo '###' $( echo $etcd_clusters | wc -w ) ' etcd clusters found in namespace ' $namespace

    for cluster in $etcd_clusters
    do
        # check that the expected number of etcd members are running
        etcd_members=0
        members_msg=""

        exp_members=$(kubectl get etcd $cluster -n $namespace -o jsonpath='{.spec.size}')
        act_members=$(kubectl get etcd $cluster -n $namespace -o jsonpath='{.status.size}')
        min_members=$(( $exp_members / 2 + 1 )) # minimum members for quorum
        if [ "$act_members" -lt "$exp_members" ]
        then
            if [ "$act_members" -lt "$min_members" ]
            then
                members_msg="ERROR-Too few members for quorum. Expected $exp_members etcd members, got $act_members memebers, needs atleast $min_members."
                etcd_members=1
            else
                members_msg="WARNING-Expected $exp_members etcd members, got $act_members members."
            fi
        else
            members_msg="GOOD-Expected $exp_members etcd members, got $act_members members."
        fi

        # check endpoint health
        cluster_end_health=0
        endpoint_msg=""
        pods=$(kubectl get pods -l etcd_cluster=$cluster -n $namespace -o jsonpath='{.items[*].metadata.name}')
        for pod in $pods
        do
            #shellcheck disable=SC2034
            temp=$(kubectl -n services exec ${pod} -- /bin/sh -c "ETCDCTL_API=3 etcdctl endpoint health -w json")
            if [[ $? != 0 ]]
            then
                endpoint_msg="${endpoint_msg}Error with endpoint health of ${pod}.  "
                cluster_end_health=1
            fi
        done
        if [[ $endpoint_msg == "" ]]
        then
            endpoint_msg="All pods passed endpoint health check."
        fi

        # check alarms
        cluster_alarms=0
        alarm_msg=""
        for pod in $pods
        do
            alarm=$(kubectl -n $namespace exec ${pod} -- /bin/sh -c "ETCDCTL_API=3 etcdctl alarm list")
            if [ ! -z $alarm ]
            then
                alarm_msg="${alarm_msg}Alarms for ${pod}: ${alarm}.  "
                cluster_alarms=1
            fi
        done
        if [[ $alarm_msg == "" ]]
        then
            alarm_msg="No alarms set."
        fi

        if [[ $etcd_members == 0 && $cluster_end_health == 0 && $cluster_alarms == 0  ]]
        then
            status="PASS"
            exit_code=0
        else
            status="FAIL"
            exit_code=1
        fi
        parent="(${cluster%-etcd})" # get etcd_cluster without ending '-etcd'
        parent_spaced=$(printf "%23s" $parent)
        echo "${status} ${parent_spaced}: ${members_msg}   ${endpoint_msg}   ${alarm_msg}"
    done
done

exit  $exit_code
