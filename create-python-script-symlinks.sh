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

set -euo pipefail

source ./common.sh

# Usage: create-python-script-symlinks.sh <path to buildroot>
#                                         <path to Python virtual env>
#                                         <test|tool>
#                                         <target subdir1 in buildroot for symlinks>
#                                        [<target subdir2 in buildroot for symlinks>] ...

function err_exit
{
    echo "$0: ERROR: $*" >&2
    exit 1
}

[[ $# -ge 4 ]] || err_exit "Too few arguments ($#): $*"

buildroot="$1"
venv_path="$2"
script_type="$3"

# Sanity check some of the arguments
[[ ${script_type} == test || ${script_type} == tool ]] || err_exit "Script type argument must be tests or tools. Invalid: $*"
[[ -n ${buildroot} ]] || err_exit "Build root path may not be blank"
[[ -d ${buildroot} ]] || err_exit "Build root path does not exist or is not a directory"
[[ -n ${venv_path} ]] || err_exit "Venv path may not be blank"
[[ -d ${buildroot}${venv_path} ]] || err_exit "Venv path does not exist in buildroot or is not a directory"
[[ -d ${buildroot}${venv_path}/bin ]] || err_exit "Venv path has no bin subdirectory"
[[ -f ${buildroot}${venv_path}/bin/python ]] || err_exit "Venv path has no bin/python file"

shift 3

for target_dir in "$@"; do
    [[ -n ${target_dir} ]] || err_exit "Target subdir may not be blank"
    [[ -d ${buildroot}${target_dir} ]] || err_exit "Target does not exist in buildroot or is not a directory: ${target_dir}"
done

[[ -s pyproject.toml ]] || err_exit "pyproject.toml does not exist or is not a non-empty file"

# SYMLINK_PREFIX and SYMLINK_FS are defined in common.sh
full_pattern="^${SYMLINK_PREFIX}${SYMLINK_FS}${script_type}_"
num_found=0

for source_script_name in $(grep -E "${full_pattern}" pyproject.toml |
                            cut -d"${SYMLINK_FS}" -f2); do
    let num_found+=1
    target_script_name=${source_script_name/${script_type}_/}

    source_script_path="${buildroot}${venv_path}/bin/${source_script_name}"
    [[ -f ${source_script_path} ]] || err_exit "Script does not exist or is not a regular file: ${source_script_path}"
    [[ -x ${source_script_path} ]] || err_exit "Script not executable: ${source_script_path}"   

    for target_dir in "$@"; do
        # Create symbolic link (use -r to have it use relative paths)
        target_script_path="${buildroot}${target_dir}/${target_script_name}"
        ln -rsv "${source_script_path}" "${target_script_path}"
    done
done

if [[ ${num_found} -eq 0 ]]; then
    err_exit "No symlink script lines found in pyproject.toml"
fi
echo "Created symlinks for ${num_found} scripts"
