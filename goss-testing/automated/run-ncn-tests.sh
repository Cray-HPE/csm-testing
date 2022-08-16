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

# No shebang line at the top of the file, because this is not intended to be executed, only included as a source in other Bash scripts.
# The following line lets the linter know how to appropriately check this file.
# shellcheck shell=bash

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

# Set some default variables here, both because we use them in this library, and also to save
# scripts from having to set them if they source this library.
if [[ -z ${GOSS_BASE} ]]; then
    GOSS_INSTALL_BASE_DIR=${GOSS_INSTALL_BASE_DIR:-"/opt/cray/tests/install"}

    if is_pit_node ; then
        GOSS_BASE="${GOSS_INSTALL_BASE_DIR}/livecd"
    else
        GOSS_BASE="${GOSS_INSTALL_BASE_DIR}/ncn"
    fi
else
    # If GOSS_BASE is set, then the default value for GOSS_INSTALL_BASE_DIR will
    # be the parent directory of GOSS_BASE
    GOSS_INSTALL_BASE_DIR=${GOSS_INSTALL_BASE_DIR:-$(dirname "${GOSS_BASE}")}
fi
export GOSS_BASE=${GOSS_BASE}
export GOSS_INSTALL_BASE_DIR=${GOSS_INSTALL_BASE_DIR}

export GOSS_LOG_BASE_DIR=${GOSS_LOG_BASE_DIR:-"${GOSS_INSTALL_BASE_DIR}/logs"}

# These do not need to be exported -- they are only used by the functions in this file, or
# by files sourcing this file.
GOSS_SERVERS_CONFIG=${GOSS_SERVERS_CONFIG:-"${GOSS_INSTALL_BASE_DIR}/dat/goss-servers.cfg"}

# Pattern to match 100-999: [1-9][0-9][0-9]
# Pattern to match 010-099: 0[1-9][0-9]
# Pattern to match 001-009: 00[1-9]
ncn_num_pattern="([1-9][0-9][0-9]|0[1-9][0-9]|00[1-9])"

function sw_admin_pw_set {
    if [[ -z ${SW_ADMIN_PASSWORD} ]]; then
        print_error "Management switch 'admin' user password must be provided via the SW_ADMIN_PASSWORD environment variable"
        echo "Example: export SW_ADMIN_PASSWORD='changeme'"
        return 1
    fi
    return 0
}

function SSHPASS {
    if [[ -z ${SSHPASS} ]]; then
        print_error "Management switch 'admin' user password must be provided via the SSHPASS environment variable"
        echo "Example: export SSHPASS='changeme'"
        return 1
    fi
    return 0
}

