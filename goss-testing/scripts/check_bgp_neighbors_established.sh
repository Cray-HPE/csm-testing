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

# On failures we will exit with unusual exit codes, to help make it clearer where the test failed

# This test uses command pipelines, so we will set pipefail. That way the pipelines will
# fail (i.e. exit non-0) if any of the commands in the chain fail
set -o pipefail



function err_exit
{
    local rc
    rc=$1
    shift
    echo "ERROR: $*" 1>&2
    echo "FAIL"
    exit $rc
}

SECRET=$(kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d) ||
    err_exit 10 "Command pipeline failed with return code $?: kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d"
# We omit the client secret from the error message, so it is not recorded in the log.
# Ideally we would not be passing it to curl on the command line either.
TOKEN=$(curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret="$SECRET" https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token') ||
    err_exit 15 "Command pipeline failed with return code $?: curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=XXXXXX https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token'"

# Set vault_check to 0 if healthy and unsealed.  Set to 0 otherwise.
VAULTPOD=$(kubectl get pods -n vault | grep -E 'cray-vault-[[:digit:]].*Running' | awk 'NR==1{print $1}')
if [ "$(kubectl -n vault exec -i ${VAULTPOD:-cray-vault-0} -c vault -- env VAULT_ADDR=http://cray-vault.vault:8200 VAULT_FORMAT=json vault status  | jq '.sealed')" = false ]; then
    vault_check=0
else
    vault_check=1
fi

# check if metalLB configmap exists
# Set metallb_check to 1 if we cannot get the metallb configmap from Kubernetes. Set to 0 otherwise.
if kubectl -n metallb-system get cm metallb ; then
    metallb_check=0
else
    metallb_check=1
fi

# check SLS Networks data for BiCAN toggle
curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN |
    jq -r .ExtraProperties.SystemDefaultRoute |
    grep -e CHN -e CAN
# Set sls_network_check to 0 if the BICAN endpoint responds and
# has the CAN or CHN strings in its ExtraProperties.SystemDefaultRoute field. Otherwise set to 1
[[ $? -eq 0 ]] && sls_network_check=0 || sls_network_check=1

# vault is running and checking for switch admin password in vault
if [ -z "$SW_ADMIN_PASSWORD" ] && [ "$vault_check" -lt "1" ]; then
    VAULT_PASSWD=$(kubectl -n vault get secrets cray-vault-unseal-keys -o json | jq -r '.data["vault-root"]' |  base64 -d)
    SW_ADMIN_PASSWORD=$(kubectl -n vault exec -i cray-vault-0 -c vault -- env VAULT_TOKEN="$VAULT_PASSWD" VAULT_ADDR=http://127.0.0.1:8200 VAULT_FORMAT=json vault kv get secret/net-creds/switch_admin | jq -r  .data.admin) ||
        err_exit 20 'Detected Vault is running.  Missing switch admin password from vault.  Please run the following commands:
        VAULT_PASSWD=$(kubectl -n vault get secrets cray-vault-unseal-keys -o json | jq -r .data["vault-root"] |  base64 -d)
        alias vault="kubectl -n vault exec -i cray-vault-0 -c vault -- env VAULT_TOKEN=\"$VAULT_PASSWD\" VAULT_ADDR=http://127.0.0.1:8200 VAULT_FORMAT=json vault"
        vault kv put secret/net-creds/switch_admin admin=SWITCH_ADMIN_PASSWORD'
fi
# this is the case if vault is not running and env variable has not been set
if [ -z "$SW_ADMIN_PASSWORD" ] && [ "$vault_check" -gt "0" ]; then
    echo "******************************************"
    echo "******************************************"
    echo "**** Enter SSH password of switches: ****"
    read -t180 -sp ""  SW_ADMIN_PASSWORD
    echo
fi

# We really shouldn't be passing a password in plaintext on the command line, but as long as we are, at least
# we won't also include it in the error message on failure
# RFE: https://jira-pro.its.hpecorp.net:8443/browse/CASMNET-880

if [ "$metallb_check" -gt "0" ] || [ "$sls_network_check" -gt "0" ];then
    # csm-1.0 networking
    echo "Running: canu validate network bgp --network nmn --password XXXXXXXX"
    canu validate network bgp --network nmn --password $SW_ADMIN_PASSWORD ||
        err_exit 20 "canu validate network bgp --network nmn failed (rc=$?)"
else
    # csm-1.2+ networking
    echo "Running: canu validate network bgp --network all --password XXXXXXXX"
    canu validate network bgp --network all --password $SW_ADMIN_PASSWORD ||
        err_exit 25 "canu validate network bgp --network all failed (rc=$?)"
fi
echo "PASS"
exit 0
