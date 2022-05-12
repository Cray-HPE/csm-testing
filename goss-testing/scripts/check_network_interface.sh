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

[ $# -eq 1 ] || err_exit 5 "Test requires exactly 1 argument but received $#: $*"
[ -n "$1" ] || err_exit 7 "Argument to test may not be blank"

TESTIF=$1

echo "Test interface: $TESTIF"

if ! command -v kubectl > /dev/null || [ ! -r /etc/kubernetes/admin.conf ]; then
    echo "Cannot determine the configured user network on this node."
    USER_NETWORK="none"
else
    SECRET=$(kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d) ||
        err_exit 10 "Command pipeline failed with return code $?: kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d"
    if [ -z "$SECRET" ]; then
        err_exit 12 "Failed to retrieve admin-client-auth secret"
    fi

    TOKEN=$(curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret="$SECRET" https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token') ||
        err_exit 15 "Command pipeline failed with return code $?: curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=XXXXXX https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token'"
    if [ -z "$TOKEN" ] || [ "$TOKEN" == null ]; then
        err_exit 17 "Failed to retrieve token from https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
    fi

    # check SLS Networks data for BiCAN toggle
    USER_NETWORK=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN | jq -r .ExtraProperties.SystemDefaultRoute | tr '[:upper:]' '[:lower:]')
    if [ -z "$USER_NETWORK" ] || [ "$USER_NETWORK" == null ]; then
        err_exit 18 "Failed to retrieve user network from SLS"
    fi
fi

echo "USER_NETWORK = $USER_NETWORK"

if [[ "$TESTIF" =~ .*can0 ]]; then
    if [[ "$TESTIF" =~ .*"$USER_NETWORK".* ]]; then
        ip link show dev $TESTIF || err_exit 20 "Command pipeline failed with return code $?: ip link show dev $TESTIF"
    else
        echo "Skipping test for $TESTIF because user network is $USER_NETWORK"
    fi
else
    ip link show dev $TESTIF || err_exit 20 "Command pipeline failed with return code $?: ip link show dev $TESTIF"
fi

echo "PASS"
exit 0
