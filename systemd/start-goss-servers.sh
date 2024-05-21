#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2020-2024 Hewlett Packard Enterprise Development LP
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
set -e

if [ -f /etc/pit-release ]; then
    export GOSS_BASE=/opt/cray/tests/install/livecd
else
    export GOSS_BASE=/opt/cray/tests/install/ncn
fi

# necessary for kubectl commands to run
export KUBECONFIG=/etc/kubernetes/admin.conf

# necessary for test that need to know the current hostname
HOSTNAME=$(hostname -s)
export HOSTNAME

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
    # This creates a temporary Goss variables file and saves the path to it in the $tmpvars variable
    tmpvars=$(create_goss_variable_file)
    rc=$?
    
    if [[ ${rc} -eq 127 ]]; then
        # In this specific case we want the error to be fatal, because that means that the create_goss_variable_file function is not defined, and
        # no amount of retrying will alter that.
        echo "ERROR: create_goss_variable_file function does not appear to be defined" 1>&2
        exit 2
    fi

    # Otherwise, if the function passed and generated a non-empty variable file (setting the tmpvar variable to its path), then proceed
    [[ ${rc} -eq 0 && -n ${tmpvars} && -s ${tmpvars} ]] && break

    # create_goss_variable_file failed for some reason, so sleep and retry
    sleep 5
done

if is_vshasta_node; then
    echo "vshasta detected."

    # Use junit for vshasta
    results_format=junit

    # On vshasta there is only one network and no hmn
    # However, host command may not work if dnsmasq is not yet configured - try to parse ip address output in this case
    ip=$(host "$(hostname)" | grep -Po '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' || \
        ip address show dev eth0 | awk '/ inet / {gsub("/.+", "", $2); print $2}')
else
    # for security reasons we only want to run the servers on the HMN network, which is not connected to open Internet
    ip=$(host "$(hostname).hmn" | grep -Po '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
    
    # Return results in JSON format outside of vshasta
    results_format=json
fi
[[ -z ${ip} ]] && exit 2

# The goss_suites_endpoints_ports function calls a Python script that outputs lines of the format:
# <suite file path> <endpoint name> <port>
# For all Goss endpoints that should be started on this node
goss_suites_endpoints_ports | while read suite endpoint port ; do
    [[ -n ${endpoint} ]] || continue
    if [[ ! -s ${suite} ]]; then
        echo "Skipping goss server entry because suite file is empty or does not exist. suite=${suite} endpoint=${endpoint} port=${port}" 1>&2
        continue
    fi

    # Start Goss server for this entry.
    echo "starting ${endpoint} in background on port ${port}"
    /usr/bin/goss -g "${suite}" --vars "${tmpvars}" serve \
        --format "${results_format}" \
        --max-concurrent 4 \
        --endpoint "/${endpoint}" \
        --listen-addr "${ip}:${port}" &
done
echo "Goss servers started in background"

# Keep process running so systemd can kill and monitor background jobs as needed
sleep infinity
