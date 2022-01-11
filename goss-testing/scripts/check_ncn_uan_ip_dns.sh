#!/usr/bin/env bash

# init variables
uan_list=""
ncn_list=""
ncn_uan_list=""
smd_ip_list=""
error_found=false

# get access token
TOKEN=$(curl -s -k -S -d grant_type=client_credentials \
        -d client_id=admin-client \
        -d client_secret=`kubectl get secrets admin-client-auth \
        -o jsonpath='{.data.client-secret}' | base64 -d` \
        https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token | jq -r '.access_token')

# query SLS for hardware inventory
sls_hardware=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" https://api-gw-service-nmn.local/apis/sls/v1/hardware)

# quey SMD for EthernetInterface data
smd_ethernet_interfaces=$(curl -s -k -H "Authorization: Bearer ${TOKEN}" \
                         https://api-gw-service-nmn.local/apis/smd/hsm/v2/Inventory/EthernetInterfaces)

# check to see if there are any duplicate IPs in SMD EthernetInterface data
for row in $(echo "${smd_ethernet_interfaces}" | jq -r '.[] | @base64'); do
    _jq() {
     echo ${row} | base64 --decode | jq -r ${1}
    }
    ips=$(_jq '.IPAddresses[]'|jq -r .IPAddress)
    component_id=$(_jq '.ComponentID')
    if [[ ! -z $ips ]] && [[ ! -z $component_id ]];then
        for ip in $ips; do
            read a b c d <<<"${ip//./ }"
            dupe_check=$(echo $smd_ip_list|grep "$a\.$b\.$c\.$d"|wc -l)
            if [ $dupe_check -gt 0 ]; then
                error_found=true
                echo "ERROR: $ip duplicate IP found in SMD"
                nslookup $ip
            else
                smd_ip_list+="${ip} "
            fi
        done

    fi
done

# get application node aliases
for row in $(echo "${sls_hardware}" | jq -r '.[] | @base64'); do
    _jq() {
     echo ${row} | base64 --decode | jq -r ${1}
    }
    role=$(_jq '.ExtraProperties.Role')
    if [[ "$role" == "Application" ]]; then
    	uan_alias=$(_jq '.ExtraProperties.Aliases[0]')
        uan_list+="${uan_alias}.nmn"$'\n'
        uan_list+="${uan_alias}.can"$'\n'
        uan_list+="${uan_alias}.hmn"$'\n'
        uan_list+="${uan_alias}.mgmt"$'\n'
    fi
done

# get ncn hostnames
ncn_list=$(cat /etc/hosts|grep -e nmn -e hmn -e chn -e can -e mgmt|awk '{ print $2 }')

# combine application list and ncn list into one list
ncn_uan_list=${ncn_list}$'\n'${uan_list}

# check to make sure each hostname resolves to only 1 ip
for hostname in $ncn_uan_list; do
	#echo $hostname
	ip_count=$(dig $hostname +short| wc -l)
	if [ $ip_count -gt 1 ]; then
		echo "ERROR: $hostname has more than 1 ip in DNS."
		echo "ERROR: Possible issues could be moved cables or network config issue."
		echo "ERROR: Verify cabling, network configs and discovery data."
        nslookup $hostname
		error_found=true
        echo
	fi
done

if $error_found; then
	echo "FAILED: Errors found, please see above output."
	exit 1
else
	echo "PASS: No errors found."
	exit 0
fi