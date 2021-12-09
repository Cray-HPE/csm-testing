#!/bin/bash

# Copyright 2020-2021 Hewlett Packard Enterprise Development LP

function get_client_secret() {
    # Kubernetes is not installed on all storage nodes. If executing on a storage
    # node, verify a functional master or worker node. Obtain client secret
    # from identified NCN Kubernetes node.
    
    activeKubNcnNode=""
    hostNodeType=""
    clientSecret=""
    listOfKubNcns=""
    sshOptions="-q -o StrictHostKeyChecking=no"
    
    # If executing on a storage node, determine an active NCN Kubernetes node:
    hostNodeType=$(echo $(hostname) | awk '/s/ {print "storage"}')
    if [[ $hostNodeType == "storage" ]]
    then
        # Determine active non-storage NCN node:
        listOfKubNcns=$(cat /etc/hosts | grep -ohE "ncn-[m,w]([0-9]{3})" | awk '!a[$0]++' | sort)
        for node_i in $listOfKubNcns;
        do
            ssh $sshOptions $node_i 'kubectl get nodes' >/dev/null
            if [[ $? -eq 0 ]]
            then
                activeKubNcnNode=$node_i
                break
            fi
        done
    fi

    # Get client secret:
    if [[ -z $activeKubNcnNode ]]
    then
        clientSecret=$(kubectl get secrets admin-client-auth \
                               -o jsonpath='{.data.client-secret}' | base64 -d)
    else
        clientSecret=$(ssh $sshOptions $activeKubNcnNode \
                           'kubectl get secrets admin-client-auth \
                           -o jsonpath='{.data.client-secret}' | base64 -d')
    fi
    echo $clientSecret
}

function get_token() {
  cnt=0
  TOKEN=""
  endpoint="https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token"
  client_secret=$(get_client_secret)
  while [ "$TOKEN" == "" ]; do
    cnt=$((cnt+1))
    TOKEN=$(curl -k -s -S -d grant_type=client_credentials -d client_id=admin-client -d client_secret=$client_secret $endpoint)
    if [[ "$TOKEN" == *"error"* ]]; then
      TOKEN=""
      if [ "$cnt" -eq 5 ]; then
        break
      fi
      sleep 5
    else
      TOKEN=$(echo $TOKEN | jq -r '.access_token')
      break
    fi
  done
  echo $TOKEN
}

no_wipe_status() {
    echo "Note that before the PIT node has been rebooted into ncn-m001,"
    echo "metal.no-wipe status may not available which will cause this test to fail."
    noWipeFail=0
    export TOKEN=$(get_token)
    if [[ -z $TOKEN ]]
    then
        echo "Failed to get token, skipping metal.no-wipe checks."
        noWipeFail=2
    fi

    xName=$(cat /etc/cray/xname)
    if [[ -z $xName ]]
    then
        echo "Failed to obtain xname, skipping metal.no-wipe checks."
        noWipeFail=2
    fi

    if [[ $noWipeFail -eq 0 ]]
    then
        noWipe=""
        iter=0
        # Because we're using bootparameters instead of bootscript, this loop is likely no longer
        # necessary. However, it also doesn't hurt to have it.
        while [[ -z $noWipe && $iter -lt 5 ]]; do
            noWipe=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" "https://api-gw-service-nmn.local/apis/bss/boot/v1/bootparameters?name=${xName}" | grep -o "metal.no-wipe=[01]")
            if [[ -z $noWipe ]]; then sleep 3; fi
            iter=$(($iter + 1))
        done
        if [[ -z $noWipe ]]
        then
            noWipe='unavailable'
            noWipeFail=1
        else
            noWipeVal=$(echo $noWipe | cut -d "=" -f2)
            if [[ $noWipeVal -ne 1 ]]; then noWipeFail=1; fi
        fi
        echo "$xName - $noWipe"
    fi

    if [[ $noWipeFail -eq 1 ]]
    then
        echo " --- FAILED --- metal.no-wipe status is not 1. (note: node_status = upgrade/rebuild, then metal.no-wipe=0 is valid)";
        failureMsg="FAIL: metal.no-wipe status is not 1 or unavailable. (note: node_status = upgrade/rebuild, then metal.no-wipe=0 is valid)."
        exit_code=1
    elif [[ $noWipeFail -eq 2 ]]
    then
        echo " --- FAILED --- Failed to get token or xname."
        failureMsg="FAIL: Failed to get token or xname, skipped metal.no-wipe check. Could not verify no-wipe status."
        exit_code=2
    else
        echo " --- PASSED ---"
        exit_code=0
    fi

    exit $exit_code
}

no_wipe_status
