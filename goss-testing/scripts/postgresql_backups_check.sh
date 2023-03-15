#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2021-2023 Hewlett Packard Enterprise Development LP
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

# By default do not print the results
print_results=0
# Pass the test unless the latest logical-backup job has failed or the logical-backup completed but no backup exists in s3.
error_flag=0

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

# Get the list of postgresql clusters.
postgres_clusters=$(kubectl get postgresql -A --no-headers 2>/dev/null | awk '{print $1","$2}')

if [[ -z $postgres_clusters ]]
then
    if [[ $print_results -eq 1 ]]; then echo "No Postgresql clusters."; fi
fi

for c in $postgres_clusters
do
    # Set the namespace and PostgreSQL cluster name.
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"
    if [[ $print_results -eq 1 ]]; then echo -n "$c_name -- "; fi

    # Continue to the next cluster if logical backups are not enabled for this cluster.
    if [[ ! $(kubectl get postgresql -n $c_ns $c_name -o json | jq -r '.spec.enableLogicalBackup') == "true" ]]
    then # pass
	if [[ $print_results -eq 1 ]]; then echo "Logical backups are not enabled for this cluster (pass)"; fi
        continue
    fi

    # If there are any logical backup jobs for this cluster, get the latest one and determine if it Failed, Completed or still Running.
    #   Completed - check that there is a backup in s3.
    #   Failed    - set the failed flag and continue to the next cluster.
    #   Running   - continue checking the next cluster.
    if [[ ! -z $(kubectl get jobs -l application=spilo-logical-backup,cluster-name=$c_name -n $c_ns --no-headers 2>/dev/null) ]]
    then
        latest_backup_job=$(kubectl get jobs -l application=spilo-logical-backup,cluster-name=$c_name -n $c_ns \
		            --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}')

        if [[ $(kubectl get job $latest_backup_job -n $c_ns -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}') == "True" ]]
        then # fail
	    if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job failed (fail)"; fi
            error_flag=1
            continue
         elif [[ $(kubectl get job $latest_backup_job -n $c_ns -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}') == "True" ]]
         then # pass
            if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job completed"; fi
         else # pass
    	    if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job is running - neither failed or completed at this point in time (pass)"; fi
            continue
         fi
    else # pass
	if [[ $print_results -eq 1 ]]; then echo "No logical backup jobs have run at this point in time (pass)"; fi
        continue
    fi

    # Given the logical-backup job succeeded for the cluster - check that backup(s) exist in s3.
    #   None  - set the failed flag and continue to the next cluster.
    #   Exist - print the latest backup key and time stamp.
    backup_key_and_date=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" \
	                  '.artifacts[] | select(.Key | contains($cluster)) | "\(.Key) \(.LastModified)"')

    if [[ ! -z ${backup_key_and_date} ]]
    then # pass
	if [[ $print_results -eq 1 ]]
        then # Find the latest backup key to print
	    latest_s3backup_time=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" \
		                   '[.artifacts[] |  select(.Key | contains($cluster)).LastModified] | sort | .[-1]')

	    latest_s3backup_key=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" --arg time $latest_s3backup_time \
		                  '.artifacts[] | select((.Key | contains($cluster)) and (.LastModified==$time)) | .Key')

	    echo "  Most recent backup ${latest_s3backup_key} at ${latest_s3backup_time} (pass)"
	 fi
    else # fail
       if [[ $print_results -eq 1 ]]; then echo " Postgres backup(s) are missing from s3 (fail)"; fi
       error_flag=1
       continue
    fi
done

if [[ error_flag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1;
fi
