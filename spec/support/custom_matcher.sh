#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2022-2023 Hewlett Packard Enterprise Development LP
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

shellspec_syntax 'shellspec_matcher_regexp'

shellspec_matcher_regexp() {
  shellspec_matcher__match() {
    SHELLSPEC_EXPECT="$1"
    [ "${SHELLSPEC_SUBJECT+x}" ] || return 1
    expr "$SHELLSPEC_SUBJECT" : "$SHELLSPEC_EXPECT" > /dev/null || return 1
    return 0
  }

  # Message when the matcher fails with "should"
  shellspec_matcher__failure_message() {
    shellspec_putsn "expected: $1 match $2"
  }

  # Message when the matcher fails with "should not"
  shellspec_matcher__failure_message_when_negated() {
    shellspec_putsn "expected: $1 not match $2"
  }

  # checking for parameter count
  shellspec_syntax_param count [ $# -eq 1 ] || return 0
  shellspec_matcher_do_match "$@"
}


shellspec_syntax 'shellspec_matcher_be_json'
shellspec_matcher_be_json() {
  shellspec_matcher__match() {
    # no args because we match the subject
    [ ${SHELLSPEC_SUBJECT+x} ]
    # check if jq can read the subject
    if ! echo "$SHELLSPEC_SUBJECT" | jq -r > /dev/null;then return 1;fi
    return 0
  }

  shellspec_syntax_failure_message + \
    'expected: valid json' \
    '     got: $1'

  shellspec_syntax_failure_message - \
    'expected: invalid json' \
    '     got: $1'

  shellspec_syntax_param count [ $# -eq 0 ] || return 0
  shellspec_matcher_do_match "$@"
}

shellspec_syntax 'shellspec_matcher_be_yaml'
shellspec_matcher_be_yaml() {
  shellspec_matcher__match() {
    # no args because we match the subject
    [ ${SHELLSPEC_SUBJECT+x} ]
    # check if yq can read the subject
    if ! echo "$SHELLSPEC_SUBJECT" | yq > /dev/null;then return 1;fi
    return 0
  }

  shellspec_syntax_failure_message + \
    'expected: valid yaml' \
    '     got: $1'

  shellspec_syntax_failure_message - \
    'expected: invalid yaml' \
    '     got: $1'

  shellspec_syntax_param count [ $# -eq 0 ] || return 0
  shellspec_matcher_do_match "$@"
}