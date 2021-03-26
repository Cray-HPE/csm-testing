#!/usr/bin/env bash
# Goss server start up commands to serve health check endpoints
#
# (C) Copyright 2020 Hewlett Packard Enterprise Development LP.
# Author: Forrest Jadick
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

export GOSS_BASE=/opt/cray/tests/install/ncn
vars_file="/opt/cray/tests/install/ncn/vars/variables-ncn.yaml"

nodes=$(cat /etc/hosts | grep -ohE 'ncn-[m,w,s]([0-9]{3})' | awk '!a[$0]++')
tmpvars=/tmp/goss-variables-$(date +%s)-temp.yaml
interface=vlan004

# add node names from /etc/hosts to temp variables file
if [ `echo $nodes | wc -w` -ne 0 ];then
  echo "nodes:" >> $tmpvars
  for node in $nodes; do
    echo "  - $node" >> $tmpvars
    echo "" >> $tmpvars
  done
else
  echo "Node names could not be found in /etc/hosts file! Exiting now."
  exit 1
fi
cat $vars_file >> $tmpvars

# for security reasons we only want to run the servers on the HMN network, which is not connected to open Internet
ip=$(ip -f inet addr show $interface | grep -Po 'inet \K[\d.]+')
[[ -z $ip ]] && exit 2

# start server with NCN test suites (as of now, Goss servers only run on NCNs)
# designated goss-servers port range: 8994-9001

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-preflight-tests.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-preflight-tests \
  --listen-addr $ip:8995 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-master.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-master \
  --listen-addr $ip:8996 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-worker.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-worker \
  --listen-addr $ip:8998 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-storage-tests.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-storage-tests \
  --listen-addr $ip:8997 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-master.yaml --vars $tmpvars serve \
  --format json \
  --endpoint /ncn-healthcheck-master \
  --max-concurrent 4 \
  --listen-addr $ip:8994 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-worker.yaml --vars $tmpvars serve \
  --format json \
  --endpoint /ncn-healthcheck-worker \
  --max-concurrent 4 \
  --listen-addr $ip:9000 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-storage.yaml --vars $tmpvars serve \
  --format json \
  --endpoint /ncn-healthcheck-storage \
  --max-concurrent 4 \
  --listen-addr $ip:9001 &

exit