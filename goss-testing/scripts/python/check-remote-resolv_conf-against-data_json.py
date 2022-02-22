#! /usr/bin/env python3

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

# Script to check remote resolv.conf namserver value == dns-server value in data.json
# Invocation: check-remote-resolv_conf-against-data_json.py /path/to/data.json
# Check the count of passed tests against the number of NCNs in data.conf - and send either PASS or FAIL

import subprocess, sys
import lib.data_json_parser as djp

remoteCommand = "grep nameserver /etc/resolv.conf"
passed = 0
failed = 0

def remoteCmd(host, command):
    cmd = subprocess.Popen(['ssh', '-o StrictHostKeyChecking=no', host , command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
   
    stdout,stderr = cmd.communicate()
    return stdout

# quick check to ensure we received the locations of data.json and statics.conf
if len(sys.argv) != 2:
    print("Wrong number of arguments provided")
    sys.exit()
    
data = djp.dataJson(sys.argv[1])
dns_server = data.getGlobalMD()['dns-server']

# ensure remote MAC matches data.json (casminst-384) and statics.conf (casminst-380)
for server in data.ncnList:
    # get the MAC from the NCN
    results = remoteCmd(server, remoteCommand).decode().strip().split()
    
    if len(results) < 1:
        # result set empty
        print("No nameserver entry in /etc/resolv.conf for server " , server)

    else:
        for result in results:
            #print("result", result, type(result), dns_server, dns_server in result)
            if dns_server in result:
                passed += 1

if passed == len(data.ncnList):
    print("PASS")
else:
    print("FAIL")
