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

# On failures we will exit with unusual exit codes, to help make it clearer where the test failed

# This test uses command pipelines, so we will set pipefail. That way the pipelines will
# fail (i.e. exit non-0) if any of the commands in the chain fail
set -o pipefail

IFCFG_BOND0=/etc/sysconfig/network/ifcfg-bond0

function err_exit
{
    local rc
    rc=$1
    shift
    echo "ERROR: $*" 1>&2
    exit $rc
}

function usage
{
    echo -e "Usage: check_bond_members_have_correct_mtu.sh <mtu>\n" 1>&2
    err_exit "$@"
}

if [[ $# -eq 0 ]]; then
    usage 10 "MTU must be specified"

elif [[ $# -gt 1 ]]; then
    usage 15 "Only one MTU may be specified. Invalid arguments: $*"

elif [[ -z $1 ]]; then
    usage 20 "MTU may not be blank"

elif ! [[ $1 -gt 0 ]]; then
    usage 25 "MTU must be a positive integer"

elif [[ ! -e $IFCFG_BOND0 ]]; then
    err_exit 30 "$IFCFG_BOND0 does not exist"

elif [[ ! -f $IFCFG_BOND0 ]]; then
    ls -ald $IFCFG_BOND0
    err_exit 35 "$IFCFG_BOND0 exists but is not a regular file"

elif [[ ! -s $IFCFG_BOND0 ]]; then
    err_exit 40 "$IFCFG_BOND0 is an empty file"

fi

expected_mtu=$1
echo "Expected MTU: $expected_mtu"
echo

bond_members=$(awk -F "=" '/BONDING_SLAVE/{print $2}' $IFCFG_BOND0 | tr -d "'") ||
    err_exit 45 "Command failed (rc $?): awk -F \"=\" '/BONDING_SLAVE/{print \$2}' $IFCFG_BOND0"

echo "bond0 members found: "$bond_members

errors=0
count=0
for member in $bond_members ; do
    mtu=$(ip addr show $member | grep mtu | sed 's/^.*mtu \([0-9][0-9]*\) .*$/\1/') ||
        err_exit 50 "Command failed (rc $?): ip addr show $member | grep mtu | sed 's/^.*mtu \([0-9][0-9]*\) .*$/\1/'"
    #shellcheck disable=SC2053
    if [[ $mtu == $expected_mtu ]]; then
        echo "MTU of $member matches expected value"
    else
        echo "ERROR: MTU of $member ($mtu) does NOT match expected value" 1>&2
        let errors+=1
    fi
    let count+=1
done

if [[ $count -eq 0 ]]; then
    echo "ERROR: No bond members found in $IFCFG_BOND0" 1>&2
    let errors+=1
fi

echo
if [[ $errors -eq 0 ]]; then
    echo "PASS"
    exit 0
fi

echo "FAIL"
exit 100
