#!/bin/bash
#
# MIT License
#
# (C) Copyright 2022-2024 Hewlett Packard Enterprise Development LP
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
set -euo pipefail

DEBUG=${DEBUG:=false}

# get an array of all non-running pods in the kube-system namespace
while IFS='' read -r line; do non_running_pods+=("$line"); done < <(kubectl get po -n kube-system --no-headers \
  | awk '{ print $1" "$3 }' \
  | grep -Ev ' (Running|Completed)$' \
  | grep -Ev '-etcdbackup-.* (ContainerCreating|Init:[0-9]+/[0-9]+|NotReady|Pending|PodInitializing|Terminating)$' \
  | awk '{ print $1 }')


for pod_name in "${non_running_pods[@]}"; do
  if [ "${DEBUG}" == "true" ]; then echo "checking non-running pod: $pod_name";fi
  # get the label name of the current pod
  label_name=$(kubectl get -n kube-system po "$pod_name" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/name}')
  if [ "${DEBUG}" == "true" ]; then echo "checking for other pods with the label: $label_name";fi
  # check if there are any other pods with the same label name since they may be newer and have a different status
  while IFS='' read -r line; do same_pods+=("$line"); done < <(kubectl get pods -l app.kubernetes.io/name="$label_name" -n kube-system -o json | jq -r '.items[].metadata.name')
  most_recent_pod=""
  most_recent_time=0
  # for each pod with the same label name, check if it is running or completed
  for same in "${same_pods[@]}"; do
    status=$(kubectl get pod -n kube-system "$same" -o json | jq -r '.status.phase')
    if [ "${DEBUG}" == "true" ]; then echo "  found: $same $status";fi
    # if there is no error, get the start time of the pod
    if [ "$status" != "Error" ]; then
      start_time=$(kubectl get pod -n kube-system "$same" -o json | jq -r '.status.startTime')
      # Calculate the start time in seconds since epoch
      start_time_seconds=$(date -u -d "$start_time" +%s)
      # if the start time is greater than the most recent time, update the most recent time and pod
      if [ "$start_time_seconds" -gt "$most_recent_time" ]; then
        if [ "${DEBUG}" == "true" ]; then echo "  $same start_time is greater than most_recent_time: $start_time_seconds > $most_recent_time";fi
        most_recent_time=$start_time_seconds
        most_recent_pod=$same
      fi
    fi
  done
  # if there is a most recent pod and it is not the current pod, go to the next non_running_pod
  # this is considered a success and prevents false positives since the newer pod has successfully started
  if [ -n "$most_recent_pod" ] && [ "$most_recent_pod" != "$pod_name" ]; then
    if [ "${DEBUG}" == "true" ]; then echo "  a more recent pod is not in a fail state: $pod_name";fi
    continue
  else
    # print the pod that is in a poor state to fail the test
    echo "$pod_name is not running or completed" >&2
  fi
done

exit 0
