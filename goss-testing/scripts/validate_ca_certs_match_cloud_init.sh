#!/bin/bash
#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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

# This script validates that the platform-ca-certs.crt file matches what is in
# BSS. Since the meta-data request may return the certificates in a different
# order than what was originally provided this will check against multiple
# order differences.
# Copyright 2014-2022 Hewlett Packard Enterprise Development LP

set -euo pipefail

MAXARRAY=$(($(curl -s http://10.92.100.71:8888/meta-data | jq -r '.Global."ca-certs".trusted | length') - 1))
SERVER=http://10.92.100.71:8888/meta-data
LOCALCA=/etc/pki/trust/anchors/platform-ca-certs.crt
TRUSTEDDATA=$(curl -s "$SERVER" | jq -r '.Global."ca-certs".trusted')
TRUSTEDORDER=()

for i in $(seq 0 $MAXARRAY); do
  TRUSTEDORDER+=("\(.[${i}])")
done

# Iterate through all BSS trusted certificate sequences and test against the
# platforms file
for i in $(seq 0 $MAXARRAY); do
  for j in $(seq 0 $((MAXARRAY - 1))); do
    TMP=${TRUSTEDORDER[$j]}
    TRUSTEDORDER[$j]=${TRUSTEDORDER[$((j + 1))]}
    TRUSTEDORDER[$((j + 1))]=$TMP

    STRING=$(echo "${TRUSTEDORDER[@]}" | tr -d " ")
    if diff <(echo "$TRUSTEDDATA" | jq -r \""${STRING}"\" | sed '/^$/d' | sort) <(cat "${LOCALCA}" | sed '/^$/d' | sort) >/dev/null; then
      exit 0
    fi
  done
done
exit 1
