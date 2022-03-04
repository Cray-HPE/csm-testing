#!/usr/bin/env bash
# MIT License
#
# (C) Copyright [2022] Hewlett Packard Enterprise Development LP
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

# Checks that expected static routes are on the NCNs. 

set -eu

function get_client_secret() {
    # Kubernetes is not installed on all storage nodes. If executing on a storage
    # node, verify a functional master or worker node. Obtain client secret
    # from identified NCN Kubernetes node.

    activeKubNcnNode=""
    hostNodeType=""
    clientSecret=""
    listOfKubNcns=""
    sshOptions="-q -o StrictHostKeyChecking=no"

    # If executing on a storage node, determine an active NCN Kubernetes node:
    hostNodeType=$(echo $(hostname) | awk '/ncn-s/ {print "storage"}')
    if [[ $hostNodeType == "storage" ]]
    then
        # Determine active non-storage NCN node:
        listOfKubNcns=$(cat /etc/hosts | grep -ohE "ncn-[mw]([0-9]{3})" | awk '!a[$0]++' | sort)
        for node_i in $listOfKubNcns;
        do
            ssh $sshOptions $node_i 'kubectl get nodes' >/dev/null
            if [[ $? -eq 0 ]]
            then
                activeKubNcnNode=$node_i
                break
            fi
        done
    fi

    # Get client secret:
    if [[ -z $activeKubNcnNode ]]
    then
        clientSecret=$(kubectl get secrets admin-client-auth \
                               -o jsonpath='{.data.client-secret}' | base64 -d)
    else
        clientSecret=$(ssh $sshOptions $activeKubNcnNode \
                           'kubectl get secrets admin-client-auth \
                           -o jsonpath='{.data.client-secret}' | base64 -d')
    fi
    echo $clientSecret
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
  echo $TOKEN
}

print_results=0
while getopts ph options
do
    case "${options}" in 
        p) print_results=1
           ;;
        h) echo "usage: ${0}       # Only print 'PASS upon success"
           echo "       ${0} -p    # Print all results and errors if found. Use for manual check."
           exit 3
           ;;
       \?) echo "usage: ${0}       # Only print 'PASS upon success"
           echo "       ${0} -p    # Print all results and errors if found. Use for manual check."
           exit 3
           ;;
    esac
done

get_token

# Get the NMN gateway
nmngw=$(craysys metadata get --level node ipam | jq .nmn.gateway | tr -d '\"')
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: NMN gateway is $nmngw"
fi
if [ "$nmngw" == "null" ]; then 
    echo "FAIL"
    exit 1
fi

# Get the HMN gateway
hmngw=$(craysys metadata get --level node ipam | jq .hmn.gateway | tr -d '\"')
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: HMN gateway is $hmngw"
fi
if [ "$hmngw" == "null" ]; then 
    echo "FAIL"
    exit 1
fi

# Check for NMNLB static route
nmnlb_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/NMNLB | jq -r '.ExtraProperties.Subnets[0].CIDR')
nmnlb_passed=false
ip route | grep -q "$nmnlb_cidr via $nmngw dev bond0.nmn0" && nmnlb_passed=true
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: NMNLB CIDR is $nmnlb_cidr - route found = $nmnlb_passed"
fi

# Check for NMN_RVR static route
nmnrvr_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/NMN_RVR | jq -r '.ExtraProperties.Subnets[0].CIDR')
nmnrvr_passed=false
ip route | grep -q "$nmnrvr_cidr via $nmngw dev bond0.nmn0" && nmnrvr_passed=true
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: NMNLB CIDR is $nmnrvr_cidr - route found = $nmnrvr_passed"
fi

# Check for HMNLB static route
hmnlb_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/HMNLB | jq -r '.ExtraProperties.Subnets[0].CIDR')
hmnlb_passed=false
ip route | grep -q "$hmnlb_cidr via $hmngw dev bond0.hmn0" && hmnlb_passed=true
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: HMNLB CIDR is $hmnlb_cidr - route found = $hmnlb_passed"
fi

# Check for HMN_RVR static route
hmnrvr_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/HMN_RVR | jq -r '.ExtraProperties.Subnets[0].CIDR')
hmnrvr_passed=false
ip route | grep -q "$hmnrvr_cidr via $hmngw dev bond0.hmn0" && hmnrvr_passed=true
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: HMNLB CIDR is $hmnrvr_cidr - route found = $hmnrvr_passed"
fi

# Check for MTL static route
mtl_cidr=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks/MTL | jq -r '.ExtraProperties.Subnets[0].CIDR')
mtl_passed=false
ip route | grep -q "$mtl_cidr via $nmngw dev bond0.nmn0" && mtl_passed=true
if [[ ${print_results} -eq 1 ]]; then
    echo "INFO: MTL CIDR is $mtl_cidr - route found = $mtl_passed"
fi

if $nmnlb_passed && $hmnlb_passed && $mtl_passed && $nmnrvr_passed && $hmnrvr_passed; then
    echo "PASS"
    status=0
else
    echo "FAIL"
    status=1
fi

exit $status

