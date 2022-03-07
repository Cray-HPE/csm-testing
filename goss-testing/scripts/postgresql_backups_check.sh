#!/bin/bash
#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: postgresql_backups_check.sh           # Only print 'PASS' upon success"
             echo "       postgresql_backups_check.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: postgresql_backups_check.sh           # Only print 'PASS' upon success"
             echo "       postgresql_backups_check.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

# checks age of cluster
# if cluster is older than 24 hours, checks that a backup was created within the last 24 hours

current_date_sec=$(date +"%s")
one_day_sec=86400

check_backup_within_day() {
    backup_within_day=0
    cluster_backups=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "$c_name" '.artifacts[].Key | select(contains($cluster))')

    if [[ ! -z $cluster_backups ]] # check if any backups exist
    then
        for backup in $cluster_backups
        do
            backup_prefix=$(echo $backup | cut -d '.' -f1)
            backup_date=${backup_prefix: -19}
            if [[ ! -z $backup_date ]]
            then
                backup_sec=$(date -d "${backup_date}" "+%s" 2>/dev/null)
                if [[ ! -z $backup_sec && $(( $current_date_sec - $backup_sec )) -lt $one_day_sec ]] # check if backup is less that 24 hours old
                then
                    backup_within_day=1
                    if [[ $print_results -eq 1 ]]
                    then echo "$c_name -- recent backup found: $backup"
                    fi
                    break
                fi
            fi
        done
    fi
}

error_flag=0

postgres_clusters_wBackup=$(kubectl get cronjobs -A | grep postgresql-db-backup | awk '{print $1","$2}')
if [[ -z $postgres_clusters_wBackup ]]
then
    if [[ $print_results -eq 1 ]]; then echo "No Postgresql clusters have automatic backups set in cron jobs."; fi
    error_flag=1
fi

for c in $postgres_clusters_wBackup
do

    # NameSpace and PostgreSQL cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_cronjob_name="$(echo $c | awk -F, '{print $2;}')"
    c_name=${c_cronjob_name%"ql-db-backup"}     # remove suffix 'ql-db-backup'
    c_name=${c_name#"cray-"}                    # remove prefix 'cray-'
    c_name=$(kubectl get postgresql -n ${c_ns} | grep $c_name |awk '{print $1}')

    # Base the c_age on the cronjob creation time instead of when the postgres resource was created.
    # During upgrades, cronjobs may get re-created if they failed to start due to too many missed starts.
    c_age=$(kubectl get cronjobs.batch ${c_cronjob_name} -n ${c_ns} -o jsonpath='{.metadata.creationTimestamp}')
    c_age_sec=$(date -d "${c_age}" "+%s")

    if [[ ! -z $c_age && ! -z $c_age_sec ]]
    then
        if [[ $(( $current_date_sec - $c_age_sec )) -gt $one_day_sec ]]
        then
            check_backup_within_day
            if [[ $backup_within_day -eq 0 ]] 
            then 
                if [[ $print_results -eq 1 ]]; then echo "Error: No recent backup found for $c_name."; error_flag=1; 
                else exit 1; fi
            fi
        else
            if [[ $print_results -eq 1 ]]; then echo "$c_name is less than 24 hours old. Did not check if recent backups exist."; fi
        fi
    else
        if [[ $print_results -eq 1 ]]; then echo "Error: could not find age of $c_name."; error_flag=1;
        else exit 2; fi
    fi
done

if [[ error_flag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1; 
fi
