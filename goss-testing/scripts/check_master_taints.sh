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
#
# This test checks that master nodes have the correct taint

this_node_name=$1
if [[ -z $this_node_name ]]; then
  echo "ERROR node name was not supplied as an argument. Exiting."
  exit 1
fi

# the following taint is expected in CSM 1.6+ which has K8s 1.24+
taint="node-role.kubernetes.io/control-plane:NoSchedule"

k8s_version=$(kubectl version --short -o json | jq -r '.serverVersion')
major=$(echo $k8s_version | jq -r '.major')
minor=$(echo $k8s_version | jq -r '.minor')
if [[ $major -ne 1 ]]; then
  echo "FAIL: K8s major version: $major is unexpected"
  exit 1
fi
if [[ $minor -lt 24 ]]; then
  # master node taint should be node-role.kubernetes.io/master:NoSchedule if on K8s version before 1.24
  taint="node-role.kubernetes.io/master:NoSchedule"
fi

kubectl get node $this_node_name  -o jsonpath='{range .spec.taints[*]}{.key}:{.effect}{"\n"}{end}' | grep "$taint"
exit $?
