#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022-2024 Hewlett Packard Enterprise Development LP
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
exit_on_failure=0
while getopts pem:a:w:h stack
do
    case "${stack}" in
          p) print_results=1;;
          e) exit_on_failure=1;;
          m) POSTGRES_MAX_LAG=$OPTARG;;
          a) POSTGRES_MAX_ATTEMPTS=$OPTARG;;
          w) POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS=$OPTARG;;
          h) echo "usage: postgres_replication_lag.sh           # Print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
             echo "       postgres_replication_lag.sh -p -e     # Print all results and errors if found. Exit if failure is encountered."
             echo "       postgres_replication_lag.sh -p -m <max_allowed_lag> -a <number_attempts> -w <wait_seconds_between_attempts>"
             echo "default parameters: -m 0  -a 10  -w 10"
             exit 4;;
         \?) echo "usage: postgres_replication_lag.sh           # Print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
             echo "       postgres_replication_lag.sh -p -e     # Print all results and errors if found. Exit if failure is encountered."
             echo "       postgres_replication_lag.sh -p -m <max_allowed_lag> -a <number_attempts> -w <wait_seconds_between_attempts>"
             echo "default parameters: -m 0  -a 10  -w 10"
             exit 4;;
    esac
done

function postgres_leader()
{
    # Get the postgres leader
    # If patronictl list fails, try the others member when attempting to determine the leader.
    c_leader=""
    for member in $(seq 0 $(( ${c_pods} -1 )))
    do
        p_list=$(kubectl exec "${c_name}-${member}" -c postgres -n ${c_ns} -- patronictl list -f json 2>/dev/null)

        if [[ $? == 0 ]]; then
            c_leader=$(echo $p_list | jq -r '.[] | select((.Role == "Leader") and (.State =="running")) | .Member')
            echo "  Found leader ${c_leader} from ${c_name}-${member}."
            break
        else
            echo "  Unable to determine the leader from ${c_name}-${member}, trying the next member."
            continue
        fi
    done
}



# The POSTGRES_MAX_LAG environment variable may be exported by the user to control
# the maximum lag value permitted by this script. Setting its value to
# a negative number or a non-integer value has the effect of skipping the
# maximum lag check. In other words, if one wishes to skip this check,
# one could:
# export POSTGRES_MAX_LAG=skip
POSTGRES_MAX_LAG=${POSTGRES_MAX_LAG:-'0'}

# POSTGRES_MAX_ATTEMPTS specifies the maximum number of times the
# PostgreSQL check will be performed on a given cluster before failing. Note that
# failures other than due to maximum lag are always fatal and are not retried.
# If unset or set to a non-positive integer, default to 10
if [[ ! $POSTGRES_MAX_ATTEMPTS =~ ^[1-9][0-9]*$ ]]; then
    POSTGRES_MAX_ATTEMPTS=10
fi

# POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS specifies the time (in seconds)
# between PostgreSQL checks on a given cluster.
# If unset or set to a non-positive integer, default to 10
if [[ ! $POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS =~ ^[1-9][0-9]*$ ]]; then
    POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS=10
fi

if [[ ! $POSTGRES_MAX_LAG =~ ^[0-9][0-9]*$ ]]; then
    echo "Skipping PostgreSQL cluster max lag checks because of POSTGRES_MAX_LAG setting"
    exit 0
else
    echo "PostgreSQL cluster checks may take several minutes, depending on the number of attempts per cluster."
fi

echo "Checking to see if any cluster members need a patroni service restart."

