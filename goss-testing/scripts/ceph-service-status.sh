#!/bin/bash
# Copyright 2021 Hewlett Packard Enterprise Development LP

# Default values
verbose=false

while getopts n:s:a:A:v:h stack
do
  case "${stack}" in
          n) node=$OPTARG;;
          s) service=$OPTARG;;
          a) all_services=$OPTARG;;
          A) all=$OPTARG;;
          v) verbose=$OPTARG;;
          h) echo "usage:  ceph-service-status.sh # runs a simple ceph health check"
             echo "        ceph-service-status.sh -n <node> -s <service> # checks a single service on a single node"
             echo "        ceph-service-status.sh -n <node> -a true # checks all Ceph services on a node"
             echo "        ceph-service-status.sh -A true # checks all Ceph services on all nodes in a rolling fashion"
             echo "        ceph-service-status.sh -s <service name> # will find the where the service is running and report its status"
             exit 0;;
          \?) echo "usage:  ceph-service-status.sh # runs a simple ceph health check"
             echo "        ceph-service-status.sh -n <node> -s <service> # checks a single service on a single node"
             echo "        ceph-service-status.sh -n <node> -A true # checks all Ceph services on a node"
             echo "        ceph-service-status.sh -a true # checks all Ceph services on all nodes in a rolling fashion"
             echo "        ceph-service-status.sh -s <service name> # will find the where the service is running and report its status"
             exit 1;;
  esac
done

