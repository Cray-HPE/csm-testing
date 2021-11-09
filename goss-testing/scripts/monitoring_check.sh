#!/bin/bash
# Copyright 2021 Hewlett Packard Enterprise Development LP

# Verify that the monitoring urls are redirecting and responding.

failFlag=0
monitoring="$(kubectl get vs -A --no-headers=false | awk '{print $1","$4}' | grep "kiali\|prometheus\|alertmanager\|grafana\|jaeger")"

for m in $monitoring
do
    # namespace and url
    m_ns="$(echo $m | awk -F, '{print $1}')"
    m_url="$(echo $m | awk -F, '{print $2}' | sed 's/[][]//g' | tr -d '"')"

    # Check for 307 redirects (location oauth and keycloak)
    response=$(curl -i -s -S -L --max-redirs 2 https://$m_url/ | grep -c "HTTP/2 307")

    if [[ $response -ne 2 ]]; then
        echo "Monitoring url https://$m_url/ in namespace $m_ns failed to redirect for auth."
        failFlag=1
    fi

    # Check for 200 OK (istio-envoy)
    response=$(curl -i -s -S -L https://$m_url/ | grep "HTTP/2 200")

    if [[ -z $response ]]; then
	echo "Monitoring url https://$m_url/ in namespace $m_ns failed to respond with OK."
        failFlag=1
    fi

done

if [[ $failFlag -eq 0 ]]
then
    echo "PASS"
    exit 0
else
    echo "FAIL"
    exit 1
fi
