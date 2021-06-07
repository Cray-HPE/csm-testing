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

# necessary for kubectl commands to run
export KUBECONFIG=/etc/kubernetes/admin.conf

# variables for ncn tests
vars_file="/opt/cray/tests/install/ncn/vars/variables-ncn.yaml"

# temporary variable file location
tmpvars=/tmp/goss-variables-$(date +%s)-temp.yaml
cat $vars_file > $tmpvars
echo "" >> $tmpvars

echo "Using goss vars: $tmpvars"

nodes=""
# add node names from basecamp metadata to temp variables file
while [[ `echo $nodes | wc -w` -eq 0 || "$nodes" == "null" ]]; do
  # get node list from basecamp metadata endpoint
  nodes=$(curl -s http://ncn-m001:8888/meta-data | jq -r .Global.host_records[].aliases[1] | grep -ohE "ncn-[m,w,s]([0-9]{3})" | awk '!a[$0]++')

  if [[ `echo $nodes | wc -w` -ne 0 && "$nodes" != "null" ]]; then
    # add list of all nodes
    echo "Found nodes $nodes"
    echo "nodes:" >> $tmpvars
    for node in $nodes; do
      echo "  - $node" >> $tmpvars
    done
    echo "" >> $tmpvars

    # add lists of k8s and storage nodes
    k8s_nodes=$(curl -s http://ncn-m001:8888/meta-data | jq -r .Global.host_records[].aliases[1] | grep -ohE "ncn-[m,w]([0-9]{3})" | awk '!a[$0]++')
    echo "k8s_nodes:" >> $tmpvars
    for node in $k8s_nodes; do
      echo "  - $node" >> $tmpvars
    done
    echo "" >> $tmpvars

    storage_nodes=$(curl -s http://ncn-m001:8888/meta-data | jq -r .Global.host_records[].aliases[1] | grep -ohE "ncn-[s]([0-9]{3})" | awk '!a[$0]++')
    echo "storage_nodes:" >> $tmpvars
    for node in $k8s_nodes; do
      echo "  - $node" >> $tmpvars
    done
  else
    echo "Node names could not be found in Basecamp. Waiting for 30s"
    sleep 30
  fi
done

# for security reasons we only want to run the servers on the HMN network, which is not connected to open Internet
ip=$(host $(hostname).hmn | grep -Po '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
[[ -z $ip ]] && exit 2

# start servers with NCN test suites
# designated goss-servers port range: 8994-9002

echo "starting ncn-preflight-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-preflight-tests.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-preflight-tests \
  --listen-addr $ip:8995 &

echo "starting ncn-kubernetes-tests-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-master.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-master \
  --listen-addr $ip:8996 &

echo "starting ncn-kubernetes-tests-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-worker.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-worker \
  --listen-addr $ip:8998 &

echo "starting ncn-storage-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-storage-tests.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-storage-tests \
  --listen-addr $ip:8997 &

echo "starting ncn-healthcheck-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-master.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-master \
  --listen-addr $ip:8994 &

echo "starting ncn-healthcheck-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-worker.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-worker \
  --listen-addr $ip:9000 &

echo "starting ncn-healthcheck-storage in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-storage.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-storage \
  --listen-addr $ip:9001 &

echo "starting ncn-smoke-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-smoke-tests.yaml --vars $tmpvars serve \
  --format json \
  --endpoint /ncn-smoke-tests \
  --max-concurrent 4 \
  --listen-addr $ip:9002 &

echo "Goss servers started in background"

# Keep process running so systemd can kill and monitor background jobs as needed
sleep infinity
