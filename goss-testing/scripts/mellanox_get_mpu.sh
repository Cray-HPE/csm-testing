#! /bin/bash

COOKIE=/tmp/cookiejar
CMD_OUT=/tmp/mellanox_script_out.txt
IP=$1
PASSWORD=$2

curl -k -L -X POST -d '{"username":"admin","password":"$PASSWORD"}' -c $COOKIE "https://$IP/admin/launch?script=rh&template=json-request&action=json-login"
curl -k -L -X POST -d '{"cmd":"show interface status"}' -b $COOKIE "https://$IP/admin/launch?script=json" | jq .'data' | grep -A7 \"Mpo | grep 'MTU.*9216' || echo FAIL
