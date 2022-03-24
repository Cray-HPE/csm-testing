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

TOKEN=$(curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=`kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d` https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token')

# check if metalLB configmap exists
kubectl -n metallb-system get cm metallb 2>&1 |grep -i error|wc -l > $TMPFILE ||
    err_exit 10 "ERROR: Command failed (rc=$?): kubectl -n metallb-system get cm metallb 2>&1 |grep -i error|wc -l " >> $TMPFILE
metallb_cm=$(kubectl -n metallb-system get cm metallb 2>&1 |grep -i error|wc -l)

# Check for BiCAN configs in MetalLB configmap
if [ "$metallb_cm" -gt "0" ];then
	metallb_check="0"
else
    kubectl -n metallb-system get cm metallb -o jsonpath='{.data.config}' | grep customer-management | wc -l >> $TMPFILE ||
        err_exit 20 "ERROR: Command failed (rc=$?): kubectl -n metallb-system get cm metallb -o jsonpath='{.data.config}' | grep customer-management | wc -l" > TMPFILE
	metallb_check=$(kubectl -n metallb-system get cm metallb -o jsonpath='{.data.config}' | grep customer-management | wc -l)
fi

# check SLS Networks data for BiCAN toggle
curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN|jq -r .ExtraProperties.SystemDefaultRoute | grep -e CHN -e CAN |wc -l >> $TMPFILE ||
    err_exit 30 "ERROR: Command failed (rc=$?): curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN|jq -r .ExtraProperties.SystemDefaultRoute | grep -e CHN -e CAN |wc -l" >> $TMPFILE
sls_network_check=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/BICAN|jq -r .ExtraProperties.SystemDefaultRoute | grep -e CHN -e CAN |wc -l)

# check spine switch motd for csm version
ssh -o ConnectTimeout=1 -o BatchMode=yes-o StrictHostKeyChecking=no -o PasswordAuthentication=no admin@sw-spine-001 "" 2>&1 | grep CSM | awk '{ print $4 }' >> $TMPFILE ||
    err_exit 40 "ERROR: Command failed (rc=$?): ssh -o ConnectTimeout=1 -o BatchMode=yes-o StrictHostKeyChecking=no -o PasswordAuthentication=no admin@sw-spine-001 "" 2>&1 | grep CSM | awk '{ print $4 }' " >> $TMPFILE
switch_motd_check=$(ssh -o ConnectTimeout=1 -o BatchMode=yes -o StrictHostKeyChecking=no -o PasswordAuthentication=no admin@sw-spine-001 "" 2>&1 | grep CSM | awk '{ print $4 }' )

# We really shouldn't be passing a password in plaintext on the command line, but as long as we are, at least
# we won't also include it in the error message on failure
# RFE: https://jira-pro.its.hpecorp.net:8443/browse/CASMNET-880

if [ "$metallb_check" -eq "0" ] && [ "$sls_network_check" -eq "0" ] || [ "$switch_motd_check" == "1.0" ];then
    # csm-1.0 networking
    echo "Running: canu validate network bgp --network nmn --password XXXXXXXX"
    canu validate network bgp --network nmn --password {{.Env.SW_ADMIN_PASSWORD}} ||
        err_exit 50 "canu validate network bgp --network nmn failed (rc=$?)"
else
    # csm-1.2+ networking
    echo "Running: canu validate network bgp --network all --password XXXXXXXX"
    canu validate network bgp --network all --password {{.Env.SW_ADMIN_PASSWORD}} ||
        err_exit 60 "canu validate network bgp --network all failed (rc=$?)"
fi
echo "PASS"
cleanup
exit 0