function check_service(){
  if [[ $service =~ "osd" ]]
    then
      if [[ -n "$osd" ]]
      then
        osd_id=$(echo "$osd"|cut -d '.' -f2)
      else
        osd_id=$(echo "$service"|cut -d '.' -f2)
      fi
      current_start_time=$(ceph orch ps --daemon_type osd --hostname "$host" -f json-pretty |jq --arg osd_id "$osd_id" -r '.[]|select(.daemon_id==$osd_id)|.started')
      current_epoch=$(date +%s)
      if [[ -n "$current_start_time" ]]
      then
        current_start_epoch=$(date -d "$current_start_time" +%s 2>/dev/null)
        diff=$((current_epoch-current_start_epoch))
      elif [[ -z "$current_start_time" ]]
      then
        if [[ $verbose == "true" ]]
        then
          echo "Tests run: $tests  Tests Passed: $passed"
        fi
        exit 1
      fi

      if [[ -n "$osd" ]]
      then
        read -r -d "\n" up in < <(ceph osd info "$osd" -f json-pretty|jq '.up, .in')
      else
        read -r -d "\n" up in < <(ceph osd info "$service" -f json-pretty|jq '.up, .in')
      fi

      if [[ $verbose == "true" ]]
      then
        echo "Service $service on $host is reporting up for $diff seconds"
        echo "$service's status is reporting up: $up  in: $in"
      fi
      if [[ -n "$osd_id" ]] || [[ -n "$osd" ]]
      then
        read -r -d "\n" service_unit status < <(pdsh -N -w "$host" podman ps --format json 2>&1 |grep -v "Permanently added"|jq --arg osd "$osd_prefix$osd_id" -r '.[]|select(.Names[]|endswith($osd))|.Names[], .State')
        (( tests++ ))
        if [[ "$service_unit" =~ $FSID_STR-$osd_prefix$osd_id ]]
        then
          (( passed++ ))
        fi
      else
        read -r -d "\n" service_unit status < <(pdsh -N -w "$host" podman ps --format json 2>&1|grep -v "Permanently added"|jq --arg service "$service" -r '.[]|select(.Names[]|contains($service))|.Names[], .State')
        (( tests++ ))
        if [[ "$service_unit" =~ $FSID_STR-$service ]]
        then
          (( passed++ ))
        fi
      fi
      if [[ $verbose == "true" ]]
      then
        echo "Service unit name: $service_unit"
        echo "Status: $status"
      fi

   elif [[ $service =~ "mds" ]]
     then
      active_mds=$(ceph fs status -f json-pretty|jq -r '.mdsmap[]|select(.state=="active")|.name')
      mds_id=$(echo "$service"|cut -d '.' -f2,3,4)
      current_start_time=$(ceph orch ps --daemon_type mds --hostname "$host" -f json-pretty |jq --arg mds_id "$mds_id" -r '.[]|select(.daemon_id==$mds_id)|.started')
      current_epoch=$(date +%s)
      if [[ -n "$current_start_time" ]]
      then
        current_start_epoch=$(date -d "$current_start_time" +%s 2>/dev/null)
        diff=$((current_epoch-current_start_epoch))
      elif [[ -z "$current_start_time" ]]
      then
        exit 1
      fi

      active=$(ceph orch ps --daemon_type mds --hostname "$host" -f json-pretty|jq --arg mds_id "$mds_id" -r '.[]|select(.daemon_id==$mds_id)|.is_active')
      if [[ $verbose == "true" ]]
      then
        echo "Service $service on $node is reporting up for $diff seconds"
        echo "$service is_active: $active"
      fi
      if [[ "${active}" == "true" ]] && [[ -n $( echo "$active_mds" | grep $service ) ]]
      then
        (( active_test++ ))
      fi
      service_name=$(echo "$service"|cut -d '.' -f2)
      read -r -d "\n" service_unit status < <(pdsh -N -w "$host" podman ps --format json 2>&1|grep -v "Permanently added"|jq --arg service "mds-$service_name" -r '.[]|select(.Names[]|contains($service))|.Names[], .State')
      (( tests++ ))
      if [[ "$service_unit" =~ $FSID_STR-$service ]]
      then
        (( passed++ ))
      fi
      echo "Service unit name: $service_unit"
      echo "Status: $status"
  else
      service_name=$(echo $service|cut -d "." -f 1)
      current_epoch=$(date +%s)
      current_start_time=$(ceph orch ps --hostname "$host" --daemon_type "$service_name" -f json-pretty|grep -v "Permanently added"|jq -r '.[]|select(".daemon_id==$service")|.started')
      if [[ -n "$current_start_time" ]]
      then
        current_start_epoch=$(date -d "$current_start_time" +%s) 2>&-
        diff=$((current_epoch-current_start_epoch))
      fi
      if [[ $verbose == "true" ]]
      then
        echo "Service $service on $node has been restarted and up for $diff seconds"
        echo "$service is: $(ceph orch ps --daemon_type $service_name --hostname "$host" -f json-pretty|jq -r '.[].status_desc')"
      fi
      # adding service_name_2 to make the selection more specific, sometimes a random string contains mds, rgw, etc. which fails a test
      service_name_2=$(echo $service|cut -d "." -f 2)
      read -r -d "\n" service_unit status  < <(pdsh -N -w "$host" podman ps --format json 2>&1|grep -v "Permanently added"|jq --arg service "${service_name}-${service_name_2}" -r '.[]|select(.Names[]|contains($service))|.Names[], .State')
      (( tests++ ))
      if [[ "$service_unit" =~ $FSID_STR-$service_name ]]
      then
        (( passed++ ))
      fi
      if [[ $verbose == "true" ]]
      then
        echo "Service unit name: $service_unit"
        echo "Status: $status"
      fi
  fi
}

function check_ceph_health_basic() {
  ceph_status=$(ceph health -f json-pretty | jq -r .status)
  (( tests++ ))
  if [[ $ceph_status == "HEALTH_OK" ]]; then
    if [[ $verbose == "true" ]]
    then
      echo "Ceph is reporting a status of $ceph_status"
    fi
    (( passed++ ))
  else
    if [[ $verbose == "true" ]]
    then
      echo "Ceph is reporting a status of $ceph_status and may need to be investigated"
    fi
  fi
}


### MAIN ###

