#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2023 Hewlett Packard Enterprise Development LP
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

function err_exit {
  echo "ERROR: $*" >&2
  exit 1
}

# Checks that bond config file exists and contains at least one bond member interface
# For each such interface, verifies that it has an active link (status UP).
# Exits rc 0 if all looks good, otherwise exits 1.

BOND_CONFIG_FILE=/etc/sysconfig/network/ifcfg-bond0

[[ -e ${BOND_CONFIG_FILE} ]] || err_exit "Does not exist: '${BOND_CONFIG_FILE}'"
[[ -f ${BOND_CONFIG_FILE} ]] || err_exit "Exists but is not a regular file: '${BOND_CONFIG_FILE}'"
[[ -s ${BOND_CONFIG_FILE} ]] || err_exit "File has size 0: '${BOND_CONFIG_FILE}'"

# Read the file, to have it in the test log, and to confirm it is readable
echo "Running: cat '${BOND_CONFIG_FILE}'"
cat "${BOND_CONFIG_FILE}"

echo "Finding member interfaces in file"

# We deliberately populate the array in this way so that we can make sure the script exits if
# the awk or tr commands fail
#shellcheck disable=SC2207
member_interfaces=( $(awk -F '=' '/BONDING_SLAVE/{print $2}' "${BOND_CONFIG_FILE}" | tr -d \') )
echo "Found ${#member_interfaces[@]} interfaces in bond0: ${member_interfaces[*]}"
[[ ${#member_interfaces[@]} -gt 0 ]] || err_exit "No interfaces found in bond0"

tempfile=$(mktemp /tmp/check_bond_member_links_XXXX.txt) ||
    err_exit "Command failed: mktemp /tmp/check_bond_member_links_XXXX.txt"

for interface in "${member_interfaces[@]}"; do
    echo "Running: ip -d -j link show dev '${interface}'"
    ip -d -j link show dev "${interface}" | tee "${tempfile}" ||
        err_exit "Error writing to '${tempfile}' or command failed: ip -d -j link show dev '${interface}'"

    # The command output should be a JSON array with 1 entry
    num_entries=$(jq length "${tempfile}") || err_exit "Command failed: jq length '${tempfile}'"
    echo "Number of entries in command output: ${num_entries}"
    [[ ${num_entries} -eq 1 ]] ||
        err_exit "Command output should have exactly 1 entry but it had ${num_entries}: ip -d -j link show dev '${interface}'"

    # Make sure the command reported the status as UP
    status=$(jq -r '.[0].operstate' "${tempfile}") || err_exit "Command failed: jq -r '.[0].operstate' '${tempfile}'"
    echo "Link status of interface ${interface}: ${status}"
    [[ ${status} == UP ]] || err_exit "Interface ${interface} status should be UP but it is '${status}'"
done

# Remove temporary file
rm "${tempfile}" || err_exit "Command failed: rm '${tempfile}'"

echo "PASSED"
exit 0
