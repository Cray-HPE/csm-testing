#!/bin/bash
# Copyright 2014-2021 Hewlett Packard Enterprise Development LP
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