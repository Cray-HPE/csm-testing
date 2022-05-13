#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
preflight_image="${1:-"dtr.dev.cray.com/cray/cray-preflight:latest"}"
NAMESPACE="${2:-"preflight"}"

echo "Running Stage 4 Preflight Checks"

# Wait up to 5 minutes for all k8s nodes to be in a ready state
function check_nodes_ready() {
    ready="false"

    for i in {1..60}; do
        nodes=$(kubectl get nodes -o wide|grep NotReady)

        if [ -z "$nodes" ]; then
              echo "Kubernetes nodes are ready"
              ready="true"
              break
        else
              echo "Waiting for kubernetes nodes to become ready ($i)..."
              sleep 5
        fi
    done

    if [ "$ready" != "true" ]; then
        echo "Kubernetes nodes did not become ready in time"
        kubectl get nodes -o wide
        exit 1
    fi

}

# Check to make sure the kube-system pods are healthy
# Make sure that over the course of 3 minutes, the k8s pods emain in a running state.
# NOTE: This does have the possibility of having false failures, we may need
# to scale this back eventually. But right not it causes enough issues during
# the installs to fail.
#shellcheck disable=SC2120
function check_kube_process_ok(){
    sleep_time=${1:-180}
    initial_sum=$(kubectl get pods -n kube-system --no-headers| awk '{sum += $4} END {print sum}')
    echo "Waiting for $sleep_time seconds to see if pods are restarting."
    sleep $sleep_time
    sum=$(kubectl get pods -n kube-system --no-headers| awk '{sum += $4} END {print sum}')
    if [ $initial_sum -ne $sum ]; then
          echo "Some kube-system pods are restarting!"
          kubectl get pod -n kube-system -o wide
          exit 1
    fi
    # Sanity check in case the above happened between a CBL retry
    not_running=$(kubectl get pods -n kube-system --no-headers|grep -v Running )
    if [ ! -z "$not_running" ]; then
          echo "Some kube-system pods are not running!"
          kubectl get pods -n kube-system -o wide
          exit 1
    fi
    echo "Kube-system pods seem healthy."
}

# Verify we have a default storage class
function verify_default_sc_set() {
    sc=$(kubectl get sc |grep "(default)")
    if [ -z "$sc" ]; then
          echo "No default storage class set!"
          kubectl get sc
          exit 1
    fi
    echo "Default storage class exists: $(echo $sc|awk '{print $1}')"
}

# Create the preflight namespace, delete and recreate if needed.
function create_ns(){
    ns=$(kubectl get ns|grep $NAMESPACE)
    if [ ! -z "$ns" ]; then
        echo "$NAMESPACE exists, recreating it."
        kubectl delete ns $NAMESPACE
        for i in {1..60}; do
            ns=$(kubectl get ns|grep $NAMESPACE)
            if [ -z "$ns" ]; then
                echo "Namespace deleted"
                break
            fi
            sleep 5
        done
    fi

    if [ ! -z "$ns" ]; then
        echo "Namespace not deleted within timeout!"
        exit 1
    fi

    kubectl create ns $NAMESPACE
}

# This test is meant to do a few things
# 1) We can pull images from the local registry (bis.local, etc)
# 2) We can get a container running with a cluster ip (k8s networking is working)
# 3) We can make curl calls to the cluster ip (networking is working)
# 4) Create a PV from the default storage class (make sure ceph is working)
# We're using a statefulset here purely to make the PV/PVC creation easier
function run_preflight_pod_checks() {
    echo $preflight_image
    create_ns
    cat <<EOF | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: Service
metadata:
  name: preflight
  labels:
    app: preflight
spec:
  ports:
  - name: http
    port: 80
    targetPort: 80
  selector:
    app: preflight
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: preflight
spec:
  serviceName: "preflight"
  replicas: 1
  selector:
    matchLabels:
      app: preflight
  template:
    metadata:
      labels:
        app: preflight
    spec:
      containers:
      - name: preflight
        image: $preflight_image
        imagePullPolicy: Always
        ports:
        - containerPort: 80
          name: http
        volumeMounts:
        - name: preflight
          mountPath: /preflight
  volumeClaimTemplates:
  - metadata:
      name: preflight
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 1Gi
---
EOF

    ok="false"
    # Wait up to 5 minutes for pod to come up
    for i in {1..60}; do
        pods=$(kubectl get po -n $NAMESPACE|grep Running)
        if [ ! -z "$pods" ]; then
              echo "Preflight pod ready"
              break
        fi
        sleep 5
    done

    ip=$(kubectl get svc -n $NAMESPACE preflight -o jsonpath="{.spec.clusterIP}")

    # Try up to 10 times to curl the service
    for i in {1..10}; do
        resp=$(curl http://$ip/status/200 -i -s| grep 200)
        if [ ! -z "$resp" ]; then
            echo "Preflight pod working successfully!"
            ok="true"
            break
        fi
        sleep 2
    done

    if [ "$ok" != "true" ]; then
        echo "Preflight check failed."
        echo "This would indicate something with kubernetes is unstable, or something it uses (ceph, CNI, DNS, etc)"
        kubectl describe pod -n $NAMESPACE -l app=preflight
        # NOTE: We don't delete the deployment here so we can investigate errors
        # The create_ns function will delete and recreate it next run.
        exit 1
    fi

    echo "Cleaning up preflight deployments"
    kubectl delete ns $NAMESPACE
}


echo "#########################################################"
echo "Making sure kubernetes nodes are ready"
echo "#########################################################"
check_nodes_ready
echo "#########################################################"
echo "Making sure kube-system pods seem healthy"
echo "#########################################################"
check_kube_process_ok
echo "#########################################################"
echo "Verify default storage class set"
echo "#########################################################"
verify_default_sc_set
echo "#########################################################"
echo "Running preflight container and validation tests"
echo "#########################################################"
run_preflight_pod_checks
echo "#########################################################"
echo "Success!"
echo "#########################################################"