FSID=$(ceph status -f json-pretty |jq -r .fsid)
FSID_STR="ceph-$FSID"
if [[ $verbose == "true" ]]
then
  echo "FSID: $FSID  FSID_STR: $FSID_STR"
fi
tests=0
passed=0
active_test=0
num_storage_nodes=$(craysys metadata get num-storage-nodes)
version=$(ceph version --format json|jq -r '.["version"]'|awk '{print $3}'|awk -F "." '{print $1}')


if [[ $version -lt 16 ]]; then
  osd_prefix="osd."
else 
  osd_prefix="osd-"
fi

check_ceph_health_basic

if [[ $verbose == "true" ]]
then
  echo "Updating ssh keys.."
fi

truncate --size=0 ~/.ssh/known_hosts  2>&1

for node_num in $(seq 1 "$num_storage_nodes"); do
  nodename=$(printf "ncn-s%03d" "$node_num")
  ssh-keyscan -H "$nodename" 2> /dev/null >> ~/.ssh/known_hosts
done

for node_num in $(seq 1 "$num_storage_nodes"); do
 nodename=$(printf "ncn-s%03d.nmn" "$node_num")
 ssh-keyscan -H "$nodename" 2> /dev/null >> ~/.ssh/known_hosts
done

# check all services on all nodes
if [[ $all == "true" ]]
then
  for host in $(ceph orch host ls -f json-pretty |jq -r '.[].hostname');
  do
    if [[ $verbose == "true" ]]
    then
      echo -ne "\nHOST: $host"
      echo "#######################"
    fi
    for service in $(ceph orch ps "$host" -f json-pretty |jq -r '.[]|.daemon_type+"."+.daemon_id'|grep -v crash)
    do
      check_service
    done
  done
fi

# check all or a specific service on a specific node
if [[ -n "${node+x}" ]]
then
  for host in $node;
  do
     if [[ $verbose == "true" ]]
     then
       echo -ne "\nHOST: $host"
       echo "#######################"
     fi
     if [[ $all_services == "true" ]]
     then
       for service in $(ceph orch ps "$host" -f json-pretty |jq -r '.[]|.daemon_type+"."+.daemon_id'|grep -v crash)
       do
         check_service
       done
     elif [[ $service =~ "osd" ]]
     then
       for osd in $(ceph orch ps --daemon_type osd --hostname "$host" -f json-pretty |jq -r '.[]|(.daemon_type+"."+.daemon_id)')
       do
         check_service 
       done
     elif [[ $service =~ "mds" ]]
     then
       for mds in $(ceph orch ps --daemon_type mds --hostname "$host" -f json-pretty |jq -r '.[]|(.daemon_type+"."+.daemon_id)')
       do
         check_service
       done
     else
       check_service
     fi
  done
fi

# check specific service(s) on all nodes
if [[ -n "${service+x}" && ! -n "${node+x}" ]]
  then
    for host in $(ceph orch ps --daemon_type $service -f json-pretty |jq -r '.[].hostname' | sort -u);
    do
      node=$host
      if [[ $verbose == "true" ]]
      then
        echo -ne "\nHOST: $host"
        echo "#######################"
      fi
      if [[ $service =~ "osd" ]]
       then
         for osd in $(ceph orch ps --daemon_type osd --hostname "$host" -f json-pretty |jq -r '.[]|(.daemon_type+"."+.daemon_id)')
         do
          check_service
         done
      elif [[ $service =~ "mds" ]]
        then
          for service in $(ceph orch ps --daemon_type mds --hostname "$host" -f json-pretty |jq -r '.[]|(.daemon_type+"."+.daemon_id)')
          do
            check_service
         done
      else
         check_service
      fi
    done
fi


if [ $tests -ne $passed ]
then
  if [[ $verbose == "true" ]]
  then
    echo "Tests run: $tests  Tests Passed: $passed"
    ceph health detail
  fi
  exit 1
else
  if [[ $verbose == "true" ]]
  then
    echo "Tests run: $tests  Tests Passed: $passed"
  fi
  exit 0
fi
