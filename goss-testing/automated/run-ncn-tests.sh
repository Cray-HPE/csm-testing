#!/usr/bin/env bash
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
# This file is sourced by the NCN automated testing scripts.

function print_warn {
    echo "WARNING: $*" 1>&2
}

function print_error {
    echo "ERROR: $*" 1>&2
}

# Print an error message and exit
function err_exit {
    print_error "$@"
    exit 1
}

function is_pit_node {
    [[ -f /etc/pit-release ]]
    return $?
}

# Prints a list of all NCNs
# Prints warnings if there are fewer than expected
function get_ncns {
    # Usage: get_ncns [--exclude-pit] [--masters] [--storage] [--workers]
    #
    # The base set of NCNs returned is based on the --masters, --storage, --workers flags.
    # If none of those are specified, then all NCNs are included. If any of them are specified, then
    # only the specified types of NCNs are returned.
    #
    # Regardless of the above, if --exclude-pit is specified, and this function is being called on the PIT node,
    # then ncn-m001 will be excluded from the results.
    # 
    local ncns type_char_pattern type_string

    local masters=N
    local storage=N
    local workers=N
    local exclude_m001=N

    while [[ $# -gt 0 ]]; do
        case "$1" in
            "--masters") masters=Y ;;
            "--storage") storage=Y ;;
            "--workers") workers=Y ;;
            "--exclude-pit") if is_pit_node; then exclude_m001=Y ; fi ;;
            *) err_exit"PROGRAMMING LOGIC ERROR: get_ncns: Invalid argument: '$1'"
        esac
        shift
    done
    if [[ ${masters} == N && ${storage} == N && ${workers} == N ]]; then masters=Y ; storage=Y; workers=Y; fi

    if [[ ${masters} == N ]]; then
        # No need to exclude ncn-m001 if we aren't including it in the first place
        exclude_m001=N
    fi

    if [[ ${masters} == Y && ${storage} == Y && ${workers} == Y ]]; then
        type_string="NCN"
        type_char_pattern="[msw]"
    else
        type_string=""
        type_char_pattern="["
        if [[ ${masters} == Y ]]; then type_char_pattern+="m" ; type_string+="/master" ; fi
        if [[ ${storage} == Y ]]; then type_char_pattern+="s" ; type_string+="/storage" ; fi
        if [[ ${workers} == Y ]]; then type_char_pattern+="w" ; type_string+="/worker" ; fi
        type_string+=" NCN"
        # Strip the first character, which is a /
        type_string=${type_string:1}
        type_char_pattern="${type_char_pattern}]"
    fi
    # Pattern to match 100-999: [1-9][0-9][0-9]
    # Pattern to match 010-099: 0[1-9][0-9]
    # Pattern to match 001-009: 00[1-9]
    local ncn_num_pattern="([1-9][0-9][0-9]|0[1-9][0-9]|00[1-9])"
    local ncn_string_pattern="ncn-${type_char_pattern}${ncn_num_pattern}"

    # Define a local function to do the output filtering based on the arguments passed in here.
    # End with a grep command that will give status code 0 if any output is matched (that is, the output is not blank)
    if [[ ${exclude_m001} == Y ]]; then
        function __unique_ncns { grep -oE "${ncn_string_pattern}" | sort -u | grep -v ncn-m001 | grep . ; }
    else
        function __unique_ncns { grep -oE "${ncn_string_pattern}" | sort -u | grep . ; }
    fi

    # If the GOSS_TEST_NCN_LIST environment variable has been set, this will be used. This allows users a method to
    # run the automated scripts in cases where the usual methods of obtaining the NCN list does not work.
    if [[ -n ${GOSS_TEST_NCN_LIST} ]]; then
        if echo "${GOSS_TEST_NCN_LIST}" | __unique_ncns ; then
            return 0
        fi
        print_warn "GOSS_TEST_NCN_LIST variable is set, but unable to obtain ${type_string} list from it: '${GOSS_TEST_NCN_LIST}'"
    fi

    if is_pit_node; then
        if [[ -z ${PITDATA} ]]; then
            print_warn "The PITDATA environment variable is not set."
        elif [[ -z ${SYSTEM_NAME} ]]; then
            print_warn "The SYSTEM_NAME environment variable is not set."
        else
            local sys_prep_dir="${PITDATA}/prep/${SYSTEM_NAME}"
            local sls_json="${sys_prep_dir}/sls_input_file.json"
            local sys_prep_dnsmasqd_statics="${sys_prep_dir}/dnsmasq.d/statics.conf"

            if [[ ! -s ${sls_json} ]]; then
                print_warn "The '${sls_json}' file does not exist or is empty"
            else
                if cat "${sls_json}" |
                        jq -r '.Hardware | .[] | select(.Type=="comptype_node" and .TypeString=="Node" and .ExtraProperties.Role=="Management") | .ExtraProperties.Aliases | .[]' |
                        __unique_ncns
                then
                    return 0
                fi
                print_warn "Unable to obtain ${type_string} list from '${sls_json}'"
            fi

            if [[ ! -s ${sys_prep_dnsmasqd_statics} ]]; then
                print_warn "The '${sys_prep_dnsmasqd_statics}' file does not exist or is empty"
            else
                if cat "${sys_prep_dnsmasqd_statics}" | __unique_ncns ; then
                    return 0
                fi
                print_warn "Unable to obtain ${type_string} list from '${sys_prep_dnsmasqd_statics}'"
            fi
        fi
        
        # Final backup option is to use the live dnsmasq statics file
        local dnsmasqd_statics=/etc/dnsmasq.d/statics.conf

        if [[ ! -s ${dnsmasqd_statics} ]]; then
            print_warn "The '${dnsmasqd_statics}' file does not exist or is empty"
        else
            if cat "${dnsmasqd_statics}" | __unique_ncns ; then
                return 0
            fi
            print_warn "Unable to obtain ${type_string} list from '${dnsmasqd_statics}'"
        fi
    else
        # Not on a PIT node

        # Loop until node names are found
        while true ; do

            # Try getting node list from basecamp metadata endpoint first
            if curl -s http://ncn-m001:8888/meta-data | jq -r '.Global.host_records[].aliases[1]' | __unique_ncns ; then
                return 0
            fi
            # No warning message is printed in this case, because this is expected to fail once the PIT node is redeployed

            # Try BSS metadata
            if curl -s http://api-gw-service-nmn.local:8888/meta-data | jq -r '.Global.host_records[].aliases[1]' | __unique_ncns ; then
                return 0
            else
                print_warn "Unable to obtain ${type_string} list from BSS"
            fi

            if [[ ! -s /etc/hosts ]]; then
                print_warn "File does not exist or is empty: /etc/hosts"
            else
                if cat /etc/hosts | __unique_ncns ; then
                    return 0
                fi
                print_warn "Unable to obtain ${type_string} list from /etc/hosts"
            fi
            
            echo "${type_string} names could not be found. Sleeping for 30 seconds and retrying" 1>&2
            sleep 30

        done
    fi
    print_error "Unable to obtain ${type_string} list from any source"
    return 1
}

