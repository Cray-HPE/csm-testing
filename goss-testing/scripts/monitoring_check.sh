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
# Verify that the monitoring URLs are redirecting and responding.

failFlag=0
monitoring="$(kubectl get vs -A --no-headers=false | awk '{print $1","$4}' | grep "kiali\|prometheus\|alertmanager\|grafana\|jaeger")"

for m in $monitoring
do
    # namespace and url
    m_ns="$(echo $m | awk -F, '{print $1}')"
    m_url="$(echo $m | awk -F, '{print $2}' | sed 's/[][]//g' | tr -d '"')"

    # Check for 302 redirect from oauth2-proxy to the Keycloak login page
    response=$(curl -i -s -S -L --max-redirs 1 https://$m_url/ | grep -c "HTTP/1.1 302")

    if [[ $response -ne 1 ]]; then
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
