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
while getopts h stack
do
    case "${stack}" in
          h) echo "usage: etcd_backups_check.sh # Print 'PASS' upon success"
             exit 3;;
         \?) echo "usage: etcd_backups_check.sh # Print 'PASS' upon success"
             exit 3;;
    esac
done

#
# Since clusters subscribed to disaster recovery will have a
# snapshot taken when the cluster first starts, and the cronjob
# that pushes snapshots to S3 happens just after the top of the
# hour, two hours should be enough to have a backup if things are
# working.  Even though below we check has_recent_backup (below)
# within a day, that should succeed.
#
check_ss_old_enough() {
    cluster=$1
    old_enough=0
    now=$(date +"%s")
    two_hours_sec=7200
    create_date=$(kubectl get statefulsets.apps -n services ${cluster}-bitnami-etcd -o jsonpath='{.metadata.creationTimestamp}')
    create_sec=$(date -d "${create_date}" "+%s" 2>/dev/null)
    if [[ ! -z $create_sec && $(( $now - $create_sec )) -ge $two_hours_sec ]]; then
        old_enough=1
    fi
    echo $old_enough
}

error_flag=0

clusters=$(kubectl get statefulsets.apps -A | grep bitnami-etcd | awk '{print $2}')
for c in $clusters; do
  short_name=$(echo $c | sed s/-bitnami-etcd//g)
  ns=$(kubectl get statefulset -A -o json | jq --arg name ${c} '.items[].metadata | select (.name==$name) | .namespace' | sed 's/\"//g')

  dr_setting=$(kubectl get statefulsets.apps -n ${ns} ${c} -o json | jq -r '.spec.template.spec.containers[].env[] | select(."name" == "ETCD_DISASTER_RECOVERY") | .value')
  if [ "$dr_setting" != "yes" ]; then
    echo "$short_name -- not configured for disaster recovery, skipping..."
    continue
  fi

  old_enough=$(check_ss_old_enough $short_name)
  if [[ $old_enough -eq 0 ]]; then
    echo "$short_name -- not old enough to expect backups, skipping..."
    continue
  fi

  #
  # Need to chop off the goofy carriage return in the result from the pod
  #
  result=$(/opt/cray/platform-utils/etcd/etcd-util.sh has_recent_backup ${short_name} 1 | sed 's/\r$//')
  if [ "$result" == "Pass" ]; then
    echo "$short_name -- backup found in the past 24 hours"
  else
    echo "$short_name -- no backup found in the past 24 hours!"
    error_flag=1
  fi
done

if [[ $error_flag -eq 0 ]]; then
  echo "PASS"
  exit 0
else
  echo "FAIL"
  exit 1
fi