function k8s_local_tests {
    local tmpvars GOSS_VARS

    # create_tmpvars_file creates the temporary variables file and saves the path to it in the ${tmpvars} variable
    create_tmpvars_file || return 1

    export GOSS_VARS=${tmpvars}
    if is_pit_node; then
        # Running on the PIT node -- run the PIT-appropriate suite
        echo "Test Suite: Kubernetes Cluster Checks (on PIT node)"
        /usr/bin/goss -g "${GOSS_BASE}/suites/common-kubernetes-tests-cluster.yaml" v
        echo
    else
        # Not on the PIT node
        echo "Test Suite: Kubernetes Cluster Checks"
        /usr/bin/goss -g "${GOSS_BASE}/suites/ncn-kubernetes-tests-cluster.yaml" v
        echo
    fi
}

function run_ncn_tests {
    local NODE port endpoint
    NODE=$1
    port=$2
    endpoint=$3

    echo
    echo Running tests against node $'\e[1;33m'${NODE}$'\e[0m'
    url="http://${NODE}.hmn:${port}/${endpoint}"

    echo Server URL: ${url}
    #shellcheck disable=SC2006
    if ! results=`curl -s "${url}"` ; then
        echo $'\e[1;31m'ERROR: Server endpoint could not be reached$'\e[0m'
        return 1
    fi

    #shellcheck disable=SC2092
    #shellcheck disable=SC2006
    if ! `echo ${results} | jq -e > /dev/null 2>&1`; then
        echo $'\e[1;31m'ERROR: Output not valid JSON$'\e[0m'
        return 1
    else
        echo ${results} | jq -c '.results | sort_by(.result) | .[]' | while read -r test; do
            result=$(echo ${test} | jq -r '.result')

            if [[ -z ${result} ]]; then
                continue
            elif [[ ${result} == 0 ]]; then
                result=PASS
                echo $'\e[1;32m'
            else
                result=FAIL
                echo $'\e[1;31m'
            fi

            title=$(echo ${test} | jq -r '.title')
            description=$(echo ${test} | jq -r '.meta.desc')
            severity=$(echo ${test} | jq -r '.meta.sev')
            summary=$(echo ${test} | jq -r '."summary-line"')
            time=$(echo ${test} | jq -r '.duration')
            time=$(echo "scale=8; ${time}/1000000000" | bc | awk '{printf "%.8f\n", $0}')

            echo "Result: ${result}"
            echo "Test Name: ${title}"
            echo "Description: ${description}"
            echo "Severity: ${severity}"
            echo "Test Summary: ${summary}"
            echo "Execution Time: ${time} seconds"
            echo "Node: ${NODE}"
        done
    fi

    echo $'\e[0m'

    total=$(echo ${results} | jq -r '.summary."test-count"')
    failed=$(echo ${results} | jq -r '.summary."failed-count"')
    time=$(echo ${results} | jq -r '.summary."total-duration"')
    time=$(echo "scale=4; ${time}/1000000000" | bc | awk '{printf "%.4f\n", $0}')

    echo "Total Tests: ${total}, Total Passed: $((total-failed)), Total Failed: ${failed}, Total Execution Time: ${time} seconds"
    return 0
}

