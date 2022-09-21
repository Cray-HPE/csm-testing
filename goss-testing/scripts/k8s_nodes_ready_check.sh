#!/bin/bash
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

# Validate that all Kubernetes nodes are reported as being Ready
# Return 0 if the check passes, non-0 otherwise

# Count errors, so that we do not fail on the first one that we see, but instead only fail after checking everything
ERRORS=0

# Echo arguments to stderr prefixed with "ERROR: ", increment error counter
function err_echo
{
    echo "ERROR: $*" 1>&2
    let ERRORS+=1
}

# This script accepts no arguments
if [[ $# -ne 0 ]]; then
    err_echo "usage: k8s_nodes_ready_check.sh"
    exit 2
fi

# By running with these options, it will cut down on the amount of code devoted to error-checking and logging.
# -e -> exit script in failure if any command fails
# -u -> exit script in failure if any unset variable is referenced
# -x -> print the commands that are being run
# -o pipefail -> if any command in a command pipeline fails, the entire pipeline fails
set -euxo pipefail

# Get temporary file to use for storing command output, so that we can run commands, show their output, and also
# parse the output with subsequent commands.
TMPFILE=$(mktemp /tmp/.k8s_nodes_ready_check.$$.XXXXXX.tmp)

# TMPFILE should now point to our temporary file
[[ -n ${TMPFILE} ]]
[[ -f ${TMPFILE} ]]

# Print the list of Kubernetes nodes to the screen and the temporary file
kubectl get nodes --no-headers | tee "${TMPFILE}"

# We will count the nodes as we check them. The test will fail if no nodes are found
COUNT=0

while read NODE STATE REST ; do
    let COUNT+=1

    # Sanity check that the node name appears reasonable
    if ! [[ ${NODE} =~ ^ncn-[mw][0-9]{3}$ ]]; then        
        err_echo "Kubernetes node name does not match expected format: ${NODE}"
    fi
    
    # And verify that the state is Ready
    if [[ ${STATE} != Ready ]]; then
        err_echo "Node '${NODE}' state is '${STATE}', not 'Ready'"
    fi
done < "${TMPFILE}"

# Remove the temporary file. On the off chance that this command fails, we do not want to fail the test. Hence the || true.
rm "${TMPFILE}" || true

# While we expect there to be several master and worker nodes, the purpose of this test is just to check the state of the nodes.
# Therefore, we simply make sure that we found at least one.
if [[ ${COUNT} -eq 0 ]]; then
    err_echo "No Kubernetes nodes reported by kubectl command"
fi

# Make sure that we found no errors
if [[ ${ERRORS} -ne 0 ]]; then
    echo "FAIL"
    exit 1
fi

# If we make it here, it means that no problems were found
echo "PASS"
exit 0
