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

ci_cert=""
etc_cert=""

function remove_tmpfiles
{
  local tmpfile
  for tmpfile in "${etc_cert}" "${ci_cert}" ; do
    if [[ -n ${tmpfile} && -f ${tmpfile} ]]; then
      rm "${tmpfile}" || echo "WARNING: Command failed: rm '${tmpfile}'" >&2
    fi
  done
}

function do_test
{
  ci_cert=$(mktemp /tmp/goss-sorted-cloud-init-cert-XXX.txt) || return 10
  curl -s http://10.92.100.71:8888/meta-data | jq -r '.Global."ca-certs".trusted[]' | sed '/^$/d' | sort > "${ci_cert}" || return 20
  etc_cert=$(mktemp /tmp/goss-sorted-etc-cert-XXX.txt) || return 30
  sed '/^$/d' /etc/pki/trust/anchors/platform-ca-certs.crt | sort > "${etc_cert}" || return 40
  diff "${etc_cert}" "${ci_cert}"
  return $?
}

do_test
rc=$?
remove_tmpfiles
if [[ $rc -eq 0 ]]; then
  echo PASSED
fi
exit ${rc}
