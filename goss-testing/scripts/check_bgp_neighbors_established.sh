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

TMPFILE=/tmp/check_bgp_neighbors_established.$$.$RANDOM.tmp

function cleanup
{
    if [[ -f $TMPFILE ]]; then
        rm -f $TMPFILE || echo "WARNING: Unable to remove temporary file $TMPFILE" 1>&2
    fi
}

function err_exit
{
    local rc
    rc=$1
    shift
    echo "ERROR: $*" 1>&2
    cleanup
    echo "FAIL"
    exit $rc
}

kubectl -n metallb-system get cm metallb -o jsonpath='{.data.config}' > $TMPFILE ||
    err_exit 10 "ERROR: Command failed (rc=$?): kubectl -n metallb-system get cm metallb -o jsonpath='{.data.config}' > $TMPFILE"

# We really shouldn't be passing a password in plaintext on the command line, but as long as we are, at least
# we won't also include it in the error message on failure
if grep -q customer-management $TMPFILE ; then
    echo "Running: canu validate network bgp --network all --password XXXXXXXX"
    canu validate network bgp --network all --password {{.Env.SW_ADMIN_PASSWORD}} ||
        err_exit 20 "canu validate network bgp --network all failed (rc=$?)"
else
    echo "Running: canu validate network bgp --network nmn --password XXXXXXXX"
    canu validate network bgp --network nmn --password {{.Env.SW_ADMIN_PASSWORD}} ||
        err_exit 30 "canu validate network bgp --network nmn failed (rc=$?)"
fi
echo "PASS"
cleanup
exit 0
