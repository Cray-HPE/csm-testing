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

tmpfile=$(mktemp)

source ./common.sh

function addline {
    # Usage: <script_prefix> <mainfile-path>
    local prefix mainfile dirpath subdir script_name script_target
    [[ $# -eq 2 ]]
    [[ -n $1 ]]
    [[ -n $2 ]]
    [[ -f $2 ]]
    prefix="$1"
    mainfile="$2"

    dirpath=$(dirname "${mainfile}")
    subdir=$(basename "${dirpath}")

    # the name of the script is the name of the subdirectory, prepended with prefix_
    script_name="${prefix}_${subdir}"

    # Script target is dirpath with / replaced by ., appended with .__main__:main
    script_target=${dirpath//\//.}.__main__:main

    {
        echo "${script_name} = \"${script_target}\""
        # Also add a comment line, which will be used as input by the create-python-script-symlinks.sh script
        # SYMLINK_PREFIX and SYMLINK_FS are defined in common.sh
        echo "${SYMLINK_PREFIX}${SYMLINK_FS}${script_name}"
    }  >> "${tmpfile}"
}

pushd src

for mainfile in csm_testing/tests/*/__main__.py ; do
    addline test "${mainfile}"
done

for mainfile in csm_testing/tools/*/__main__.py ; do
    addline tool "${mainfile}"
done

popd # Leave src subdirectory

# Update the pyproject.toml file with these new lines, and update its version string
sed -i -e "/\[project\.scripts\]/r ${tmpfile}" \
       -e "s#^version = '0[.]0[.]57'#version = '${SIMPLE_VERSION}'#" \
       pyproject.toml

cat pyproject.toml

rm "${tmpfile}"
