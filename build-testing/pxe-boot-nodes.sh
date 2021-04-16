#!/usr/bin/env bash
# Attempts to boot NCNs from the LiveCD for testing purposes based on type (storage, master or worker)
#
# (C) Copyright 2021 Hewlett Packard Enterprise Development LP.
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

# usage: pxe-boot-nodes.sh [s, m or w] [IPMI password]

# arguments
type=$1 # options: s, m or w
export IPMI_PASSWORD=$2

export NODE_COUNT=$(grep -ohE "ncn-$type([0-3]{3})" /etc/dnsmasq.d/statics.conf | awk '!a[$0]++' | wc -l)
export NODE_NUM=1
export IPMI_USERNAME=root
export MAX_START_RETRIES=5
export MAX_SSH_RETRIES=100
export MAX_BOOT_RETRIES=2
export CONMAN_LOGS=/var/log/conman

function pxe_boot_check {
  # checks the conman node console log to verify the node pxe booted
  node=$1
  grep " kernel : " $CONMAN_LOGS/console.$node-mgmt > /dev/null 2>&1
  if [[ $? -eq 0 ]]; then
    return 0
  fi
}

function conman_log_prep {
  # renames the node's log file for conman so it can be replaced by a new log file
  node=$1
  mv $CONMAN_LOGS/console.$node-mgmt $CONMAN_LOGS/console.$node-mgmt.$(date +%s)
  /usr/bin/systemctl restart conman
}

function restart_node {
  # attempts to network boot the node
  node=$1

  power_status=$(ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power status)
  echo "Current chassis power status: $power_status"

  if echo $power_status | grep on; then
    # node is powered on, so power it off
    echo "Attempting to power off node..."
    ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power off

    if [[ $? -ne 0 ]]; then
      echo "Could not power off node."
      return 2
    fi
  fi

  echo "Setting node to PXE boot from network..."
  ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt chassis bootdev pxe options=efiboot,persistent

  if [[ $? -ne 0 ]]; then
    echo "Could not set node to network boot."
    return 2
  fi

  echo "Waiting to power on node..."
  sleep 8

  echo "Attempting to power on node '$node'"
  ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power on

  if [[ $? -ne 0 ]]; then
    echo "Could not power on node. Retrying $MAX_START_RETRIES more times."
    return 2
  fi

  sleep 5
  echo "Power status: $(ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power status)"
  return 0
}

function retry_ssh {
  # attempts ssh connection until the node can be reached or the max retries are exhausted
  node=$1
  ssh_retries=$MAX_SSH_RETRIES
  boot_retries=$MAX_BOOT_RETRIES

  while [[ $ssh_retries -ne 0 ]]; do
    nmap $node -PN -p ssh | grep open > /dev/null 2>&1

    if [[ $? -eq 0 ]]; then
      return 0
    else
      echo -en "\rAttempting SSH connection on port 22 ($ssh_retries attempts remaining)"
    fi

    sleep 5
    ((ssh_retries = $ssh_retries - 1))
  done

  if [[ $rc -ne 0 ]] ; then
    if [[ $boot_retries -gt 0 ]]; then
      echo
      echo "Could not SSH to node '$node' after $MAX_SSH_RETRIES attempts. Rebooting node."
      node_boot_attempt $node 1 $boot_retries
      ((boot_retries = $boot_retries - 1))
    else
      echo "Could not boot node. Giving up."
      return 1
    fi
  fi
}

function node_boot_attempt {
  # main orchestration function
  node=$1
  start_retries=$MAX_START_RETRIES

  # keep trying to restart the node for specified number of retries
  while [[ $start_retries -ne 0 ]]; do
    ((start_retries = $start_retries - 1))
    echo
    echo "Restarting Node: $node"
    echo "-------------------------"

    restart_node $node

    if [[ $? -eq 0 ]]; then
      # node started
      conman_log_prep $node
      break
    else
      if [[ $start_retries -eq 0 ]]; then
        echo
        echo "Failed to start node! Exiting."
        exit 1
      fi
    fi

    sleep 5
  done

  # try sshing to the node since it started
  sleep 30

  echo
  echo "Testing Connection: $node"
  echo "----------------------------"

  retry_ssh $node

  if [[ $? -eq 0 ]]; then
    echo
    echo "Connection succeeded."

    pxe_boot_check $node

    if [[ $? -eq 0 ]]; then
      echo "Network boot confirmed. Boot was successful."
    else
      echo "Node did not PXE boot. Restarting node."
      node_boot_attempt $node
    fi
  fi

  if [[ $NODE_COUNT -eq $NODE_NUM ]]; then
    # we've hit every node, so exit
    exit 0
  fi

  ((NODE_NUM = $NODE_NUM + 1))
}

if [[ -z $1 ]]; then
  echo "Must specify a node type prefix (either m, w or s)."
  exit 0
fi

if [[ -z $2 ]]; then
  echo "Must provide the IPMI password."
  exit 0
fi

nodes=$(grep -ohE "ncn-$type([0-3]{3})" /etc/dnsmasq.d/statics.conf | grep -v m001 | awk '!a[$0]++')

for node in $nodes; do
  node_boot_attempt $node
done

exit