#!/bin/bash

# (C) Copyright 2022 Hewlett Packard Enterprise Development LP.
#
# MIT License
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

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: etcd_backups_check.sh           # Only print 'PASS' upon success"
             echo "       etcd_backups_check.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: etcd_backups_check.sh           # Only print 'PASS' upon success"
             echo "       etcd_backups_check.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

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
            backup_date=$(echo ${backup##*_} | sed "s/-/ /3")
            if [[ ! -z $backup_date ]]
            then
                backup_sec=$(date -d "${backup_date}" "+%s" 2>/dev/null)
                if [[ ! -z $backup_sec && $(( $current_date_sec - $backup_sec )) -lt $one_day_sec ]] # check if backup is less that 24 hours old
                then
                    backup_within_day=1
                    if [[ $print_results -eq 1 ]]
                    then echo "$cluster -- recent backup found: $backup"
                    fi
                    break
                fi
            fi
        done
    fi
}

error_flag=0
for cluster in cray-bos cray-bss cray-crus cray-fas
do
    # look at age of cluster
    age=$(kubectl get etcd ${cluster}-etcd -n services -o jsonpath='{.metadata.creationTimestamp}')
    if [[ ! -z $age ]]
    then
        age_sec=$(date -d "${age}" "+%s")
        if [[ $(( $current_date_sec - $age_sec )) -gt $one_day_sec ]]
        then
            check_backup_within_day $cluster
            if [[ $backup_within_day -eq 0 ]] 
            then 
                if [[ $print_results -eq 1 ]]; then echo "Error: No recent backup found for $cluster."; error_flag=1; 
                else exit 1; fi
            fi
        else
            if [[ $print_results -eq 1 ]]; then echo "$cluster is less than 24 hours old. Did not check if recent backups exist."; fi            
        fi
    else
        if [[ $print_results -eq 1 ]]; then echo "Error: could not find age of $cluster."; error_flag=1;
        else exit 2; fi
    fi
done

if [[ error_flag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; 
fi
