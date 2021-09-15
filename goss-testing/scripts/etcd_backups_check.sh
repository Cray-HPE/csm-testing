#!/bin/bash

# checks age of cluster
# if cluster is older than 24 hours, checks that a backup was created within the last 24 hours

current_date_sec=$(date +"%s")
one_day_sec=86400

check_backup_within_day() {
    backup_within_day=0
    backups=$(kubectl exec -it -n operators $(kubectl get pod -n operators | \
        grep etcd-backup-restore | head -1 | awk '{print $1}') -c boto3 -- list_backups ${cluster})
    if [[ "$backups" != *"KeyError: 'Contents'"* ]] && [[ ! -z $backups ]] # check if any backups exist
    then
        for backup in $backups
        do
	    backup_date=$(echo ${backup: -20} | sed "s/-/ /3")
            if [[ ! -z $backup_date ]]
	    then
		backup_sec=$(date -d "${backup_date}" "+%s" 2>/dev/null)
		if [[ ! -z $backup_sec && $(( $current_date_sec - $backup_sec )) -lt $one_day_sec ]] # check if backup is less that 24 hour old
                then
                    backup_within_day=1
                    break
                fi
            fi
        done
    fi
}


for cluster in cray-bos cray-bss cray-crus cray-externaldns cray-fas
do
    # look at age of cluster
    age=$(kubectl get etcd ${cluster}-etcd -n services -o jsonpath='{.metadata.creationTimestamp}')
    if [[ ! -z $age ]]
    then
        age_sec=$(date -d "${age}" "+%s")
        if [[ $(( $current_date_sec - $age_sec )) -gt $one_day_sec ]]
        then
            check_backup_within_day $cluster
            if [[ $backup_within_day -eq 0 ]]; then exit 1; fi
        fi
    else
        exit 2
    fi
done

echo "PASS"
exit 0
