#!/bin/bash
#
# MIT License
#
# (C) Copyright 2014-2022 Hewlett Packard Enterprise Development LP
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
# Verify configmaps managed by the trustedcerts operator
# exist, exit 0 if they do, 1 otherwise. 

set -e -o pipefail
QUERY_NS="${1:-"pki-operator"}"
QUERY_TC="${2:-"shasta-platform-1-3-compat"}"

CERT_MAPS=$(kubectl get trustedcertificates \
            -n "$QUERY_NS" "$QUERY_TC" \
            -o json | jq '.spec.destinations[] | select(.type=="configmap") | [.config.namespace, .config.name] | @csv' | sed -e 's/"//g' -e 's/\\//g')

for CERT_MAP in $CERT_MAPS
do
   NS="$(echo $CERT_MAP | awk -F, '{print $1;}')"
   CM="$(echo $CERT_MAP | awk -F, '{print $2;}')"
   kubectl get cm -n "$NS" "$CM" &> /dev/null || exit 1
done