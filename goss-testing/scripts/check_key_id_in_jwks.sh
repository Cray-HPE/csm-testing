#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2023, 2025 Hewlett Packard Enterprise Development LP
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

jwt=$(/usr/bin/heartbeat-spire-agent api fetch jwt -socketPath /var/lib/spire/agent.sock -audience goss-test -output json \
  | jq -r '.[0]?.svids[0]?.svid') || exit 10

# Make sure the value of the variable is not empty
[[ -n ${jwt} ]] || exit 20

# Split the JWT into its three parts
jwt_header=$(echo "${jwt}" | cut -d '.' -f1)
# jwt_payload=$(echo "${jwt}" | cut -d '.' -f2)
# jwt_signature=$(echo "${jwt}" | cut -d '.' -f3) 

# Decode the header (header and payload are base64-encoded; signature is not typically decoded)
# The base64 decoder will be unhappy if we give it a string whose length (in characters) is not a multiple of 4
# (See: https://unix.stackexchange.com/questions/631501/base64-d-decodes-but-says-invalid-input)
# To avoid this, if the length is not already a multiple of 4, it should have = characters added at the end, to pad it out.
decode_base64() {
  local input=$1
  # to avoid this use the following logic:
  # length % 4 = 2 -> Add 2 = characters
  # length % 4 = 3 -> Add 1 = character
  # length % 4 = 0 -> No padding needed
  local len_mod_4=$(( ${#input} % 4 ))
  if [ $len_mod_4 -ne 0 ]; then
    # use printf to append the required number of = characters
    input="${input}$(printf '=%.0s' $(seq 1 $((4 - len_mod_4))))"
  fi
  echo "${input}" | base64 -d | jq . 2>/dev/null
}

# Decode the header
decoded_header=$(decode_base64 "${jwt_header}")

# Extract the "kid" field from the header
jwt_kid=$(echo "${decoded_header}" | jq -r .kid) || exit 30

# Make sure the value we found is non-empty
[[ -n ${jwt_kid} ]] || exit 40

kubectl exec -n spire cray-spire-postgres-0 -c postgres -- curl -s http://cray-spire-jwks/keys \
  | jq -r '.[][].kid' | grep -Eq "^${jwt_kid}$" || exit 50

echo "PASSED"
exit 0
