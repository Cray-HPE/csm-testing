#!/bin/bash
# This script validates that the platform-ca-certs.crt file matches what is in
# BSS. Since the meta-data request may return the certificates in a different
# order than what was originally provided this will check against multiple
# order differences.
# Copyright 2014-2021 Hewlett Packard Enterprise Development LP

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
    if diff <(echo "$TRUSTEDDATA" | jq -r \""${STRING}"\" | sed '/^$/d') "$LOCALCA" >/dev/null; then
      exit 0
    fi
  done
done
exit 1
