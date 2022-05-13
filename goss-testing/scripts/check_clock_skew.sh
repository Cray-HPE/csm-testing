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

#
# Being a bit conservative here -- want to leave a bit
# of room for ssh times, but not too much so we don't
# allow real drift.
#
allowed_drift_seconds=1
pdsh_node_args=""
mkdir -p ~/.ssh/sockets/
export PDSH_SSH_ARGS_APPEND="-o ControlMaster=auto -o ControlPath=~/.ssh/sockets/%r@%h-%p -o ControlPersist=600 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
nodes=$(cloud-init query ds | jq -r ".meta_data[].host_records[] | select(.aliases[]? | contains(\"ncn\")) | .aliases[]"  2>/dev/null | sort | uniq | grep -v '\.' | grep -v 'mgmt')

for node in $nodes; do
  # set up the initial ssh connection to each node so it can be re-used below for a faster test
  #shellcheck disable=SC2086
  ssh $PDSH_SSH_ARGS_APPEND "$node" 'sleep 180' &
done

for node in $nodes; do
  pdsh_node_args="$pdsh_node_args -w $node"
done

cnt=0
exit_code=0
baseline=""

node_times=$(pdsh $pdsh_node_args 'date -u "+%s"' 2>/dev/null)
#shellcheck disable=SC2206
node_times_array=( $node_times )
array_length=${#node_times_array[@]}

echo "Epoch seconds by node (allowing $allowed_drift_seconds seconds of drift):"
echo "$node_times"
echo ""

while [[ "$cnt" -lt "$array_length" ]]; do
  node="${node_times_array[$cnt]}"
  cnt=$((cnt+1))
  epoch_secs="${node_times_array[$cnt]}"
  cnt=$((cnt+1))
  node=$(echo $node | sed 's/://g')

  if [ "$baseline" == "" ]; then
    baseline=$epoch_secs
    continue
  fi
  diff="$(($baseline-$epoch_secs))"
  diff=${diff/-/} # absolute value
  if [[ "$diff" -gt "$allowed_drift_seconds" ]]; then
    echo "ERROR: $node has drifted $diff second(s)"
    exit_code=1
  fi
done
for node in $nodes; do
  # if the persistent ssh connection is still open, close it
  if ssh -O check -o ControlPath=~/.ssh/sockets/%r@%h-%p "$node"; then
    ssh -O exit -o ControlPath=~/.ssh/sockets/%r@%h-%p "$node"
  fi
done
# exit with the exit code that was set
exit $exit_code
