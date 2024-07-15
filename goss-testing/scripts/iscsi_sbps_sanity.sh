#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP
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

# This script is to do some sanity tests for iSCSI based boot content 
# projection.

# shellcheck disable=SC2207,SC2143,SC2002

LIO_ACT=0

echo "Checking whether the node is configured with iSCSI"

ISCSI=$(kubectl get nodes --selector="iscsi=sbps,kubernetes.io/hostname=${HOSTNAME}" -o jsonpath='{.items[*].metadata.name}')

if [ -z "${ISCSI}" ]
then
    echo "iSCSI is not configured, exiting"
    exit 0
else
    echo "${HOSTNAME} is configured with iSCSI"
fi

# Verifying whether Marshal agent is running or not

echo "*******************************"
echo "Marshal agent is $(systemctl is-active sbps-marshal.service)"
echo "*******************************"

# Verifying whether LIO target(s) is active

LIO_ACT=$(targetcli /iscsi status | awk '{print $(NF)}')

if [[ "${LIO_ACT}" -gt 0 ]]
then
    echo "${LIO_ACT} LIO Target(s) is active"
else
    echo "LIO Target(s) is not active"
fi

echo "*******************************"

# Verify TCP service probes complete against all active portals (iSCSI)

PORTALS=($(ss -tnpl | grep ':3260 ' | awk '{ print $4 }' ))

if [[ -n "${PORTALS[*]}" ]]; then
    echo "iSCSI portals exist and are as below:"
    echo "-------------------------------"
    for portals in "${PORTALS[@]}"
    do
        echo "$portals"
    done
else
    echo "iSCSI portals do not exist, so exiting"
    exit 1
fi

echo "                         "

for portals in "${PORTALS[@]}"
do
    IP=$(echo "$portals" | cut -f1 -d":")
    if nmap -sS -p 3260 "${IP}" | grep 3260 | grep -q open
    then
        echo "$IP is open"
    else
        echo "$IP is not open"
    fi
done

echo "*******************************"

# Verify DNS SRV and A records exist for the worker respective of the iSCSI portals

host=$(kubectl get vs -n sysmgmt-health cray-sysmgmt-health-grafana -o jsonpath='{.spec.hosts[0]}' | sed -e 's/grafana\.[^.]*\.//')

dig -t SRV +short _sbps-hsn._tcp."${host}" _sbps-nmn._tcp."${host}" >> tmp_file

if [ -s tmp_file ];then
    echo "DNS SRV records exist as below:"
    echo "---------------------------"
    cat tmp_file
    echo "*******************************"
else
    echo "DNS SRV records do not exist, please create them"
    exit 1
fi

SRV=($(cat tmp_file | awk '{print $(NF)}' | sed -e 's/\.$//'))

echo "DNS A records are as below"
echo "--------------------------"

for i in "${SRV[@]}"
do
    dig -t A +short "${i}"
done

rm tmp_file

# Mapping between DNS A records and host iscsi portals
echo "                                       "
echo "*********************************************"
echo "Mapping between DNS A records and host iscsi portals"
echo "*********************************************"

for s in $(dig -t srv +short _sbps-hsn._tcp."${host}" | sort -k3 | awk '{print $NF;}' | xargs); do printf '** %s **\n' "$s"; dig +short "$s"; done

for s in $(dig -t srv +short _sbps-nmn._tcp."${host}" | sort -k3 | awk '{print $NF;}' | xargs); do printf '** %s **\n' "$s"; dig +short "$s"; done
