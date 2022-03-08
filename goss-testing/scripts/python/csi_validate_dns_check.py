#!/usr/bin/env python3
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
import sys, os
import lib.data_json_parser as dp

''' Simple test to validate dns. It mimics the CSI validate check `grep -Eo 'ncn-.*-mgmt'` 
    against data.json global meta-data ntp-peers.
Counts the number of times that the ntp-peer appears in dnsmasq.leases file
matches that to the number of ntp_peers - they should be ==
'''

PASSED = 0
dnsmasq_file = '/var/lib/misc/dnsmasq.leases'

# Assume we got the right info from goss, but JIC
if len(sys.argv) == 2:
    data_json = sys.argv[1].strip('[').strip(']')
else:
    data_json = "/var/www/ephemeral/configs/data.json"

# load the info from dnsmasq.leases
if os.path.isfile(dnsmasq_file):
    f = open(dnsmasq_file, 'r')
    dns_contents = f.read()

dj = dp.dataJson(data_json)
peers = dj.getGlobalMD()["ntp_peers"].split()

# If this machine(ncn-m001) is in data.json global meta-data ntp-peers, remove it
if 'ncn-m001' in peers:
    peers.remove('ncn-m001')

for peer in peers:
    if peer+'-mgmt' in dns_contents:
        PASSED += 1

if PASSED == len(peers):
    print("PASS")
    sys.exit(0)
else:
    print("FAIL")
    sys.exit(1)
