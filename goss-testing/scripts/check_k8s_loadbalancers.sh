#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
# Checks that all Kubernetes LoadBalancer resources have an IP address
# Author: Chris Spiller <christian.spiller@hpe.com>

set -eu

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

function get_sls_network_data() {

  export TOKEN=$(curl -s -k -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=`kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d` https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token')

  NETWORKSJSON=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/networks)

  if [ -z "${NETWORKSJSON}" -o "${NETWORKSJSON}" == "" -o "${NETWORKSJSON}" == "null" ]; then
      echo >&2 "error: failed to get Networks from SLS"
      exit 1
  fi
  echo "$NETWORKSJSON"
}

function check_chn_config_from_sls() {

  defaultRoute=$(echo "$1" | jq -r --arg n "BICAN" '.[] | select(.Name == $n) | .ExtraProperties | .SystemDefaultRoute')

  # Check to see if the CHN is configured by checking the BICAN toggle in SLS
  chn_configured=0
  if [ "$defaultRoute" == "CHN" ]; then
    chn_configured=1
  else
    chn_configured=0
  fi

  echo "$chn_configured"
}

function check_cmn_config_from_sls() {

  cmn_config=$(echo "$1" | jq -r --arg n 'customer-management-static' '.[].ExtraProperties.Subnets[]| select(.MetalLBPoolName == $n)')

  # Check to see if the CHN is configured by checking the BICAN toggle in SLS
  cmn_configured=0
  if [[ -n "$cmn_config" ]]; then
    cmn_configured=1
  else
    cmn_configured=0
  fi

  echo "$cmn_configured"
}

function check_can_config_from_sls() {

  can_config=$(echo "$1" | jq -r --arg n "can_metallb_static_pool" '.[].ExtraProperties.Subnets[]| select(.Name == $n)')

  # Check to see if the CHN is configured by checking the BICAN toggle in SLS
  can_configured=0
  if [[ -n "$can_config" ]]; then
    can_configured=1
  else
    can_configured=0
  fi

  echo "$can_configured"
}

networks_json=$(get_sls_network_data)
chn_sls_check=$(check_chn_config_from_sls "$networks_json")
cmn_sls_check=$(check_cmn_config_from_sls "$networks_json")
can_sls_check=$(check_can_config_from_sls "$networks_json")

if [[ ${chn_sls_check} -eq 1 ]]
# CHN is configured and CMN is configured
then
    if [[ ${print_results} -eq 1 ]]
    then
        echo 'INFO: CHN is configured, excluding istio-ingressgateway-can and cray-oauth2-proxies-customer-access-ingress LoadBalancers'
        printf '\n%-16s %-35s %-15s %-4s\n' "NAMESPACE" "LOADBALANCER" "IPADDRESS" "STATUS"
    fi
    kubectl get service -A | grep LoadBalancer | grep -Ev "istio-ingressgateway-can|cray-oauth2-proxies-customer-access-ingress" | awk '{print $1" "$2" "$5}' | \
    while read namespace loadbalancer ip
    do
        if [[ ${print_results} -eq 1 ]]
        then
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then status='PASS'; else status='*FAIL*'; fi
            printf '%-16s %-35s %-15s %-8s\n' ${namespace} ${loadbalancer} ${ip} "${status}"
        else
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'PASS'; else echo 'FAIL'; fi
        fi
    done
elif [[ ${chn_sls_check} -eq 0 && ${cmn_sls_check} -eq 1 ]]
then
# CHN is not configured and CMN is configured
    if [[ ${print_results} -eq 1 ]]
    then
        echo 'INFO: CHN is not configured, excluding istio-ingressgateway-chn and cray-oauth2-proxies-customer-high-speed-ingress LoadBalancers'
        echo 'INFO: CMN is configured, including CMN LoadBalancers'
        printf '\n%-16s %-35s %-15s %-4s\n' "NAMESPACE" "LOADBALANCER" "IPADDRESS" "STATUS"
    fi
    kubectl get service -A | grep LoadBalancer | grep -Ev "istio-ingressgateway-chn|cray-oauth2-proxies-customer-high-speed-ingress" | awk '{print $1" "$2" "$5}' | \
    while read namespace loadbalancer ip
    do
        if [[ ${print_results} -eq 1 ]]
        then
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then status='PASS'; else status='*FAIL*'; fi
            printf '%-16s %-35s %-15s %-4s\n' ${namespace} ${loadbalancer} ${ip} "${status}"
        else
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'PASS'; else echo 'FAIL'; fi
        fi
    done
else
# CHN is not configured and CAN is configured
    if [[ ${print_results} -eq 1 ]]
    then
        echo 'INFO: CHN is not configured, excluding istio-ingressgateway-chn and cray-oauth2-proxies-customer-high-speed-ingress LoadBalancers'
        echo 'INFO: CAN is configured, including CAN LoadBalancers'
        printf '\n%-16s %-35s %-15s %-4s\n' "NAMESPACE" "LOADBALANCER" "IPADDRESS" "STATUS"
    fi
    kubectl get service -A | grep LoadBalancer | grep -Ev "istio-ingressgateway-chn|cray-oauth2-proxies-customer-high-speed-ingress|cmn" | awk '{print $1" "$2" "$5}' | \
    while read namespace loadbalancer ip
    do
        if [[ ${print_results} -eq 1 ]]
        then
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then status='PASS'; else status='*FAIL*'; fi
            printf '%-16s %-35s %-15s %-4s\n' ${namespace} ${loadbalancer} ${ip} "${status}"
        else
            if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'PASS'; else echo 'FAIL'; fi
        fi
    done
fi
