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
set -euf -o pipefail

if ! { [[ -f /var/www/ephemeral/configs/data.json ]] \
  || [[ "$HOSTNAME" == *pit ]] ;}; then
  # If this is runtime, check cloud-init
  nodes=$(cloud-init query ds | jq -r ".meta_data[].host_records[] | select(.aliases[]? | contains(\"ncn\")) | .aliases[]"  2>/dev/null | sort | uniq | grep -v '\.' | grep -v 'mgmt')
else
  # If this is running on the PIT, check dnsmasq as the source of truth
  nodes=$(grep -oP 'ncn-\w\d+' /etc/dnsmasq.d/statics.conf | sort -u)
fi

for node in $nodes; do
  # waitsync
  #    arg 1: maximum number of tries before giving up and returning a non-zero error code
  #    arg 2: maximum allowed remaining correction of the system clock 
  #    arg 3: maximum allowed skew (in ppm) as reported by the tracking command
  #    arg 4: interval specified in seconds in which the check is repeated
  #
  # try 10 times and allow skew of up to 1 second before returning a non-zero error code
  # remote chronyc commands require 'cmdallow' and 'bindcmdaddress' to be set in the chrony config
  printf '%s: ' "$node"
  chronyc -h "$node" waitsync 2 1.0 
  printf "\n"
  # printf "%d." $(echo 0AFC0107 | sed 's/../0x& /g' | tr ' ' '\n' | cat) | sed 's/\.$/\n/'
done
