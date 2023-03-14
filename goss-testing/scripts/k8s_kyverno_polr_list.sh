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

set -o pipefail

print_results=0
while getopts ph stack
do
    case "${stack}" in
          p) print_results=1;;
          h) echo "usage: k8s_kyverno_polr_list.sh           # Only print 'PASS' upon success"
             echo "       k8s_kyverno_polr_list.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
         \?) echo "usage: k8s_kyverno_polr_list.sh           # Only print 'PASS' upon success"
             echo "       k8s_kyverno_polr_list.sh -p        # Print all results and errors if found. Use for manual check."
             exit 3;;
    esac
done

error_flag=0

function check_policy_reports
{
    # Usage: count_policy_reports <type>
    # type: fail, warn, error, skip
    # Counts the total reports of that type. If the total is 0, no output is produced .
    # If the total is above 0, the error_flag global variable is set to 1. If the print_results variable is set to 1, the function
    # will also print an appropriate error message to stdout.
    # Finally, if there are any errors determining the total, then an error message is printed to stderr, and the script is exited.

    local count rc report_type
    report_type=$1
    count=$(kubectl get polr -A -o json | jq "[.items[].summary.${report_type}] | add")
    rc=$?
    if [[ ${rc} -ne 0 ]]
    then
        # Split echo into two commands for code readability
        echo -n "ERROR: Command pipeline failed with return code ${rc}: " 1>&2
        echo "kubectl get polr -A -o json | jq '[.items[].summary.${report_type}] | add'" 1>&2
        echo "FAIL"
        exit 10
    elif [[ ${count} == 0 ]]
    then
        # If there are no such reports, just return.
        return
    elif [[ ${count} =~ ^[1-9][0-9]*$ ]]
    then
        # A non-zero number of reports indicates a problem
        error_flag=1
        if [[ ${print_results} -eq 1 ]]
        then
            echo "ERROR: There are ${count} policy reports in the '${report_type}' category."
            echo "Look into the Kyverno policy management document to address these."
            echo
        fi
        return
    fi
    
    # If this line is reached, then it means that count is either a negative integer, or not an integer at all
    echo "Command pipeline had return code 0: kubectl get polr -A -o json | jq '[.items[].summary.${report_type}] | add'" 1>&2
    echo "ERROR: Command pipeline gave unexpected output: '${count}'" 1>&2
    echo "FAIL"
    exit 20
}    

# Check Kyverno policy reports
for rtype in fail warn error skip
do
    check_policy_reports "${rtype}"
done

if [[ ${error_flag} -eq 0 ]]
then
    echo "PASS"
    exit 0
fi

echo "FAIL"
exit 1
