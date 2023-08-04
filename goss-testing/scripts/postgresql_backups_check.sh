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
# Check each postgresql cluster for backups
# If logical backup is not enabled -- pass
# If the operator and cluster have been running for >10m and the logical backup cronjob is missing -- fail
# If the latest logical backup job failed -- fail
# If the logical backup job succeeded but no backup exists in s3 - fail

print_results=0
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

tmp_dir=$(mktemp -d)
trap 'rm -rf "${tmp_dir}"; unset CRAY_CREDENTIALS' EXIT
admin_secret=$(kubectl get secrets admin-client-auth -ojsonpath='{.data.client-secret}' | base64 -d)
curl -k -s -d grant_type=client_credentials \
        -d client_id=admin-client \
        -d client_secret="$admin_secret" https://api-gw-service-nmn.local/keycloak/realms/shasta/protocol/openid-connect/token > "${tmp_dir}/cray-token.json"
export CRAY_CREDENTIALS="${tmp_dir}/cray-token.json"

current_date_sec=$(date +"%s")

# Given a timestamp, determine how many minutes have elapsed.
minutes_since_creation_timestamp() {

    creation_timestamp=$1       # e.g. 2023-02-03T16:48:16.919000+00:00 or 2023-02-03T16:48:16Z

    minutes=0
    creation_timestamp=$(echo ${creation_timestamp} | cut -d '.' -f1)  # e.g. 2023-02-02T22:55:22
    creation_timestamp_sec=$(date -d "${creation_timestamp}" "+%s" 2>/dev/null)
    minutes=$(( (${current_date_sec} - ${creation_timestamp_sec})/60 ))
    echo "$minutes"
}

# Determine how long the postgres-operator has been running. 
# Every 10 minutes when the operator syncs, it will create the logical backup cronjobs if any are not yet present.

postgres_operator_creation_timestamp=$(kubectl get pods -n services -l app.kubernetes.io/name=postgres-operator -o json | jq -r '.items[0].metadata.creationTimestamp')
postgres_operator_min=$(minutes_since_creation_timestamp ${postgres_operator_creation_timestamp})

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
    then
	if [[ $print_results -eq 1 ]]; then echo "Logical backups are not enabled for this cluster (pass)"; fi
        continue
    fi

    # The postgres operator sync's every 10 minutes and will create the logical backup cronjob if they do not exist.
    # If the postgres operator and postgres cluster have each existed for at least 10 minutes, fail the test if the cronjob is missing.

    postgresql_creation_timestamp=$(kubectl get postgresql -n $c_ns $c_name -o json | jq -r '.metadata.creationTimestamp')
    postgresql_min=$(minutes_since_creation_timestamp ${postgresql_creation_timestamp})
    if [[ ${postgresql_min} -gt 10 ]] && [[ ${postgres_operator_min} -gt 10 ]]
    then
        cronjob=$(kubectl get cronjob -n $c_ns | grep $c_name | grep "logical-backup" | awk '{print $1}')
	if [[ -z ${cronjob} ]]
        then
	    if [[ $print_results -eq 1 ]] 
	    then 
                echo "Logical backup cronjob is missing (fail)"
	        error_flag=1
                continue
	    fi
	fi
    else
	if [[ $print_results -eq 1 ]]; then echo "Logical backup cronjob may not exist yet (pass)"; fi
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
        then
	    if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job failed (fail)"; fi
            error_flag=1
            continue
        elif [[ $(kubectl get job $latest_backup_job -n $c_ns -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}') == "True" ]]
        then
            if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job completed"; fi
        else
    	    if [[ $print_results -eq 1 ]]; then echo "Latest $latest_backup_job job is running - neither failed or completed at this point in time (pass)"; fi
            continue
        fi
    else
	if [[ $print_results -eq 1 ]]; then echo "Cronjob exists, but no logical backup jobs have run at this point in time (pass)"; fi
        continue
    fi

    # Given the logical-backup job succeeded for the cluster - check that backup(s) exist in s3.
    #   None  - set the failed flag and continue to the next cluster.
    #   Exist - print the latest backup key and time stamp.

    backup_key_and_date=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" \
	                  '.artifacts[] | select(.Key | contains($cluster)) | "\(.Key) \(.LastModified)"')

    if [[ ! -z ${backup_key_and_date} ]]
    then
	if [[ $print_results -eq 1 ]]
        then # Find the latest backup key to print
	    latest_s3backup_time=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" \
		                   '[.artifacts[] |  select(.Key | contains($cluster)).LastModified] | sort | .[-1]')

	    latest_s3backup_key=$(cray artifacts list postgres-backup --format json | jq -r --arg cluster "spilo/$c_name" --arg time $latest_s3backup_time \
		                  '.artifacts[] | select((.Key | contains($cluster)) and (.LastModified==$time)) | .Key')

	    echo "  Most recent backup ${latest_s3backup_key} at ${latest_s3backup_time} (pass)"
	 fi
    else
        if [[ $print_results -eq 1 ]]; then echo " Postgres backup(s) are missing from s3 (fail)"; fi
        error_flag=1
        continue
    fi
done

if [[ error_flag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 1;
fi
