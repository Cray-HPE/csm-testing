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

# This file is sourced by automated testing scripts.

# No shebang line at the top of the file, because this is not intended to be executed, only included as a source in other Bash scripts.
# The following line lets the linter know how to appropriately check this file.
# shellcheck shell=bash

set -o pipefail

function vault_check {
    # Return 0 if healthy and unsealed. Return 1 otherwise.
    local VAULTPOD
    if ! VAULTPOD=$(kubectl get pods -n vault | grep -E 'cray-vault-[[:digit:]].*Running' | awk 'NR==1{print $1}'); then
        echo "Vault appears to be unhealthy" >&2
        return 1
    fi
    if [ "$(kubectl -n vault exec -i ${VAULTPOD:-cray-vault-0} -c vault -- env VAULT_ADDR=http://cray-vault.vault:8200 VAULT_FORMAT=json vault status  | jq '.sealed')" = false ]; then
        echo "Vault appears to be healthy and unsealed"
        return 0
    fi
    echo "Vault appears to be sealed" >&2
    return 1
}

function set_sw_admin_password_if_needed {
    # If the SW_ADMIN_PASSWORD variable is already set and non-empty, just return 0.
    # Otherwise, get it from Vault if possible. Return 0 if successful, 1 otherwise.
    local VAULT_PASSWD
    if [[ -n ${SW_ADMIN_PASSWORD} ]]; then
        echo "Using switch admin password from SW_ADMIN_PASSWORD environment variable"
        return 0
    fi
    vault_check || return 1
    if ! VAULT_PASSWD=$(kubectl -n vault get secrets cray-vault-unseal-keys -o json \
      | jq -r '.data["vault-root"]' |  base64 -d); then
        echo "Unable to get Vault password from cray-vault-unseal-keys Kubernetes secret" >&2
        return 1
    fi
    if ! SW_ADMIN_PASSWORD=$(kubectl -n vault exec -i cray-vault-0 -c vault -- \
      env VAULT_TOKEN="$VAULT_PASSWD" VAULT_ADDR=http://127.0.0.1:8200 \
      VAULT_FORMAT=json vault kv get secret/net-creds/switch_admin \
      | jq -r  .data.admin); then
        echo 'Detected Vault is running.  Missing switch admin password from vault.  Please run the following commands:
        VAULT_PASSWD=$(kubectl -n vault get secrets cray-vault-unseal-keys -o json | jq -r '"'"'.data["vault-root"]'"'"' |  base64 -d)
        alias vault="kubectl -n vault exec -i cray-vault-0 -c vault -- env VAULT_TOKEN=\"$VAULT_PASSWD\" VAULT_ADDR=http://127.0.0.1:8200 VAULT_FORMAT=json vault"
        vault kv put secret/net-creds/switch_admin admin=SWITCH_ADMIN_PASSWORD' >&2
        return 1
    fi
    echo "Switch admin password retrieved from Vault"
    return 0
}
