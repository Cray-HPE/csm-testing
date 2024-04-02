#!/bin/bash
#
# MIT License
#
# (C) Copyright 2021-2024 Hewlett Packard Enterprise Development LP
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

# External DNS resolution is best tested by checking if the configured LDAP server hostname can be resolved.
# Pass if LDAP are not configured.
# Fail if Unbound is not configured.
# Fail if the LDAP providerId is configured but the LDAP connectionURL is not.
# Pass/Fail based on whether the LDAP server hostname can be resolved.

set -uo pipefail

function err_echo
{
    echo "ERROR: $*" >&2
}

function err_exit
{
    local exitcode
    exitcode=$1
    shift
    err_echo "$*"
    exit $exitcode
}

function run_cmd
{
    "$@" && return 0
    err_echo "Command failed with return code $?: $*"
    return 1
}


# Get the SYSTEM_DOMAIN from cloud-init
SYSTEM_NAME=$(run_cmd craysys metadata get system-name) || exit 10
echo "SYSTEM_NAME=${SYSTEM_NAME}"
SITE_DOMAIN=$(run_cmd craysys metadata get site-domain) || exit 20
echo "SITE_DOMAIN=${SITE_DOMAIN}"
SYSTEM_DOMAIN=${SYSTEM_NAME}.${SITE_DOMAIN}
echo "SYSTEM_DOMAIN=${SYSTEM_DOMAIN}"

# Use the CMN LB/Ingress
INGRESS="https://auth.cmn.${SYSTEM_DOMAIN}"
echo "INGRESS=${INGRESS}"

function get_master_token {
    MASTER_USERNAME=$(kubectl get secret -n services keycloak-master-admin-auth -ojsonpath='{.data.user}' | base64 -d) ||
        err_exit 30 "Failed getting keycloak-master-admin-auth user name"
    [[ -n "${MASTER_USERNAME}" ]] || err_exit 35 "keycloak-master-admin-auth user name is blank"
    MASTER_PASSWORD=$(kubectl get secret -n services keycloak-master-admin-auth -ojsonpath='{.data.password}' | base64 -d) ||
        err_exit 40 "Failed getting keycloak-master-admin-auth user password"
    [[ -n "${MASTER_PASSWORD}" ]] || err_exit 45 "keycloak-master-admin-auth user password is blank"

    curl -ks -d client_id=admin-cli -d username=$MASTER_USERNAME --data-urlencode password="$MASTER_PASSWORD" \
            -d grant_type=password ${INGRESS}/keycloak/realms/master/protocol/openid-connect/token \
        | jq -r '.access_token' || err_exit 50 "Failed getting authentication token from keycloak"
}

FORWARD_ADDR=$(kubectl -n services get cm cray-dns-unbound -o jsonpath='{.data.unbound\.conf}' \
                | grep "forward-zone:" -A 5 | yq r  - '"forward-zone"."forward-addr"') ||
    err_exit 60 "Failed getting forward address from Unbound"
echo "FORWARD_ADDR=${FORWARD_ADDR}"

[[ -n ${FORWARD_ADDR} ]] || err_exit 70 "Unbound must be configured for this test."

LDAP_PROVIDER=$(curl -s -H "Authorization: Bearer $(get_master_token)" ${INGRESS}/keycloak/admin/realms/shasta/components \
                    | jq -r '.[] | select(.providerId=="ldap")')

echo "LDAP_PROVIDER=${LDAP_PROVIDER}"
if [[ -z ${LDAP_PROVIDER} ]]; then 
    echo "SKIPPED: LDAP is not configured so unable to test external DNS."
    exit 0
fi

echo "Unbound and LDAP are configured" 
CONNECTION_URLS=$(curl -s -H "Authorization: Bearer $(get_master_token)" ${INGRESS}/keycloak/admin/realms/shasta/components \
                        | jq -r '.[] | select(.providerId=="ldap").config.connectionUrl[]') ||
    err_exit 80 "Unable to get LDAP connectionURL"

echo "CONNECTION_URLS=${CONNECTION_URLS}"
[[ -n ${CONNECTION_URLS} ]] ||
    err_exit 90 "LDAP provider is configured, but the connectionURL is missing from LDAP configuration."

FIRST_URL=$(echo "${CONNECTION_URLS}" | grep -Eo '//[^, /]+' | head -1 | tr -d /) ||
    err_exit 100 "No recognizable URLs found in LDAP connectionURL list"

echo "FIRST_URL=${FIRST_URL}"
[[ -n ${FIRST_URL} ]] ||
    err_exit 110 "Unable to extract first URL from LDAP connectionURL list"

echo "Attempting to resolve (A record) ${FIRST_URL}"
run_cmd host -4 -t A "${FIRST_URL}" && echo "PASSED" && exit 0

echo "Failed to resolve hostname '${FIRST_URL}'"
echo "FAILED"
exit 1
