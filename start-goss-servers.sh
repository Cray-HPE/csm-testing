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

vars="/opt/cray/tests/install/ncn/vars/variables-ncn.yaml"
export GOSS_BASE=/opt/cray/tests/install/ncn

# start server with NCN test suites (as of now, goss server only runs on NCNs)
# designated goss-servers port range: 8994-8999
nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-run-time-tests.yaml --vars $vars \
serve --format json --endpoint /ncn-run-time-tests --max-concurrent 4 --listen-addr :8994 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-preflight-tests.yaml --vars $vars \
serve --format json --endpoint /ncn-preflight-tests --max-concurrent 4 --listen-addr :8995 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-master.yaml --vars $vars \
serve --format json --endpoint /ncn-kubernetes-tests-master --max-concurrent 4 --listen-addr :8996 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-storage-tests.yaml --vars $vars \
serve --format json --endpoint /ncn-storage-tests --max-concurrent 4 --listen-addr :8997 &

nohup /usr/bin/goss -g /opt/cray/tests/install/ncn/suites/ncn-kubernetes-tests-worker.yaml --vars $vars \
serve --format json --endpoint /ncn-kubernetes-tests-worker --max-concurrent 4 --listen-addr :8998 &

exit