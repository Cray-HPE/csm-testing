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

TMPFILE=/tmp/check_bgp_neighbors_established.$$.$RANDOM.tmp

function cleanup
{
    if [[ -f $TMPFILE ]]; then
        rm -f $TMPFILE || echo "WARNING: Unable to remove temporary file $TMPFILE" 1>&2
    fi
}

function err_exit
{
    local rc
    rc=$1
    shift
    echo "ERROR: $*" 1>&2
    cleanup
    echo "FAIL"
    exit $rc
}

SECRET=$(kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d) ||
    err_exit 10 "Command pipeline failed with return code $?: kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d"
# We omit the client secret from the error message, so it is not recorded in the log.
# Ideally we would not be passing it to curl on the command line either.
TOKEN=$(curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret="$SECRET" https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token') ||
    err_exit 15 "Command pipeline failed with return code $?: curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=XXXXXX https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token'"
# check if metalLB configmap exists
echo "Checking for cofigmap called metallb." > $TMPFILE
kubectl -n metallb-system get cm metallb 2>&1 |grep -i error|wc -l >> $TMPFILE
metallb_cm=$(kubectl -n metallb-system get cm metallb 2>&1 |grep -i error|wc -l)

# If error checking for metallb configmap
if [ "$metallb_cm" -gt "0" ];then
	metallb_check="0"
else
    metallb_check="1"
fi

# check SLS Networks data for BiCAN toggle
echo "Checking for BiCAN toggle."  >> $TMPFILE
curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN|jq -r .ExtraProperties.SystemDefaultRoute | grep -e CHN -e CAN |wc -l >> $TMPFILE
sls_network_check=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN|jq -r .ExtraProperties.SystemDefaultRoute | grep -e CHN -e CAN |wc -l)

if [ -z "$SW_ADMIN_PASSWORD" ]; then
    echo "******************************************"
    echo "******************************************"
    echo "**** Enter SSH password of switches: ****"
    read -t180 -sp ""  SW_ADMIN_PASSWORD
    echo
fi

# We really shouldn't be passing a password in plaintext on the command line, but as long as we are, at least
# we won't also include it in the error message on failure
# RFE: https://jira-pro.its.hpecorp.net:8443/browse/CASMNET-880

if [ "$metallb_check" -eq "0" ] || [ "$sls_network_check" -eq "0" ];then
    # csm-1.0 networking
    echo "Running: canu validate network bgp --network nmn --password XXXXXXXX"
    canu validate network bgp --network nmn --password $SW_ADMIN_PASSWORD ||
        err_exit 10 "canu validate network bgp --network nmn failed (rc=$?)"
else
    # csm-1.2+ networking
    echo "Running: canu validate network bgp --network all --password XXXXXXXX"
    canu validate network bgp --network all --password $SW_ADMIN_PASSWORD ||
        err_exit 20 "canu validate network bgp --network all failed (rc=$?)"
fi
echo "PASS"
cleanup
exit 0
