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

# Default value for tmpvars file
tmpvars="${GOSS_BASE}/vars/variables-ncn.yaml"

# During the NCN image build, this service is started, even though the csm-testing RPM is not installed. In that
# situation, the run-ncn-tests.sh file will not be present on the system, but we do not want the service to exit in
# error (because this causes the NCN image build to think there is a real problem with the service). On live systems,
# there is likewise a chance that this service is started just before the csm-testing RPM has been installed. In both
# cases, the solution if the run-ncn-tests.sh file does not exist (or exists but is empty, for some weird reason)
# is to sleep for a bit and check again.
while [[ ! -s "${GOSS_BASE}/automated/run-ncn-tests.sh" ]]; do
    sleep 5
done

source "${GOSS_BASE}/automated/run-ncn-tests.sh"

while true ; do
    # The create_tmpvars_file function is defined in run-ncn-tests.sh
    # It creates the temporary variables file and saves the path to it in the $tmpvars variable
    create_tmpvars_file
    rc=$?
    
    if [[ ${rc} -eq 127 ]]; then
        # In this specific case we want the error to be fatal, because that means that the create_tmpvars_file function is not defined, and
        # no amount of retrying will alter that.
        echo "ERROR: create_tmpvars_file function does not appear to be defined" 1>&2
        exit 2
    fi

    # Otherwise, if the function passed and generated a non-empty variable file, then proceed
    [[ ${rc} -eq 0 && -n ${tmpvars} && -s ${tmpvars} ]] && break

    # create_tmpvars_file failed for some reason, so sleep and retry
    sleep 5
done

# for security reasons we only want to run the servers on the HMN network, which is not connected to open Internet
ip=$(host "$(hostname).hmn" | grep -Po '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
[[ -z ${ip} ]] && exit 2

# start servers with NCN test suites
# designated goss-servers port range: 8994-9008

echo "starting ncn-preflight-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-preflight-tests.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-preflight-tests \
  --listen-addr "${ip}":8995 &

echo "starting ncn-kubernetes-tests-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-master.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-master \
  --listen-addr "${ip}":8996 &

echo "starting ncn-kubernetes-tests-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-worker.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-kubernetes-tests-worker \
  --listen-addr "${ip}":8998 &

echo "starting ncn-storage-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-storage-tests.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-storage-tests \
  --listen-addr "${ip}":8997 &

echo "starting ncn-healthcheck-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-master.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-master \
  --listen-addr "${ip}":8994 &

echo "starting ncn-healthcheck-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-worker.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-worker \
  --listen-addr "${ip}":9000 &

echo "starting ncn-healthcheck-storage in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-healthcheck-storage.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-healthcheck-storage \
  --listen-addr "${ip}":9001 &

echo "starting ncn-smoke-tests in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-smoke-tests.yaml --vars "${tmpvars}" serve \
  --format json \
  --endpoint /ncn-smoke-tests \
  --max-concurrent 4 \
  --listen-addr "${ip}":9002 &

echo "starting ncn-spire-healthchecks in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-spire-healthchecks.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-spire-healthchecks \
  --listen-addr "${ip}":9003 &

echo "starting ncn-afterpitreboot-healthcheck-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-master.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-master \
  --listen-addr "${ip}":9004 &

echo "starting ncn-afterpitreboot-healthcheck-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-worker.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-worker \
  --listen-addr "${ip}":9005 &

echo "starting ncn-afterpitreboot-healthcheck-storage in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-healthcheck-storage.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-healthcheck-storage \
  --listen-addr "${ip}":9006 &

echo "starting ncn-afterpitreboot-kubernetes-tests-master in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-kubernetes-tests-master.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-kubernetes-tests-master \
  --listen-addr "${ip}":9007 &

echo "starting ncn-afterpitreboot-kubernetes-tests-worker in background"
/usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-afterpitreboot-kubernetes-tests-worker.yaml --vars "${tmpvars}" serve \
  --format json \
  --max-concurrent 4 \
  --endpoint /ncn-afterpitreboot-kubernetes-tests-worker \
  --listen-addr "${ip}":9008 &

echo "Goss servers started in background"

# Keep process running so systemd can kill and monitor background jobs as needed
sleep infinity
