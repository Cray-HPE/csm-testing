#/bin/bash

kubectl get backups -A 2>&1 | grep -q 'No resources found'
rc=$?
if [ "$rc" -eq 0 ]; then
  # No backups, we're good
  exit 0
fi

#
# Ignore the first backup, that's expected to be PartiallyFailed
# due to known velero issue
#
output=$(kubectl get backups -A -o json | jq -e '.items[].status.phase' | awk '{if(NR>1)print}')
echo "$output" | grep -q Failed
rc=$?
if [ "$rc" -eq 1 ]; then
  # None are Failed, we're good
  exit 0
fi

exit 1
