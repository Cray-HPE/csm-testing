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

# Checks that the iPXE pod responsible for generating x86-64 binaries is running
# The exact nature of this check varies based on whether the system is running
# CSM 1.4 or if it is running CSM 1.5 or later. Since this check is run during upgrades,
# either may be the case.

# Usage: check_ipxe_x86_64_pod_is_running.sh [-v]
#
# -v    Use set -x to produce verbose output

# If it passes, this script ends by printing PASSED and exiting with a 0 exit code.
# Otherwise, it exits non-0.

# -e :          Exit immediately on error
# -o pipefail : The exit code of a command pipeline is equal to the highest exit code of any
#               command in the pipeline (used to prevent errors in the middle of a pipeline
#               from being lost)
# -u :          Treat unset variables as errors
set -euo pipefail

if [[ $# -eq 1 && $1 == -v ]]; then
  # -x :          Echo commands being run
  set -x
elif [[ $# -ne 0 ]]; then
  echo "usage: check_ipxe_x86_64_pod_is_running.sh [-v]" >&2
  exit 2
fi

function err_exit {
  echo "ERROR: $*" >&2
  exit 1
}

# Get a temporary file to redirect where we can redirect the kubectl output
# That way we can display the entire output, and also check it to make sure the pod is running
tmpfile=$(mktemp)

echo "Temporary file is '${tmpfile}'"

# List pre-CSM 1.5-style iPXE pods:
kubectl get pods -n services -l 'app.kubernetes.io/name=cray-ipxe' --ignore-not-found | tee "${tmpfile}"

# Append CSM 1.5+-style x86-64 iPXE pods:
kubectl get pods -n services -l 'app.kubernetes.io/name=cray-ipxe-x86-64' --ignore-not-found | tee -a "${tmpfile}"

passed=Y

# grep the status column to make sure it is running.
awk '{ print $3 }' "${tmpfile}" | grep -q Running || passed=N

# Delete the temporary file, if it exists (it should, but a healthy dose of paranoia is good for the soul)
if [[ -f ${tmpfile} ]]; then
  rm ${tmpfile}
fi

[[ ${passed} == Y ]] || err_exit "iPXE pod status does not appear to be Running"

echo "PASSED"
exit 0
