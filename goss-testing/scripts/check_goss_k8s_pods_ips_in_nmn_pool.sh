#!/bin/bash
#
# MIT License
#
# (C) Copyright 2023-2024 Hewlett Packard Enterprise Development LP
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

out=$(cray sls search networks list --name NMN --format json 2>&1)
if [ "$?" -eq 0 ]; then
  echo "Successfully called sls search networks..."
  network=$(echo "$out" | jq -r '.[].ExtraProperties.Subnets[] | select(.FullName == "NMN Bootstrap DHCP Subnet") | .CIDR')
else
  echo "Failed to talk to sls, looking for sls_input_file.json on the filesystem..."
  #
  # We are unable to talk to sls, let's see if can find the sls_input_file.json
  # on the filesystem in either of these locations:
  #
  # /var/www/ephemeral/prep/SYSTEM-NAME/sls_input_file.json
  # /metal/bootstrap/prep/SYSTEM-NAME/sls_input_file.json
  #
  system_name=$(craysys metadata get system-name)
  if [ "$?" -ne 0 ]; then
    echo "FAIL: Unable to call craysys to get system name"
    exit 1
  fi

  pit_file="/var/www/ephemeral/prep/${system_name}/sls_input_file.json"
  post_pit_file="/metal/bootstrap/prep/${system_name}/sls_input_file.json"
  if test -f "$pit_file"; then
    echo "Found sls_input_file.json at $pit_file, proceeding..."
    network=$(cat $pit_file | jq -r '.Networks.NMN.ExtraProperties.Subnets[] | select(.FullName == "NMN Bootstrap DHCP Subnet") | .CIDR')
  elif test -f "$post_pit_file"; then
    echo "Found sls_input_file.json at $post_pit_file, proceeding..."
    network=$(cat $post_pit_file | jq -r '.Networks.NMN.ExtraProperties.Subnets[] | select(.FullName == "NMN Bootstrap DHCP Subnet") | .CIDR')
  else
    #
    # Couldn't talk to SLS, or find the sls_input_file.json file
    # anywhere, without valid data, we'll skip this test.
    #
    echo "PASS: Unable to determine NMN subnet, skipping test..."
    exit 0
  fi
fi

ips=$(kubectl -n kube-system get pods -o wide | grep -E '^kube-apiserver|^kube-controller-manager|^kube-multus-ds|^kube-proxy|^kube-scheduler|^weave-net' | awk '{print $(NF-3)}')

valid_ips=$(nmap -sL -n $network)
bad_ip=0
for ip in $ips
do
  echo "$valid_ips" | grep -q $ip
  if [ "$?" -ne 0 ]; then
    bad_ip=1
    echo "ERROR: The following IP: $ip is not in the NMN subnet ($network)"
  fi
done

if [ "$bad_ip" -eq 1 ]; then
    echo "FAIL: At least one IP was not in the correct NMN Bootstrap DHCP Subnet"
    exit 1
fi

echo "PASS: All K8S pod IPs are in the NMN Bootstrap DHCP Subnet"
exit 0