function add_local_vars {
    # $1 - goss variable file
    if [[ $# -ne 1 ]]; then
        print_error "add_local_vars: Function requires exactly 1 argument but received $#: $*"
        return 1
    elif [[ -z $1 ]]; then
        print_error "add_local_vars: Argument may not be blank"
        return 1
    elif [[ ! -e $1 ]]; then
        print_error "add_local_vars: File '$1' does not exist"
        return 1
    elif [[ ! -f $1 ]]; then
        print_error "add_local_vars: '$1' exists but is not a regular file"
        return 1
    fi

    local this_node_name this_node_manufacturer var_string node nodes

    # Add local nodename as variable
    this_node_name=$(hostname -s | grep -Eo '(ncn-[msw][0-9]{3}|.*-pit)$')
    var_string="\n\nthis_node_name: \"${this_node_name}\"\n"
    
    # Add hardware manufacturer as variable
    this_node_manufacturer=$(ipmitool mc info | 
        grep -E "^Manufacturer Name[[:space:]]{1,}:[[:space:]]*[^[:space:]]" |
        sed -e 's/^Manufacturer Name[[:space:]]*:[[:space:]]*//' -e 's/[[:space:]]*$//')
    var_string+="\nthis_node_manufacturer: \"${this_node_manufacturer}\"\n"

    # Get NCN list
    nodes=$(get_ncns)

    # add list of all nodes
    var_string+="\nnodes:\n"
    for node in ${nodes}; do
        var_string+="  - ${node}\n"
    done

    # add list of k8s nodes
    var_string+="\nk8s_nodes:\n"
    for node in $(echo "${nodes}" | grep -oE "ncn-[mw][0-9]{3}") ; do
        var_string+="  - ${node}\n"
    done
    
    # add list of storage nodes
    var_string+="\nstorage_nodes:\n"
    for node in $(echo "${nodes}" | grep -oE "ncn-s[0-9]{3}") ; do
        var_string+="  - ${node}\n"
    done

    echo -e "${var_string}" >> "$1"
    return $?
}

# Sets ${tmpvars} variable to the name of the temporary variable file it creates
function create_tmpvars_file {
    if [[ -z ${GOSS_BASE} ]]; then
        print_error "create_tmpvars_file: GOSS_BASE variable is not set"
        return 1
    elif [[ ! -d ${GOSS_BASE}/vars ]]; then
        print_error "create_tmpvars_file: Directory does not exist: ${GOSS_BASE}/vars"
        return 1
    fi
    
    local base_var_file
    
    if is_pit_node ; then
        base_var_file="${GOSS_BASE}/vars/variables-livecd.yaml"
    else
        base_var_file="${GOSS_BASE}/vars/variables-ncn.yaml"
    fi

    if [[ ! -e ${base_var_file} ]]; then
        print_error "create_tmpvars_file: File does not exist: ${base_var_file}"
        return 1
    elif [[ ! -f ${base_var_file} ]]; then
        print_error "create_tmpvars_file: Not a regular file: ${base_var_file}"
        return 1
    fi

    tmpvars=$(mktemp /tmp/goss-variables-$(date +%s)-XXXXXX-temp.yaml)
    if [[ $? -ne 0 ]]; then
        print_error "create_tmpvars_file: mktemp command failed"
        return 1
    fi

    if ! cp "${base_var_file}" "${tmpvars}" ; then
        print_error "create_tmpvars_file: Command failed: cp '${base_var_file}' '${tmpvars}'"
        return 1
    fi
    
    add_local_vars "${tmpvars}" || return 1
    
    echo "Using Goss variable file: ${tmpvars}"
    return 0
}
