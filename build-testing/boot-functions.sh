# This file is sourced by the NCN network booting scripts.
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
    echo "Powering off node..."
    ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power off

    if [[ $? -ne 0 ]]; then
      echo "Could not power off node."
      return 2
    fi
  fi

  # set network boot option
  ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt chassis bootdev pxe options=efiboot,persistent

  if [[ $? -ne 0 ]]; then
    echo "Could not set node to network boot."
    return 2
  fi

  # wait to power on node
  sleep 8

  # power on node
  ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power on

  if [[ $? -ne 0 ]]; then
    return 1
  fi

  sleep 5
  echo "Power status: $(ipmitool -I lanplus -U $IPMI_USERNAME -E -H $node-mgmt power status)"
  return 0
}

function retry_ssh {
  # attempts ssh connection until connection is successful or the max retries are reached
  node=$1
  ssh_retries=$MAX_SSH_ATTEMPTS

  echo "Attempting SSH connection to node..."

  until nmap $node -PN -p ssh | grep open; do
    if [[ $ssh_retries -eq 0 ]]; then
      return 1
    fi

    ((ssh_retries = $ssh_retries - 1))
    sleep 3
  done

  return 0
}

function node_boot_attempt {
  # main orchestration function
  node=$1
  retries_left=$2
  ((retries_left = $retries_left - 1))

  echo "Attempting to network boot node '$node' with $retries_left retries remaining..."
  echo
  echo "Restarting Node: $node"

  restart_node $node

  if [[ $? -eq 0 ]]; then
    # node started
    conman_log_prep $node
  else
    if [[ $retries_left -gt 0 ]]; then
      echo
      echo "Node startup attempt failed. Retrying $retries_left more times."
      echo
      node_boot_attempt $node $retries_left
    else
      echo
      echo "Could not successfully boot node after $MAX_BOOT_RETRIES attempts. Exiting."
      exit 1
    fi
  fi

  sleep 5

  # try sshing to the node since it started
  sleep 30

  retry_ssh $node

  if [[ $? -eq 0 ]]; then
    echo
    echo "Connection succeeded."

    pxe_boot_check $node

    if [[ $? -eq 0 ]]; then
      echo "Network boot confirmed. Boot was successful."
    else
      if [[ $retries_left -gt 0 ]]; then
        echo "Node did not PXE boot. Restarting node."
        echo
        node_boot_attempt $node $retries_left
      fi
    fi
  else
    if [[ $retries_left -gt 0 ]]; then
      echo
      echo "Could not SSH to '$node'. Rebooting node."
      echo
      node_boot_attempt $node $retries_left
    else
      echo
      echo "Could not successfully boot node after $MAX_BOOT_RETRIES attempts. Exiting."
      exit 1
    fi
  fi

  if [[ $NODE_COUNT -eq $NODE_NUM ]]; then
    # we've hit every node, so exit
    exit 0
  fi

  ((NODE_NUM = $NODE_NUM + 1))
}