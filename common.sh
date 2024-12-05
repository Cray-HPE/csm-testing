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

# No shebang line included in this file because it is only intended to be sourced, never
# directly executed. But to let shellcheck know:
# shellcheck shell=bash

# Shared definitions for Bash scripts used in the build process

# We know these variables are not used in this script -- they are defined to be used by scripts which source this one
#shellcheck disable=SC2034
SYMLINK_PREFIX="#python-script-symlink"

# The field separator needs to be a character that does not have a special meaning for regular expressions
# (e.g. do not use '|')
#shellcheck disable=SC2034
SYMLINK_FS=","

function err_exit
{
    echo "$0: ERROR: $*" >&2
    exit 1
}
