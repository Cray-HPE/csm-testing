#!/usr/bin/env bash
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP.
#
# MIT License
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

GOSS_LOG_BASE_DIR="${GOSS_LOG_BASE_DIR:-/opt/cray/tests/install/logs}"

# Usage: log_run.sh [--label <test-label>] [--no-args] [--no-stderr] [--no-stdout]
#                   <executable> [arg1] [arg2] ...
#
# Wrapper script to call an executable and log its output and exit code, while
# transparently passing through the output (both stdout and stderr) and exit code
# to the calling process.
#
# Uses environment variable GOSS_LOG_BASE_DIR (see default above).
#
#
# The log file contents are (in order):
# * A list of flags that log_run.sh was called with
# * The executable to be called, and its arguments
# * The timestamp when the executable is called
# * The output of the executable (both stdout and stderr)
# * The return code from the executable and the timestamp when the executable completed
#
# The flags to the command change the above default behavior as follows:
#
# --label <label>       Specifies the test label, which is used in determining the log directory.
#                       Defaults to "unlabeled" if not specified. If the -l argument is passed multiple
#                       times, only the final one will be used. Label may not be blank and must begin
#                       with an alphanumeric character.
# -l <label>            Same as --label <label>
#
# --no-args             The arguments to the executable will not be recorded in the log.
#                       (ideally sensitive information should not be passed in plaintext on the
#                       command line in a test, but in case it is, this gives the test the option
#                       to avoid haivng it included in the log file).
#
# --no-stderr           stderr from the executable will not be recorded in the log.
#                       In a case where the executable stderr output contains sensitive information,
#                       this prevents it from being written into the log file.
#
# --no-stdout           stdout from the executable will not be recorded in the log.
#                       Same as the previous argument, except stdout instead of stderr.
#
#
# # The log file created will be ${GOSS_LOG_BASE_DIR}/<test-label>/YYYYMMDD_hhmmss_sssssssss_PID.log

LOGRUN_START=$(date +%Y%m%d_%H%M%S_%N)
LOG_ARGS=Y
LOG_STDERR=Y
LOG_STDOUT=Y

EXE_FILE=""
GOSS_TEST_LABEL="unlabeled"

MY_ARGLIST=()
EXE_ARGLIST=()

function err_exit
{
    echo "ERROR: $*" 1>&2
    exit 57
}

function parse_args
{
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -l|--label)
                [[ $# -lt 2 ]] && err_exit "No argument specified with -l"
                # Append this to the script argument list (to be recorded in the log file)
                MY_ARGLIST+=( "$1" )
                shift
                [[ -z $1 ]] && err_exit "Test label may not be blank"
                [[ $1 == [a-zA-Z0-9]* ]] || err_exit "Test label must begin with an alphanumeric character"
                GOSS_TEST_LABEL="$1"
                ;;
            --no-args)
                LOG_ARGS=N ;;
            --no-stderr)
                LOG_STDERR=N ;;
            --no-stdout)
                LOG_STDOUT=N ;;
            --*)
                err_exit "Unrecognized argument: $1" ;;
            *)
                # This means we have reached the executable
                [[ -z $1 ]] && err_exit "Executable argument may not be blank"
                EXE_FILE="$1"
                shift
                # The remaining arguments (if any) are arguments to the executable
                EXE_ARGLIST=("$@")
                return
                ;;
        esac
        # Append this to the script argument list (to be recorded in the log file)
        MY_ARGLIST+=( "$1" )
        shift
    done
    # We only get here if we run out of arguments before reaching the executable argument
    err_exit "Executable must be specified"
}

function init_log
{
    LOG_DIR="${GOSS_LOG_BASE_DIR}/${GOSS_TEST_LABEL}"
    # mkdir -p will pass even if the directory already exists
    if mkdir -p "$LOG_DIR" >/dev/null 2>&1 && [[ -d $LOG_DIR ]]; then
        LOG_FILE="${LOG_DIR}/${LOGRUN_START}_$$.log"
        # We pipe to tee so that we can suppress errors that may
        # occur from writing to the log file
        echo "log_run argument(s): ${MY_ARGLIST[*]}" | tee "$LOG_FILE" >/dev/null 2>&1
        [[ $? -eq 0 ]] && [[ -f $LOG_FILE ]] && [[ -s $LOG_FILE ]] && return
    fi
    
    # If something goes wrong, we will just redirect log output to /dev/null
    LOG_FILE=/dev/null
}

# The output of this file will be redirected into the log file
function print_log_intro
{
    local arg
    echo "Executable: '${EXE_FILE}'"
    if [[ ${LOG_ARGS} == Y ]]; then
        if [[ ${#EXE_ARGLIST[@]} -eq 0 ]]; then
            echo "No arguments to executable"
        else
            printf "${#EXE_ARGLIST[@]} argument(s) to executable:"
            for arg in "${EXE_ARGLIST[@]}" ; do
                printf " '$arg'"
            done
            echo
        fi
    else
        echo "Argument(s) to executable suppressed in log by --no-args"
    fi
}

parse_args "$@"
init_log

# We pipe to tee so that we can suppress errors that may occur from writing to the log file.
print_log_intro | tee -a $LOG_FILE >/dev/null 2>&1

# Save current stdout to fd 3 and current stderr to fd 4
exec 3>&1
exec 4>&2

if [[ "$LOG_STDOUT" == Y ]]; then
    # Use process substitution to redirect stdout and tee it to the log file
    # And redirect the output of the tee command back to our original stdout
    exec > >( tee -a "$LOG_FILE" >&3 )
else
    # We pipe to tee so that we can suppress errors that may occur from writing to the log file.
    echo "stdout from executable will be suppressed in log by --no-stdout" | tee -a "$LOG_FILE"  >/dev/null 2>&1
fi

if [[ "$LOG_STDERR" == Y ]]; then
    # Use process substitution to redirect stderr and tee it to the log file
    # And redirect the output of the tee command back to our original stderr
    exec 2> >( tee -a "$LOG_FILE" >&4 )
else
    # We pipe to tee so that we can suppress errors that may occur from writing to the log file.
    echo "stderr from executable will be suppressed in log by --no-stderr" | tee -a "$LOG_FILE"  >/dev/null 2>&1
fi

# We pipe to tee so that we can suppress errors that may occur from writing to the log file.
printf "
## $(date +%Y%m%d_%H%M%S_%N) ##  %39s ##
###########################################################################
" "executable starting" | tee -a "$LOG_FILE"  >/dev/null 2>&1

"${EXE_FILE}" "${EXE_ARGLIST[@]}"
rc=$?

printf "\
###########################################################################
## $(date +%Y%m%d_%H%M%S_%N) ##  %39s ##
" "executable completed (exit code=$rc)" | tee -a "$LOG_FILE"  >/dev/null 2>&1

# Exit with exit code of the executable
exit $rc
