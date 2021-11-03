#!/bin/bash

print_results=0
while getopts pm:a:w:h stack
do
    case "${stack}" in
          p) print_results=1;;
          m) POSTGRES_MAX_LAG=$OPTARG;;
          a) POSTGRES_MAX_ATTEMPTS=$OPTARG;;
          w) POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS=$OPTARG;;
          h) echo "usage: postgres_replication_lag.sh           # Only print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
             echo "       postgres_replication_lag.sh -p -m <max_allowed_lag> -a <number_attempts> -w <wait_seconds_between_attempts>"
             echo "default parameters: -m 0  -a 10  -w 10"
             exit 3;;
         \?) echo "usage: postgres_replication_lag.sh           # Only print 'PASS' upon success"
             echo "       postgres_replication_lag.sh -p        # Print all results and errors if found. Use for manual check."
             echo "       postgres_replication_lag.sh -p -m <max_allowed_lag> -a <number_attempts> -w <wait_seconds_between_attempts>"
             echo "default parameters: -m 0  -a 10  -w 10"
             exit 3;;
    esac
done

# The POSTGRES_MAX_LAG may be exported by the user to control
# the maximum lag value permitted by this script. Setting its value to
# a negative number or a non-integer value has the effect of skipping the
# maximum lag check. In other words, if one wishes to skip this check,
# one could:
# export POSTGRES_MAX_LAG=skip
POSTGRES_MAX_LAG=${POSTGRES_MAX_LAG:-'0'}

# POSTGRES_MAX_ATTEMPTS specifies the maximum number of times the
# postgres check will be performed on a given cluster before failing. Note that
# failures other than due to maximum lag are always fatal and are not retried.
# If unset or set to a non-positive integer, default to 10
if [[ ! $POSTGRES_MAX_ATTEMPTS =~ ^[1-9][0-9]*$ ]]; then
    POSTGRES_MAX_ATTEMPTS=10
fi

# POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS specifies the time (in seconds)
# between postgres checks on a given cluster.
# If unset or set to a non-positive integer, default to 10
if [[ ! $POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS =~ ^[1-9][0-9]*$ ]]; then
    POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS=10
fi

if [[ ! $POSTGRES_MAX_LAG =~ ^[0-9][0-9]*$ ]]; then
    echo "Skipping postgres cluster max lag checks because of POSTGRES_MAX_LAG setting"
    exit 0
else
    echo "Postgres cluster checks may take several minutes, depending on latency"
fi

failFlag=0
postgresClusters="$(kubectl get postgresql -A | grep -v NAME | awk '{print $1","$2}')"
for c in $postgresClusters
do
    # NameSpace and postgres cluster name
    c_ns="$(echo $c | awk -F, '{print $1;}')"
    c_name="$(echo $c | awk -F, '{print $2;}')"

    first_member="$(kubectl get pod -n $c_ns -l "cluster-name=$c_name,application=spilo" \
                  -o custom-columns=NAME:.metadata.name --no-headers | head -1)"

    echo -n "$c_name - "
    c_attempt=0
    c_lag_history=""
    while [ true ]; do
        c_attempt=$((${c_attempt} + 1))

        if [[ $c_attempt -gt 1 ]]; then
            # Sleep before re-attempting
            sleep $POSTGRES_WAIT_SECONDS_BETWEEN_ATTEMPTS
        fi

        cluster_lag=$(kubectl exec $first_member -c postgres -it -n ${c_ns} -- curl -s http://localhost:8008/cluster | jq '[.members[] | .lag]')
        c_max_lag=$(echo $cluster_lag | jq max)
        c_unknown_lag=$(echo $cluster_lag | grep "unknown" | wc -l)
        if [[ -n $c_lag_history ]]; then
            c_lag_history="${c_lag_history}, $c_max_lag"
        else
            c_lag_history="$c_max_lag"
        fi

        #check lag:unknown
        if [[ $c_unknown_lag -gt 0 ]]; then
            echo -e "\n--- ERROR --- $c_name cluster has lag: unknown"
            if [[ $print_results -eq 1 ]]; then failFlag=1; break;
            else exit 1; fi
        fi

        if [[ $POSTGRES_MAX_LAG =~ ^[0-9][0-9]*$ ]]; then
            #check max_lag is <= $POSTGRES_MAX_LAG
            if [[ $c_max_lag -gt $POSTGRES_MAX_LAG ]]; then
                # If we have not exhausted our number of attempts, retry
                [[ $c_attempt -ge $POSTGRES_MAX_ATTEMPTS ]] || continue

                echo -e "\n--- ERROR --- $c cluster has lag history: $c_lag_history"
                if [[ $print_results -eq 1 ]]; then failFlag=1; break;
                else exit 2; fi
            fi
        fi
        echo " OK"
        break
    done
done

if [[ $failFlag -eq 0 ]]; then echo "PASS"; exit 0;
else echo "FAIL"; exit 3; fi