postgresClusters="$(kubectl get postgresql -A | grep -v NAME | awk '{print $1","$2","$5}')"
for c in $postgresClusters
do
    # NameSpace and PostgreSQL cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"
    c_pods="$(echo $c | awk -F, '{print $3;}')"

    echo "Cluster $c_name:"
    # Get the postgres leader (c_leader)
    postgres_leader

    if [[ -z $c_leader ]]; then
        echo "  No Leader exists for $c_name cluster - unable to restart patroni service."
        continue
    fi

    # Get the cluster details from the leader
    c_cluster_details=$(kubectl exec ${c_leader} -c postgres -n ${c_ns} -- patronictl list -f json)

    # Determine if a reinit is in progress (member state is "creating replica")
    c_cluster_state=$(echo $c_cluster_details | jq '.[] | ."State"' | grep "creating replica" | wc -l)

    # Determine the max lag across all members, unknown lag count across all members, list of lagging member by pod name
    c_max_lag=$(echo $c_cluster_details | jq '[.[] | select((."Lag in MB" != "unknown"))."Lag in MB"] | max')
    c_unknown_lag=$(echo $c_cluster_details | jq '.[] | ."Lag in MB"' | grep "unknown" | wc -l)
    c_members_lagging=$(echo $c_cluster_details | jq -r '.[] | select(((."Lag in MB" > 0) or (."Lag in MB" == "unknown"))).Member')

    # Exit with success if any member state is "creating replica"
    if [[ $c_cluster_state -gt 0 ]]; then
        echo "  Cluster member is already being reinit'ed for $c_name cluster - patroni service restart not needed."
        continue
    fi

    # Exit with success if no lag is found
    if [[ $c_unknown_lag -eq 0 ]] && [[ $c_max_lag -eq 0 ]]; then
        echo "  No lag was found for $c_name cluster - patroni service restart not needed."
        continue
    fi

    # Restart patroni for any members found to be lagging ( >0 or "unknown" )
    for member in $c_members_lagging
    do
        echo "  Restarting patroni service on $member in $c_ns namespace"
        kubectl exec $member -n $c_ns -c postgres -- /bin/sh -c 'sv stop patroni; sv start patroni'
    done
done

echo "Done checking for patroni service restarts, validating lag."

failFlag=0
postgresClusters="$(kubectl get postgresql -A | grep -v NAME | awk '{print $1","$2","$5}')"
for c in $postgresClusters
do
    # NameSpace and PostgreSQL cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"
    c_pods="$(echo $c | awk -F, '{print $3;}')"

    echo "Cluster $c_name:"
    # Get the postgres leader (c_leader)
    postgres_leader

    if [[ -z $c_leader ]]; then
        echo "No Leader exists for $c_name cluster - unable to check for lag."
        failFlag=1
        continue
    fi

    if [[ $print_results -eq 1 ]]; then echo -n "  $c_name - "; fi
    c_attempt=0
    c_lag_history=""
    while [ true ]; do
        c_attempt=$((${c_attempt} + 1))

        if [[ $c_attempt -gt 1 ]]; then
            # Sleep before re-attempting
            sleep $POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS
        fi

        # We omit the often-seen '-it' flags from the kubectl call because we do not need to pass in stdin, and using
        # those flags generates warning messages when this script is run in some contexts.

        c_cluster_details=$(kubectl exec ${c_leader} -c postgres -n ${c_ns} -- patronictl list -f json)
        c_max_lag=$(echo $c_cluster_details | jq '[.[] | select((."Lag in MB" != "unknown"))."Lag in MB"] | max')
        c_unknown_lag=$(echo $c_cluster_details | jq '.[] | ."Lag in MB"' | grep "unknown" | wc -l)
        if [[ -n $c_lag_history ]]; then
            c_lag_history="${c_lag_history}, $c_max_lag"
        else
            c_lag_history="$c_max_lag"
        fi

        #check lag:unknown
        if [[ $c_unknown_lag -gt 0 ]]; then
            if [[ $print_results -eq 1 ]]
            then 
                echo -e "\n  --- ERROR --- $c_name cluster has lag: unknown"
                kubectl -n $c_ns exec $c_leader -c postgres -- patronictl list 2>/dev/null
                if [[ $exit_on_failure -eq 1 ]]; then exit 1; else failFlag=1; fi
                break;
            else exit 1; fi
        fi

        #check max_lag is <= $POSTGRES_MAX_LAG
        if [[ $c_max_lag -gt $POSTGRES_MAX_LAG ]]; then
            # If we have not exhausted our number of attempts, retry
            [[ $c_attempt -ge $POSTGRES_MAX_ATTEMPTS ]] || continue

            if [[ $print_results -eq 1 ]]
            then 
                echo -e "\n  --- ERROR --- $c cluster has lag history: $c_lag_history"
                kubectl -n $c_ns exec $c_leader -c postgres -- patronictl list 2>/dev/null
                if [[ $exit_on_failure -eq 1 ]]; then exit 2; else failFlag=1; fi
                break;
            else exit 2; fi
        fi
        if [[ $print_results -eq 1 ]]; then echo " OK"; fi
        break
    done
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 3; fi
