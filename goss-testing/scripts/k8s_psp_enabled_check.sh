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

# Validate that PodSecurityPolicy is enabled for all kube-apiserver pods in the kube-system namespace
# Return 0 if the check passes, non-0 otherwise

# This script accepts no arguments
if [[ $# -ne 0 ]]; then
    echo "usage: k8s_psp_enabled_check.sh" 1>&2
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
TMPFILE=$(mktemp /tmp/.k8s_psp_enabled.$$.XXXXXX.tmp)

# TMPFILE should now point to our temporary file
[[ -n ${TMPFILE} ]]
[[ -f ${TMPFILE} ]]

# Write the list of kube-apiserver pod names to the screen and the temporary file
kubectl get pods -n kube-system -l component=kube-apiserver -o custom-columns=:metadata.name --no-headers=true | tee "${TMPFILE}"

# We will count the pods as we check them. The test will fail if no pods were found
COUNT=0

for PODNAME in $(cat "${TMPFILE}"); do
    let COUNT+=1
    
    # Describe the pod, writing to the screen and the temporary file
    kubectl describe -n kube-system pod "${PODNAME}" | tee "${TMPFILE}"

    # Check for string we expect to see if PodSecurityPolicy is enabled. This grep command will fail if the string is absent, causing the test to fail.
    grep -E '\-\-enable-admission-plugins=.*PodSecurityPolicy' "${TMPFILE}"
done

# We expect to have checked at least one pod (probably the actual expected number is higher, but for the purposes of this test, we just want to make sure we
# actually checked something
[[ $COUNT -gt 0 ]]

# Remove the temporary file. On the off chance that this command fails, we do not want to fail the test. Hence the || true.
rm "${TMPFILE}" || true

# If we make it here, it means that no problems were found
echo "PASS"
exit 0
