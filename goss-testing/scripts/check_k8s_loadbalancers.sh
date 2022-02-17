#!/usr/bin/env bash
# Copyright (C) 2021 Hewlett Packard Enterprise Development LP
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

# Check to see if the CHN is configured by checking for the existence of the customer-high-speed MetalLB pool
# If the CHN is not configured then the istio-ingressgateway-chn will not have an IP address and remain in a
# <pending> state.
chn_configured=0
if $(kubectl -n metallb-system get cm config -o jsonpath='{.data.config}' | grep -q customer-high-speed); then
    chn_configured=1
else
    chn_configured=0
fi

if [[ ${chn_configured} -eq 1 ]]
# CHN is configured
then
    if [[ ${print_results} -eq 1 ]]
    then 
        echo 'INFO: CHN is configured, istio-ingressgateway-chn and cray-oauth2-proxies-customer-high-speed-ingress should have an IP address'
        printf '\n%-16s %-35s %-15s %-4s\n' "NAMESPACE" "LOADBALANCER" "IPADDRESS" "STATUS"
    fi
    kubectl get service -A | grep LoadBalancer | awk '{print $1" "$2" "$5}' | \
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
else
# CHN is not configured
    if [[ ${print_results} -eq 1 ]]
    then 
        echo 'INFO: CHN is not configured, excluding istio-ingressgateway-chn and cray-oauth2-proxies-customer-high-speed-ingress LoadBalancers'
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
fi


