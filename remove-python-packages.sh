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

set -eu

# Usage: remove-python-packages.sh <python-binary> [package1] [package2] ...

# This script is called when building the csm-testing RPM to parse the
# requirements.txt file to find the packages that are inherited from the
# system Python environment, and remove them from the virtual environment
# if they exist.

# Optionally, additional packages may be specified to this script on the
# command line, in which case those too will be removed from the virtual
# environment, if they are present

function err_exit {
    echo "ERROR: $0: $*" >&2
    exit 1
}

common_pip_flags='--no-cache-dir --disable-pip-version-check'

function remove_if_installed {
    [[ $# -eq 1 ]] || err_exit "$0: Function requires exactly 1 argument but received $#: $*"
    echo "Removing $1 if it is installed..."
    if "${PYTHON_BIN}" -m pip show -q ${common_pip_flags} "$1" >/dev/null 2>&1; then
        "${PYTHON_BIN}" -m pip uninstall -y ${common_pip_flags} "$1" || err_exit "Failure trying to remove $1"
    else
        echo "Package $1 is not installed"
    fi
}

if [[ $# -eq 0 ]]; then
    err_exit "No arguments specified"
fi
PYTHON_BIN="$1"
shift

REMOVE_PIP=N

grep_pattern='^#system_python:'

if grep -Eq "${grep_pattern}" requirements.txt; then
    echo "Removing packages specified in requirements.txt"
    for package in $(grep -E '^#system_python:' requirements.txt | cut -d: -f2 | awk '{ print $1 }'); do
        if [[ ${package} == pip ]]; then
            # If asked to remove pip, remember and do it last, since we need it to do the other uninstalls
            REMOVE_PIP=Y
            echo "Delaying removal of pip until last"
            continue
        fi
        remove_if_installed "${package}"
    done
else
    echo "No packages specified in requirements.txt"
fi

if [[ $# -gt 0 ]]; then
    echo "Removing packages specified on the command line"
    for package in "$@"; do        
        if [[ ${package} == pip ]]; then
            # If asked to remove pip, remember and do it last, since we need it to do the other uninstalls
            REMOVE_PIP=Y
            echo "Delaying removal of pip until last"
            continue
        fi
        remove_if_installed "${package}"
    done
else
    echo "No packages specified on the command line"
fi

if [[ ${REMOVE_PIP} == Y ]]; then
    remove_if_installed pip
fi
