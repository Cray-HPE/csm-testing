#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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

#
# This script validates that the following things are true:
# - The /proc/cmdline file exists and contains the parameter xname=<valid-looking xname>
# - The file /etc/cray/xname exists and contains that same xname
#
# The script will also print the contnets of both files to stdout.
#
# In the case that any of the above things are not true, the script will print
# appropriate error messages to stderr and exit with a 1 return code. If an unexpected
# error occurs unrelated to the above, the script will print an appropriate error message
# to stderr and return with a return code other than 0 or 1. Otherwise,
# it will report success to stdout and exit with a 0 return code.
#

#
# NCN xnames should be in the following format:
# xXcCsSbBnN
# where:
# X - 0-9999
# C - 0-7
# S - 0-64
# B - 0-1
# N - 0-7
# source: docs-csm: operations/Component_Names_xnames.md
#
# grep regular expressions used to match each of these pieces:
xre="x([0-9]|[1-9][0-9]{0,3})"
cre="c[0-7]"
sre="s([0-9]|[1-5][0-9]|6[0-4])"
bre="b[01]"
nre="n[0-7]"
xname_regex="${xre}${cre}${sre}${bre}${nre}"

RC=0
function err
{
    echo "ERROR: $*" 1>&2
    RC=1
}

function run_cmd
{
    local cmdrc
    echo "# $*"
    "$@"
    cmdrc=$?
    echo "(return code=$cmdrc)"
    return $cmdrc
}

function file_exists_show_contents
{
    local funcrc=1
    if [[ $# -ne 1 ]]; then
        err "PROGRAMMING LOGIC: $FUNCNAME requires exactly 1 argument, but received $#: $*"
        exit 2
    elif [[ -z "$1" ]]; then
        err "PROGRAMMING LOGIC: Argument to $FUNCNAME may not be blank"
        exit 3
    elif [[ ! -e "$1" ]]; then
        err "File '$1' does not exist"
    elif ! run_cmd ls -ald "$1" ; then
        err "Command failed: ls -ald $1"
    elif [[ ! -f "$1" ]]; then
        err "File '$1' exists but is not a regular file"
    elif ! run_cmd cat "$1" ; then
        err "Command failed: cat $1"
    else
        funcrc=0
    fi
    return $funcrc
}

echo "Checking /proc/cmdline"
if file_exists_show_contents /proc/cmdline ; then
    # Extract the xname from the file, if it is present
    if ! PROC_CMDLINE_XNAME_PARAM=$(grep -Eo "[[:space:]]xname=[^[:space:]]+([[:space:]]|$)" /proc/cmdline) ; then
        err "No xname parameter found in /proc/cmdline"
    else
        # We omit the space after the colon because we know the variable will begin with a whitespace
        echo "xname parameter found in /proc/cmdline:${PROC_CMDLINE_XNAME_PARAM}"
        if ! PROC_CMDLINE_XNAME=$(echo $PROC_CMDLINE_XNAME_PARAM | 
                                    # Strip away the leading "xname="
                                    sed 's/^xname=//' | 
                                    # And grep to verify that the xname matches our expected pattern
                                    grep -E "^${xname_regex}$")
        then
            # We omit the space after the colon because we know the variable will begin with a whitespace
            err "xname parameter in /proc/cmdline not in expected format:${PROC_CMDLINE_XNAME_PARAM}"
        else
            echo "xname in /proc/cmdline is in expected format: ${PROC_CMDLINE_XNAME}"
        fi
    fi
fi

echo

echo "Checking /etc/cray/xname"
if file_exists_show_contents /etc/cray/xname ; then
    if ! ETC_CRAY_XNAME=$(cat /etc/cray/xname); then
        err "Command failed when run a second time: cat /etc/cray/xname"
    else
        echo "String found in /etc/cray/xname = '${ETC_CRAY_XNAME}'"
        if ! echo "${ETC_CRAY_XNAME}" | grep -Eq "^${xname_regex}$" ; then
            err "String from /etc/cray/xname not in expected xname format: ${ETC_CRAY_XNAME}"
        elif [[ -n ${PROC_CMDLINE_XNAME} ]]; then
            if [[ ${PROC_CMDLINE_XNAME} != ${ETC_CRAY_XNAME} ]]; then
                err "xname from /proc/cmdline (${PROC_CMDLINE_XNAME}) does NOT MATCH xname from /etc/cray/xname (${ETC_CRAY_XNAME})"
            else
                echo "xname from /proc/cmdline (${PROC_CMDLINE_XNAME}) matches xname from /etc/cray/xname (${ETC_CRAY_XNAME})"
            fi
        fi
    fi
fi

echo

if [[ $RC -eq 0 ]]; then
    echo "SUCCESS"
else
    echo "FAILED: One or more errors found" 1>&2
fi
exit $RC
