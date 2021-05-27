#!/bin/bash

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

exit $exit_code
