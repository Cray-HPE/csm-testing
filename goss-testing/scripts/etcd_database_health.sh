#!/usr/bin/env bash

for pod in $(kubectl get pods -l app=etcd -n services -o jsonpath='{.items[*].metadata.name}')
do
    dbc=$(kubectl -n services exec ${pod} -- /bin/sh \
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