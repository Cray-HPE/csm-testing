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
Simple test to validate dns. It mimics the CSI validate check `grep -Eo 'ncn-.*-mgmt'`
    against data.json global meta-data ntp-peers.
Counts the number of times that the ntp-peer appears in dnsmasq.leases file
matches that to the number of ntp_peers - they should be ==
"""

import os
import sys
import csm_testing.lib.data_json_parser as dp

DNSMASQ_FILE = '/var/lib/misc/dnsmasq.leases'


def main() -> int:  # pylint: disable=missing-function-docstring
    passed = 0

    # Assume we got the right info from goss, but JIC
    if len(sys.argv) == 2:
        data_json = sys.argv[1].strip('[').strip(']')
    else:
        data_json = "/var/www/ephemeral/configs/data.json"

    # load the info from dnsmasq.leases
    if os.path.isfile(DNSMASQ_FILE):
        with open(DNSMASQ_FILE, 'r') as file:
            dns_contents = file.read()

    djson = dp.DataJson(data_json)
    peers = djson.get_global_md()["ntp_peers"].split()

    # If this machine(ncn-m001) is in data.json global meta-data ntp-peers, remove it
    if 'ncn-m001' in peers:
        peers.remove('ncn-m001')

    for peer in peers:
        if peer + '-mgmt' in dns_contents:
            passed += 1

    if passed == len(peers):
        print("PASS")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
