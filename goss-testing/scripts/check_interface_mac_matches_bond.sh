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
# On failures we will exit with unusual exit codes, to help make it clearer where the test failed

# This test uses command pipelines, so we will set pipefail. That way the pipelines will
# fail (i.e. exit non-0) if any of the commands in the chain fail
set -eo pipefail

# error <exit code> <error message>
function error
{
    local rc
    rc=$1
    shift
    echo "ERROR: $*" 1>&2
    exit "$rc"
}

# usage <exit code> <error message>
function usage
{
    echo "\
Usage: check_interface_mac_matches_bond.sh <interface>

Given an interface (e.g. bond0.nmn), retrieves its MAC address,
retrieves the MAC address of bond0, and verifies that they are the same.
Exits 0 if this is the case. Exits non-0 if not, or if there are any errors.
" 1>&2
    error "$@"
}

INTERFACES=( "$@" )

if [[ ${#INTERFACES[@]} -eq 0 ]]; then
    usage 5 "No interface specified"
elif [[ -z ${#INTERFACES[@]} ]]; then
    usage 15 "Interface argument(s) may not be null"
fi

# Get the MAC address of bond0.
BND_MAC=""
BND_MAC="$( ip addr show dev bond0 | grep link/ether | awk '{ print $2 }' )" || 
    error 55 "bond0 MAC could not be retrieved"

for INTERFACE in "${INTERFACES[@]}"
do
echo "Checking that MAC address of interface '$INTERFACE' matches MAC address of bond0..."
echo

# if the interface does not show, it might be the option CAN
if ! eval ip addr show dev "$INTERFACE" 1>/dev/null; then
  if [[ "$INTERFACE" == "bond0.can0" ]]; then
    echo "$INTERFACE is optional...skipping"
    # so we can skip the rest of the loop here
    break
  # otherwise, it's a legit failure
  else
    error 30 $? "ip addr show dev $INTERFACE"
  fi
# if the interface does exist, continue checking if it matches bond0
else
  # Get the MAC address of the interface. 
  INT_MAC=""
  INT_MAC="$( ip addr show dev "$INTERFACE" | grep link/ether | awk '{ print $2 }' )"

  # Validate that we actually got a MAC address for each
  [[ -n $INT_MAC ]] || error 70 "No MAC address found for $INTERFACE"
  [[ -n $BND_MAC ]] || error 75 "No MAC address found for bond0"

  # Finally, validate that they match
  [[ $INT_MAC == "$BND_MAC" ]] || error 90 "MAC address of $INTERFACE does not match MAC address of bond0"

  echo "$BND_MAC (bond0)"
  echo "$BND_MAC ($INTERFACE)"

fi
done
