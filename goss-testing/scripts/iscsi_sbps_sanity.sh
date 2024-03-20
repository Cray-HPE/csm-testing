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

Found=0
LIO_ACT=0

echo "Checking whether the node is configured with iSCSI"

ISCSI=($(kubectl get nodes --selector='iscsi_sbps=true' -o jsonpath='{.items[*].metadata.name}'))

NODE="$HOSTNAME"

for i in "${ISCSI[@]}"
do
    if [ "${i}" == "${NODE}" ]
    then
        Found=1
        echo "$NODE is configured with iSCSI"
        break
    fi
done

if [ "${Found}" == 0 ]
then
    echo "iscsi is not configured, exiting"
    exit 1
fi

# Verifying whether Marshal agent is running or not

echo "*******************************"
sbps_marshal=$(systemctl is-active sbps-marshal.service)

if [ "${sbps_marshal}" == 'active' ]
then
    echo "Marshal agent is running"
else
    echo "Marshal agent is not running"
fi

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

PORTALS=($(ss -tnpl | grep 3260 | awk '{ print $4 }' ))

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
    if [[ $(nmap -sS -p 3260 "${IP}" | grep 3260 | grep open) ]]
    then
        echo "$IP is open"
    else
        echo "$IP is not open"
    fi
done

echo "*******************************"

# Verify DNS SRV and A records exist for the worker respective of the iSCSI portals

host=$(grep 127.0.0.1 /etc/hosts | head -n 1 | awk '{ print $2 }' | cut -f1 -d'-')

echo "Host = ${host}"

dig -t SRV +short _sbps-hsn._tcp."${host}".hpc.amslabs.hpecorp.net _sbps-nmn._tcp."${host}".hpc.amslabs.hpecorp.net >> tmp_file

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
