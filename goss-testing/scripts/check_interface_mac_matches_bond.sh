#!/bin/bash
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

# On failures we will exit with unusual exit codes, to help make it clearer where the test failed

# This test uses command pipelines, so we will set pipefail. That way the pipelines will
# fail (i.e. exit non-0) if any of the commands in the chain fail
set -eo pipefail

function cleanup
{
    [[ -n $TMPFILE && -f $TMPFILE ]] || return 0
    echo "Cleaning up temporary file..."
    echo "# rm -f '$TMPFILE'"
    rm -f "$TMPFILE" || echo "WARNING: Command failed with exit code $?: rm -f '$TMPFILE'" 1>&2
    echo
}

# error <exit code> <error message>
function error
{
    local rc
    cleanup
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

# cmdfail <script exit code> <command exit code> <command + args>
function cmdfail
{
    error "$1" "Command failed (exit code $2): $3"
}



TMPFILE=/tmp/check_interface_mac_matches_bound.$$.$RANDOM.tmp
INTERFACES=( "$@" )

if [[ ${#INTERFACES[@]} -eq 0 ]]; then
    usage 5 "No interface specified"
elif [[ -z ${#INTERFACES[@]} ]]; then
    usage 15 "Interface argument(s) may not be null"
fi

for INTERFACE in "${INTERFACES[@]}"
do
echo "Checking that MAC address of interface '$INTERFACE' matches MAC address of bond0..."
echo

# First print the entire output of the 'ip addr show' command, mainly for potential use in debugging
# test failures.

echo "# ip addr show"
ip addr show ||
    cmdfail 25 $? "ip addr show"

echo

# Get the MAC address of the interface. 
echo "# ip addr show dev '$INTERFACE'"
ip addr show dev "$INTERFACE" | tee "$TMPFILE" || 
    cmdfail 30 $? "ip addr show dev '$INTERFACE' | tee '$TMPFILE'"

INT_MAC=$( grep link/ether "$TMPFILE" | awk '{ print $2 }' ) || 
    cmdfail 35 $? "grep link/ether '$TMPFILE' | awk '{ print \$2 }'"
echo "Interface ($INTERFACE) MAC address = $INT_MAC"

echo

# Get the MAC address of bond0.
echo "# ip addr show dev bond0"
ip addr show dev bond0 | tee "$TMPFILE" || 
    cmdfail 50  $? "ip addr show dev bond0 | tee '$TMPFILE'"
BND_MAC=$( grep link/ether "$TMPFILE" | awk '{ print $2 }' ) || 
    cmdfail 55 $? "grep link/ether '$TMPFILE' | awk '{ print \$2 }'"
echo "bond0 MAC address = $BND_MAC"

echo

# Validate that we actually got a MAC address for each
[[ -n $INT_MAC ]] || error 70 "No MAC address found for $INTERFACE"
[[ -n $BND_MAC ]] || error 75 "No MAC address found for bond0"

# Finally, validate that they match
[[ $INT_MAC == "$BND_MAC" ]] || error 90 "MAC address of $INTERFACE does not match MAC address of bond0"

# Clean up the temporary file
cleanup

# Looks good!
echo ""MAC address of "$INTERFACE" matches MAC address of bond0""
echo "Test passed!"
done
exit 0
