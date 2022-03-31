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

baseline=""
#
# Being a bit conservative here -- want to leave a bit
# of room for ssh times, but not too much so we don't
# allow real drift.
#
allowed_drift_seconds=1
cnt=0
exit_code=0
pdsh_node_args=""

function check_ssh() {
  node=$1
  output=$(pdsh -w $node 'ls /tmp' 2>&1 | grep -q 'verification failed')
  if [[ "$?" -eq 0 ]]; then
    echo "Adding key from $node to known_hosts"
    ssh-keyscan -t rsa -H $node >> ~/.ssh/known_hosts
  fi
}

nodes=$(cloud-init query ds | jq -r ".meta_data[].host_records[] | select(.aliases[]? | contains(\"ncn\")) | .aliases[]"  2>/dev/null | sort | uniq | grep -v '\.' | grep -v 'mgmt')

for node in $nodes; do
  check_ssh $node
  pdsh_node_args="$pdsh_node_args -w $node"
done

for try in {1..3}; do
echo "Checking clock skew...attempt $try of 3..."
# short delay between tries
sleep 10

node_times=$(pdsh $pdsh_node_args 'date -u "+%s"' 2>/dev/null)
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
done
exit $exit_code