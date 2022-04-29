#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
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
# Goss server start up commands to serve health check endpoints

export GOSS_BASE=/opt/cray/tests/install/ncn
export GOSS_LOG_BASE_DIR=/opt/cray/tests/install/logs

# necessary for kubectl commands to run
export KUBECONFIG=/etc/kubernetes/admin.conf

# variables for ncn tests
vars_file="/opt/cray/tests/install/ncn/vars/variables-ncn.yaml"

# temporary variable file location
tmpvars=/tmp/goss-variables-$(date +%s)-temp.yaml
cat $vars_file > $tmpvars
echo "" >> $tmpvars

echo "Using Goss vars: $tmpvars"

source "$GOSS_BASE/automated/run-ncn-tests.sh"
# Add local nodename as variable
add_host_var "$tmpvars"

nodes=""
# add node names from basecamp or bss metadata to temp variables file
while [[ `echo $nodes | wc -w` -eq 0 || "$nodes" == "null" ]]; do
  # try getting node list from basecamp metadata endpoint first
  nodes=$(curl -s http://ncn-m001:8888/meta-data | jq -r .Global.host_records[].aliases[1] | grep -ohE "ncn-[m,w,s]([0-9]{3})" | awk '!a[$0]++')

  if [[ `echo $nodes | wc -w` -eq 0 || "$nodes" == "null" ]]; then
    echo "Node names not found in Basecamp. Trying to query BSS metadata instead."
    nodes=$(curl -s http://api-gw-service-nmn.local:8888/meta-data | jq -r .Global.host_records[].aliases[1] | grep -ohE "ncn-[m,w,s]([0-9]{3})" | awk '!a[$0]++')
  fi

  if [[ `echo $nodes | wc -w` -ne 0 && "$nodes" != "null" ]]; then
    # add list of all nodes
    echo "Found nodes $nodes"
    echo "nodes:" >> $tmpvars
    for node in $nodes; do
      echo "  - $node" >> $tmpvars
    done
    echo "" >> $tmpvars

    # add lists of k8s and storage nodes
    k8s_nodes=$(echo $nodes | grep -ohE "ncn-[m,w]([0-9]{3})")
    echo "k8s_nodes:" >> $tmpvars
    for node in $k8s_nodes; do
      echo "  - $node" >> $tmpvars
    done
    echo "" >> $tmpvars

    storage_nodes=$(echo $nodes | grep -ohE "ncn-[s]([0-9]{3})")
    echo "storage_nodes:" >> $tmpvars
    for node in $storage_nodes; do
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
# designated goss-servers port range: 8994-9008

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

echo "starting ncn-spire-healthchecks in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-spire-healthchecks.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-spire-healthchecks \
  --listen-addr $ip:9003 &

echo "starting ncn-afterpitreboot-healthcheck-master in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-master.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-master \
  --listen-addr $ip:9004 &

echo "starting ncn-afterpitreboot-healthcheck-worker in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-worker.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-worker \
  --listen-addr $ip:9005 &

echo "starting ncn-afterpitreboot-healthcheck-storage in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-storage.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-storage \
  --listen-addr $ip:9006 &

echo "starting ncn-afterpitreboot-kubernetes-tests-master in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-kubernetes-tests-master.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-kubernetes-tests-master \
  --listen-addr $ip:9007 &

echo "starting ncn-afterpitreboot-kubernetes-tests-worker in background"
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-kubernetes-tests-worker.yaml --vars $tmpvars serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-kubernetes-tests-worker \
  --listen-addr $ip:9008 &

echo "Goss servers started in background"

# Keep process running so systemd can kill and monitor background jobs as needed
sleep infinity
