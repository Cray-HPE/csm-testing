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
# Checks that expected static routes are on the NCNs. 

set -euo pipefail

print_results=0
print_token=0

function echo_stdout
{
    if [[ ${print_results} -eq 1 ]]; then
        echo "$@"
    fi
}

function echo_stderr
{
    if [[ ${print_results} -eq 1 ]]; then
        echo "$@" 1>&2
    fi
}

function get_client_secret() {
    # Try to get a Kubernetes key locally.
    clientSecret=$(kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' 2>/dev/null)
    if [[ $? -ne 0 ]] || [[ -z $clientSecret ]]
    then
        echo_stderr "INFO: Unable to get client secret by running kubectl locally. Trying other NCNs."
    
        # Kubernetes is not installed on all storage nodes. Whether or not this is
        # a storage node, we may be able to get the client secret by checking the
        # master and worker NCNs on the system, or possibly ncn-s001 (where kubectl is
        # also usually configured).

        # Force public key authentication, so that it will never prompt for a password.
        # This is most likely to occur when trying to ssh to the PIT node.
        sshOptions=( "-q" \
                     "-o" "StrictHostKeyChecking=no" \
                     "-o" "PreferredAuthentications=publickey" )

        clientSecret=""
        for node_i in $(grep -ohE "ncn-(s001|[mw][0-9]{3})" /etc/hosts | sort -ur)
        do
            if [[ ${node_i} == $(hostname -s) ]]
            then
                # No need to SSH to ourself
                continue
            fi

            echo_stderr "INFO: Trying to SSH to ${node_i}"
            ssh "${sshOptions[@]}" "$node_i" date >/dev/null || continue

            echo_stderr "INFO: SSH succeeded. Trying to obtain client secret."
            clientSecret=$(ssh "${sshOptions[@]}" "$node_i" "kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}'")
            if [[ $? -eq 0 ]] && [[ -n $clientSecret ]]
            then
                echo_stderr "INFO: Client secret obtained"
                break
            fi
            clientSecret=""
        done
        if [[ -z $clientSecret ]]; then
            echo_stderr "ERROR: Unable to find NCN where client secret could be obtained"
            return 1
        fi
    fi
    echo -n "$clientSecret" | base64 -d
    return $?
}

function get_token() {
  cnt=0
  TOKEN=""
  endpoint="https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
  client_secret=$(get_client_secret)
  while [ "$TOKEN" == "" ]; do
    cnt=$((cnt+1))
    TOKEN=$(curl -k -s -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=$client_secret $endpoint)
    if [[ "$TOKEN" == *"error"* ]]; then
      TOKEN=""
      if [ "$cnt" -eq 5 ]; then
        break
      fi
      sleep 5
    else
      TOKEN=$(echo $TOKEN | jq -r '.access_token')
      break
    fi
  done
  if [[ $print_token -eq 1 ]]; then
    echo $TOKEN
  fi
}

function usage
{
  echo "usage: ${0}       # Only print 'PASS upon success"
  echo "       ${0} -p    # Print all results and errors if found. Use for manual check."
  echo "       ${0} -t    # Print all results and errors if found. Also print API token. Use for manual check."
  exit 3
}

while getopts hpt options
do
    case "${options}" in 
        h) usage
           ;;
        p) print_results=1
           ;;
        t) print_results=1
           print_token=1
           ;;
       \?) usage
           ;;
    esac
done

get_token

# Get the NMN gateway
nmngw=$(craysys metadata get --level node ipam | jq .nmn.gateway | tr -d '\"')
echo_stdout "INFO: NMN gateway is $nmngw"
if [ "$nmngw" == "null" ]; then 
    echo "FAIL"
    exit 1
fi

# Get the HMN gateway
hmngw=$(craysys metadata get --level node ipam | jq .hmn.gateway | tr -d '\"')
echo_stdout "INFO: HMN gateway is $hmngw"
if [ "$hmngw" == "null" ]; then 
    echo "FAIL"
    exit 1
fi

# Check for NMNLB static route
nmnlb_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/NMNLB | jq -r '.ExtraProperties.Subnets[0].CIDR')
nmnlb_passed=false
ip route | grep -q "$nmnlb_cidr via $nmngw dev bond0.nmn0" && nmnlb_passed=true
echo_stdout "INFO: NMNLB CIDR is $nmnlb_cidr - route found = $nmnlb_passed"

# Check for NMN_RVR static route
nmnrvr_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/NMN_RVR | jq -r '.ExtraProperties.Subnets[0].CIDR')
nmnrvr_passed=false
ip route | grep -q "$nmnrvr_cidr via $nmngw dev bond0.nmn0" && nmnrvr_passed=true
echo_stdout "INFO: NMNLB CIDR is $nmnrvr_cidr - route found = $nmnrvr_passed"

# Check for HMNLB static route
hmnlb_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/HMNLB | jq -r '.ExtraProperties.Subnets[0].CIDR')
hmnlb_passed=false
ip route | grep -q "$hmnlb_cidr via $hmngw dev bond0.hmn0" && hmnlb_passed=true
echo_stdout "INFO: HMNLB CIDR is $hmnlb_cidr - route found = $hmnlb_passed"

# Check for HMN_RVR static route
hmnrvr_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/HMN_RVR | jq -r '.ExtraProperties.Subnets[0].CIDR')
hmnrvr_passed=false
ip route | grep -q "$hmnrvr_cidr via $hmngw dev bond0.hmn0" && hmnrvr_passed=true
echo_stdout "INFO: HMNLB CIDR is $hmnrvr_cidr - route found = $hmnrvr_passed"

# Check for MTL static route
mtl_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/MTL | jq -r '.ExtraProperties.Subnets[0].CIDR')
mtl_passed=false
ip route | grep -q "$mtl_cidr via $nmngw dev bond0.nmn0" && mtl_passed=true
echo_stdout "INFO: MTL CIDR is $mtl_cidr - route found = $mtl_passed"

if $nmnlb_passed && $hmnlb_passed && $mtl_passed && $nmnrvr_passed && $hmnrvr_passed; then
    echo "PASS"
    status=0
else
    echo "FAIL"
    status=1
fi

exit $status
