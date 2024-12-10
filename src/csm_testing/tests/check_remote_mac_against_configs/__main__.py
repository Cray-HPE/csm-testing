#
# MIT License
#
# (C) Copyright 2022, 2024 Hewlett Packard Enterprise Development LP
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
"""
Script to check MAC address of remote NCNs against data.json and statics.conf
Invocation: check-remote-mac-against-configs /path/to/data.json /path/to/statics.conf
Check the count of passed tests against the number of NCNs in data.conf - and
send either PASS or FAIL
"""

import logging
import sys
import csm_testing.lib.data_json_parser as djp
from csm_testing.lib.run_remote_command import run_remote_command

GET_MAC_COMMAND = "ip addr show dev bond0 | grep 'link/ether' | tr -s ' ' | cut -d ' ' -f 3"


def get_arg_no_brackets(arg: str) -> str:
    """
    Strip leading [ and trailing ] from the string and return it
    """
    return arg.strip('[').strip(']')


def do_test(data_json_path: str, statics_conf_path: str) -> bool:
    """
    Return True if test passed.
    Return False otherwise.
    """
    passed = 0
    data = djp.DataJson(data_json_path)
    with open(statics_conf_path, 'r') as statics_file:
        statics = statics_file.read()

    # ensure remote MAC matches data.json (casminst-384) and statics.conf (casminst-380)
    for server, server_mac in data.ncn_list.items():
        # get the MAC from the NCN
        mac = run_remote_command(server, GET_MAC_COMMAND).decode().strip()

        # ensure that the MAC address is somewhere in data.json
        if mac in data.ncn_keys:
            # ensure that the hostname's MAC in data.json matches reality
            if server_mac == mac:
                passed += 1

        # ensure that the mac exists in statics.conf
        if mac in statics:
            # check statics.conf
            # should find something like: dhcp-host=b8:59:9f:2b:2e:d2,10.252.0.7,ncn-s001,infinite
            # the ip is between the first commas
            try:
                start_index = statics.find('dhcp-host=' + server_mac)
                end_index = statics.find(
                    '\n', statics.find('dhcp-host=' + server_mac))
                search = statics[start_index:end_index]
                _, hname = search[search.find(','):search.rfind(',')].split(
                    ',')[-2:]
                if mac == data.ncn_list[hname]:
                    passed += 1
            except KeyError:
                print("Error in statics.conf")

    # There are two tests per ncn, so the number of tests passed should == number of keys * 2
    return passed == len(data.ncn_keys) * 2


def main() -> int:  # pylint: disable=missing-function-docstring
    # setup logging
    logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',
                        level=logging.DEBUG)
    logging.info("Starting up")

    # quick check to ensure we received the locations of data.json and statics.conf
    if len(sys.argv) != 3:
        print("Wrong number of arguments provided")
        return 2

    # This version of goss sends [.Arg.*] as string with [
    # Apparently fixed in 0.3.14
    data_json_path = get_arg_no_brackets(sys.argv[1])
    statics_conf_path = get_arg_no_brackets(sys.argv[2])

    if do_test(data_json_path, statics_conf_path):
        print("PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
