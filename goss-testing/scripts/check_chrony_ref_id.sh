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

set -eufo pipefail

refid=""
refid_addr=""
i=0

# until the refid is set, keep checking for a max of 30 seconds
until [[ "${refid:-127.127.1.1}" != "127.127.1.1" ]] \
  || [[ i -gt 30 ]]; do
  # during chrony startup or the switching of servers, the reference is empty or set to 7F7F0101 (127.127.1.1)
  # once that is no longer the case, the ref id is the id of the server that is being used
  #shellcheck disable=SC2046
  refid=$(printf "%d." $(chronyc tracking \
    | awk '/Reference ID/ {print $4}' \
    | sed 's/../0x& /g' \
    | tr ' ' '\n') \
    | sed 's/\.$/\n/')
  echo "Waiting for Reference ID to be set..."
  sleep 1
  echo "Ref ID: $refid"
  ((i=i+1))
done

# once the above condition is met, check the friendly name/IP of the server it is synchronised with
# this will be used to validate it is using the correct source
refid_addr=$(chronyc tracking \
  | awk '/Reference ID/ {print $5}' \
  | tr -d '()')

# the resolvable address in parenthesis can sometimes be empty if it cant resolve or isn't a real ntp server
if [[ -z "${refid_addr}" ]]; then
  >&2 echo "Unable to resolve reference ID address or no source set"
  exit 1
fi

# check ncn-m001 is using the correct source
if [[ "$HOSTNAME" = "ncn-m001" ]] || [[ "$HOSTNAME" = *pit ]]; then
  # as long as ncn-m001 isn't using another ncn as it's source, it is ok
  if [[ $refid_addr =~ (ncn-.*)(.nmn) ]];then
    >&2 echo "ncn-m001 should not use another NCN as it's source"
    exit 1
  fi
  echo "$HOSTNAME is using a reasonable source: $refid_addr"
# the other nodes can use another ncn as their source
else
  if ! [[ $refid_addr =~ (ncn-.*)(.nmn) ]];then
    >&2 echo "$HOSTNAME should use ncn-m001 or another NCN as it's source (currently $refid_addr)"
    exit 1
  fi
  echo "$HOSTNAME is using a reasonable source: $refid_addr"
fi
