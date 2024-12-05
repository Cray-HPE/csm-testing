#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP
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

set -exuo pipefail

# This updates 'pylint-requirements.txt', adding in some of the system Python requirements
# from requirements.txt. Specifically, we include all of them except rados, since we
# are not going to be able to install it for our pylint run

source ./common.sh

SRCFILE=requirements.txt
TRGFILE=pylint-requirements.txt

[[ -e ${SRCFILE} ]] || err_exit "${SRCFILE} does not exist"
[[ -f ${SRCFILE} ]] || err_exit "${SRCFILE} exists but is not a regular file"
[[ -s ${SRCFILE} ]] || err_exit "${SRCFILE} exists but is zero size"

SYS_PY_REGEX='^#system_python:'
SYS_RADOS_REGEX='^#system_python:rados[[:space:]]*$'

if ! grep -Eq "${SYS_PY_REGEX}" "${SRCFILE}" ; then
    echo "No system_python lines found in '${SRCFILE}' -> no updates necessary to '${TRGFILE}'"
    exit 0
fi

if ! grep -E "${SYS_PY_REGEX}" "${SRCFILE}" | grep -Eqv "${SYS_RADOS_REGEX}" ; then
    echo "No system_python lines other than rados found in '${SRCFILE}' -> no updates necessary to '${TRGFILE}'"
    exit 0
fi

tmpfile=$(mktemp) || err_exit "Failed to create temporary file"

grep -E "${SYS_PY_REGEX}" "${SRCFILE}" | grep -Ev "${SYS_RADOS_REGEX}" | sed "s/${SYS_PY_REGEX}//" > "${tmpfile}" || err_exit "Error creating '${tmpfile}'"

echo "Appending following lines to '${TRGFILE}'"
cat "${tmpfile}" | tee -a "${TRGFILE}"
rm -v "${tmpfile}"
