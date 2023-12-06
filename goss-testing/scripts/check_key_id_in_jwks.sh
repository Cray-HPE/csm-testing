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

jwt=$(/usr/bin/heartbeat-spire-agent api fetch jwt -socketPath /var/lib/spire/agent.sock -audience goss-test \
  | head -n2 | awk -F. 'FNR==2{sub(/^[ \t]+/, ""); print $1}') || exit 10

# Make sure the value of the variable is not empty
[[ -n ${jwt} ]] || exit 20

# The base64 decoder will be unhappy if we give it a string whose length (in characters) is not a multiple of 4
# (See: https://unix.stackexchange.com/questions/631501/base64-d-decodes-but-says-invalid-input)
# To avoid this, if the length is not already a multiple of 4, it should have = characters added at the end, to pad it out.
jwt_len=${#jwt}
len_mod_4=$((jwt_len % 4))
jwt_len=$((jwt_len + 4 - len_mod_4))
jwt="${jwt}==="

jwt_kid=$(echo ${jwt::jwt_len} | base64 -d | jq -r .kid) || exit 30

# Make sure the value we found is non-empty
[[ -n ${jwt_kid} ]] || exit 40

kubectl exec -n spire spire-postgres-0 -c postgres -- curl http://cray-spire-jwks/keys \
  | jq -r '.[][].kid' | grep -Eq "^${jwt_kid}$" || exit 50

echo "PASSED"
exit 0
