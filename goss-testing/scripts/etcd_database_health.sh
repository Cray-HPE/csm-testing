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
for pod in $(kubectl get pods -l app=etcd -n services -o jsonpath='{.items[*].metadata.name}')
do
    dbc=$(kubectl -n services exec ${pod} -c etcd -- /bin/sh \
                  -c "ETCDCTL_API=3 etcdctl put foo fooCheck && \
                  ETCDCTL_API=3 etcdctl get foo && \
                  ETCDCTL_API=3 etcdctl del foo && \
                  ETCDCTL_API=3 etcdctl get foo" 2>&1)
    echo $dbc | awk '{ if ( $1=="OK" && $2=="foo" && \
                       $3=="fooCheck" && $4=="1" && $5=="" ) print \
    "PASS:  " PRINT $0;
    else \
    print "FAIL: " PRINT $0 }'
done

exit
