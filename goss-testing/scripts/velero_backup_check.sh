#/bin/bash

# (C) Copyright 2022 Hewlett Packard Enterprise Development LP.
#
# MIT License
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

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