function is_nonempty_file {
    if [[ $# -ne 1 ]]; then
        print_error "regular_file_exists: Function requires exactly 1 argument but received $#: $*"
        return 1
    elif [[ -z $1 ]]; then
        print_error "Filepath is blank"
        return 1
    elif [[ ! -e $1 ]]; then
        print_error "File does not exist: $1"
        return 1
    elif [[ ! -f $1 ]]; then
        print_error "Not a regular file: $1"
        return 1
    elif [[ ! -s $1 ]]; then
        print_error "File is empty: $1"
        return 1
    fi
    return 0
}

function is_master_node {
    is_pit_node && return 1
    [[ $(hostname -s) =~ ^.*ncn-m${ncn_num_pattern}.*$ ]]
    return $?
}

function is_worker_node {
    [[ $(hostname -s) =~ ^.*ncn-w${ncn_num_pattern}.*$ ]]
    return $?
}
function is_storage_node {
    [[ $(hostname -s) =~ ^.*ncn-s${ncn_num_pattern}.*$ ]]
    return $?
}

function node_type {
    is_pit_node     && echo "pit"     && return 0
    is_master_node  && echo "master"  && return 0
    is_worker_node  && echo "worker"  && return 0
    is_storage_node && echo "storage" && return 0
    print_warn "Unknown node type"
    echo "unknown"
    return 1
}

# Prints a list of all NCNs
# Prints warnings if there are fewer than expected
#
# Disable the following check because this function does get called with arguments, just
# not from within this file.
#shellcheck disable=SC2120
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
    local type_char_pattern type_string

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
            *) err_exit "PROGRAMMING LOGIC ERROR: get_ncns: Invalid argument: '$1'"
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

# Some Python script wrappers -- they transparently pass their arguments into the scripts, and return the script's return code
function goss_endpoint_urls {
    "${GOSS_BASE}/automated/python/goss_suite_urls.py" "$@"
    return $?
}

function print_goss_json_results {
    "${GOSS_BASE}/automated/python/print_goss_json_results.py" "$@"
    return $?
}

function goss_suites_endpoints_ports {
    "${GOSS_BASE}/automated/python/goss_suites_endpoints_ports.py" "$@"
    return $?
}

function get_ready_k8s_node
{
    # Usage: get_ready_k8s_node [ncn1] [ncn2] ...
    # Runs kubectl get nodes and prints the name of the first master or worker node that is Ready.
    # If nodes are passed in as arguments, it will only look at those nodes.

    local node node_pattern node_list
    if [[ $# -eq 0 ]]; then
        node_list=""
        node_pattern="ncn-[mw]${ncn_num_pattern}"
    else
        node_list="$*"
        if [[ $# -eq 1 ]]; then
            node_pattern="$1"
        else
            node_pattern="($1"
            shift
            while [[ $# -gt 0 ]]; do
                node_pattern+="|$1"
                shift
            done
            node_pattern+=")"
        fi
    fi
    node=$(kubectl get nodes --no-headers "$@" 2>/dev/null | 
            grep -E "^${node_pattern}[[:space:]]{1,}Ready[[:space:]]" |
            awk '{ print $1 }' | head -1)
    [[ -n ${node} ]] && echo "${node}" && return 0
    if [[ -n ${node_list} ]]; then
        print_error "None of the following Kubernetes nodes is Ready, according to kubectl: ${node_list}"
    else
        print_error "No master or worker NCNs are Ready, according to kubectl"
    fi
    return 1
}

function healthcheck_urls_for_master_nodelist
{
    # Usage: healthcheck_urls_for_master_nodelist <node1> [<node2>] ...
    local suite after_pit_suite urls more_urls ready_node single_suite
    if [[ $# -eq 0 ]]; then
        print_error "healthcheck_urls_for_master_nodelist: Function requires at least 1 argument"
        return 1
    fi

    suite="ncn-healthcheck-master.yaml"
    single_suite="ncn-healthcheck-master-single.yaml"
    after_pit_suite="ncn-afterpitreboot-healthcheck-master.yaml"

    ready_node=$(get_ready_k8s_node "$@") || return 1

    if ! urls=$(goss_endpoint_urls "${suite}" "$@") ; then
        print_error "Error finding test URLs for ${suite} on $*"
        return 1
    fi

    if ! more_urls=$(goss_endpoint_urls "${single_suite}" "${ready_node}") ; then
        print_error "Error finding test URL for ${single_suite} on ${ready_node}"
        return 1
    fi
    urls+=" ${more_urls}"

    if ! is_pit_node ; then
        if ! more_urls=$(goss_endpoint_urls "${after_pit_suite}" "$@") ; then
            print_error "Error finding test URLs for ${after_pit_suite} on $*"
            return 1
        fi
        urls+=" ${more_urls}"
    fi

    echo ${urls}
    return 0
}    

function healthcheck_urls_for_storage_nodelist
{
    # Usage: healthcheck_urls_for_storage_nodelist <node1> [<node2>] ...
    local suite after_pit_suite urls more_urls
    if [[ $# -eq 0 ]]; then
        print_error "healthcheck_urls_for_storage_nodelist: Function requires at least 1 argument"
        return 1
    fi
    
    suite="ncn-healthcheck-storage.yaml"
    after_pit_suite="ncn-afterpitreboot-healthcheck-storage.yaml"

    if ! urls=$(goss_endpoint_urls "${suite}" "$@") ; then
        print_error "Error finding test URLs for ${suite} on $*"
        return 1
    fi

    if ! is_pit_node ; then
        if ! more_urls=$(goss_endpoint_urls "${after_pit_suite}" "$@") ; then
            print_error "Error finding test URLs for ${after_pit_suite} on $*"
            return 1
        fi
        urls+=" ${more_urls}"
    fi

    echo ${urls}
    return 0
}    

function healthcheck_urls_for_worker_nodelist
{
    # Usage: healthcheck_urls_for_worker_nodelist <node1> [<node2>] ...
    local suite after_pit_suite urls more_urls ready_node single_suite after_pit_single_suite
    if [[ $# -eq 0 ]]; then
        print_error "healthcheck_urls_for_worker_nodelist: Function requires at least 1 argument"
        return 1
    fi
    
    suite="ncn-healthcheck-worker.yaml"
    single_suite="ncn-healthcheck-worker-single.yaml"
    after_pit_suite="ncn-afterpitreboot-healthcheck-worker.yaml"
    after_pit_single_suite="ncn-afterpitreboot-healthcheck-worker-single.yaml"

    ready_node=$(get_ready_k8s_node "$@") || return 1

    if ! urls=$(goss_endpoint_urls "${suite}" "$@") ; then
        print_error "Error finding test URLs for ${suite} on $*"
        return 1
    fi

    if ! more_urls=$(goss_endpoint_urls "${single_suite}" "${ready_node}") ; then
        print_error "Error finding test URL for ${single_suite} on ${ready_node}"
        return 1
    fi
    urls+=" ${more_urls}"

    if ! is_pit_node ; then
        if ! more_urls=$(goss_endpoint_urls "${after_pit_suite}" "$@") ; then
            print_error "Error finding test URLs for ${after_pit_suite} on $*"
            return 1
        fi
        urls+=" ${more_urls}"

        if ! more_urls=$(goss_endpoint_urls "${after_pit_single_suite}" "${ready_node}") ; then
            print_error "Error finding test URL for ${after_pit_single_suite} on ${ready_node}"
            return 1
        fi
        urls+=" ${more_urls}"
    fi

    echo ${urls}
    return 0
}

function k8s_check_urls_for_master_nodelist {
    # Usage: k8s_check_urls_for_master_nodelist <node1> [<node2>] ...
    local suite after_pit_suite urls more_urls ready_node single_suite after_pit_single_suite
    if [[ $# -eq 0 ]]; then
        print_error "k8s_check_urls_for_master_nodelist: Function requires at least 1 argument"
        return 1
    fi
    
    suite="ncn-kubernetes-tests-master.yaml"
    single_suite="ncn-kubernetes-tests-master-single.yaml"
    after_pit_single_suite="ncn-afterpitreboot-kubernetes-tests-master-single.yaml"

    ready_node=$(get_ready_k8s_node "$@") || return 1

    if ! urls=$(goss_endpoint_urls "${suite}" "$@") ; then
        print_error "Error finding test URLs for ${suite} on $*"
        return 1
    fi

    if ! more_urls=$(goss_endpoint_urls "${single_suite}" "${ready_node}") ; then
        print_error "Error finding test URL for ${single_suite} on ${ready_node}"
        return 1
    fi
    urls+=" ${more_urls}"

    if ! is_pit_node ; then
        if ! more_urls=$(goss_endpoint_urls "${after_pit_single_suite}" "${ready_node}") ; then
            print_error "Error finding test URL for ${after_pit_single_suite} on ${ready_node}"
            return 1
        fi
        urls+=" ${more_urls}"
    fi

    echo ${urls}
    return 0
}

function k8s_check_urls_for_worker_nodelist {
    # Usage: k8s_check_urls_for_worker_nodelist <node1> [<node2>] ...
    local suite after_pit_suite urls more_urls ready_node single_suite after_pit_single_suite
    if [[ $# -eq 0 ]]; then
        print_error "k8s_check_urls_for_worker_nodelist: Function requires at least 1 argument"
        return 1
    fi
    
    suite="ncn-kubernetes-tests-worker.yaml"
    after_pit_single_suite="ncn-afterpitreboot-kubernetes-tests-worker-single.yaml"

    if ! urls=$(goss_endpoint_urls "${suite}" "$@") ; then
        print_error "Error finding test URLs for ${suite} on $*"
        return 1
    fi

    if ! is_pit_node ; then
        ready_node=$(get_ready_k8s_node "$@") || return 1

        if ! more_urls=$(goss_endpoint_urls "${after_pit_single_suite}" "${ready_node}") ; then
            print_error "Error finding test URL for ${after_pit_single_suite} on ${ready_node}"
            return 1
        fi
        urls+=" ${more_urls}"
    fi

    echo ${urls}
    return 0
}

function ncn_healthcheck_master_urls {
    local nodes
    nodes=$(get_ncns --masters --exclude-pit) || return 1
    healthcheck_urls_for_master_nodelist ${nodes}
    return $?
}

function ncn_healthcheck_storage_urls {
    local nodes
    nodes=$(get_ncns --storage) || return 1
    healthcheck_urls_for_storage_nodelist ${nodes}
    return $?
}

function ncn_healthcheck_worker_urls {
    local nodes
    nodes=$(get_ncns --workers) || return 1
    healthcheck_urls_for_worker_nodelist ${nodes}
    return $?
}

function run_goss_tests {
    # $1 tests/<whatever.yaml> or suites/<whatever.yaml>
    # $2+ additional arguments to goss validate (most often --format <blah>)
    # Creates a temporary variables file and then 
    # calls goss -g "${GOSS_BASE}/$1" --vars "${tmpvars}" v $2
    
    local tmpvars gossfile
    tmpvars=$(create_goss_variable_file) || return 1
    
    if [[ $# -eq 0 ]]; then
        print_error "run_goss_tests: Function requires at least 1 argument"
        return 1
    elif [[ $1 != tests/*.yaml && $1 != suites/*.yaml ]]; then
        print_error "run_goss_tests: First argument must be tests/<file>.yaml or suites/<file>.yaml. Invalid argument: $1"
        return 1
    fi
    gossfile="${GOSS_BASE}/$1"
    if ! is_nonempty_file "${gossfile}" ; then
        print_error "run_goss_tests: Invalid Goss test/suite file"
        return 1
    fi
    shift

    /usr/bin/goss -g "${gossfile}" --vars "${tmpvars}" v "$@"
    return $?
}

function run_goss_tests_print_results {
    # $1 - tests/<whatever.yaml> or suites/<whatever.yaml>
    # $2+ optional Goss URL endpoints to test
    local test_or_suite
    if [[ $# -eq 0 ]]; then
        print_error "run_goss_tests_print_results: Function requires at least one argument"
        return 1
    fi
    test_or_suite="$1"
    shift
    run_goss_tests "${test_or_suite}" --format json | print_goss_json_results "stdin:${test_or_suite}" "$@"
    return $?
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

# Creates Goss variable file and prints path to it
function create_goss_variable_file {
    if [[ -z ${GOSS_BASE} ]]; then
        print_error "create_goss_variable_file: GOSS_BASE variable is not set"
        return 1
    elif [[ ! -d ${GOSS_BASE}/vars ]]; then
        print_error "create_goss_variable_file: Directory does not exist: ${GOSS_BASE}/vars"
        return 1
    fi
    
    local base_var_file tmpvars
    
    if is_pit_node ; then
        base_var_file="${GOSS_BASE}/vars/variables-livecd.yaml"
    else
        base_var_file="${GOSS_BASE}/vars/variables-ncn.yaml"
    fi

    if [[ ! -e ${base_var_file} ]]; then
        print_error "create_goss_variable_file: File does not exist: ${base_var_file}"
        return 1
    elif [[ ! -f ${base_var_file} ]]; then
        print_error "create_goss_variable_file: Not a regular file: ${base_var_file}"
        return 1
    fi

    tmpvars=$(mktemp "/tmp/goss-variables-$(date +%s)-XXXXXX-temp.yaml")
    if [[ $? -ne 0 ]]; then
        print_error "create_goss_variable_file: mktemp command failed"
        return 1
    fi

    if ! cp "${base_var_file}" "${tmpvars}" ; then
        print_error "create_goss_variable_file: Command failed: cp '${base_var_file}' '${tmpvars}'"
        return 1
    fi
    
    add_local_vars "${tmpvars}" || return 1
    
    echo "${tmpvars}"
    return 0
}
