#! /usr/bin/env python3
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
# Script to check MAC address of remote NCNs against data.json and statics.conf
# Invocation: check-remote-mac-against-configs.py /path/to/data.json /path/to/statics.conf
# Check the count of passed tests against the number of NCNs in data.conf - and send either PASS or FAIL

import subprocess, sys, logging
import lib.data_json_parser as djp

getMACcommand = "ip addr show dev bond0 | grep 'link/ether' | tr -s ' ' | cut -d ' ' -f 3"
passed = 0
failed = 0

# setup logging
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=logging.DEBUG)
logging.info("Starting up")

def remoteCmd(host, command):
    cmd = subprocess.Popen(['ssh', '-o StrictHostKeyChecking=no', host , command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout,stderr = cmd.communicate()
    return stdout

def get_arg_no_brackets(arg):
    return arg.strip('[').strip(']')

# quick check to ensure we received the locations of data.json and statics.conf
if len(sys.argv) != 3:
    print("Wrong number of arguments provided")
    sys.exit()
    
# This version of goss sends [.Arg.*] as string with [
# Apparently fixed in 0.3.14 
data = djp.dataJson(get_arg_no_brackets(sys.argv[1]))
staticsFile = open(get_arg_no_brackets(sys.argv[2]),'r')
statics = staticsFile.read()


# ensure remote MAC matches data.json (casminst-384) and statics.conf (casminst-380)
for server in data.ncnList:
    # get the MAC from the NCN
    mac = remoteCmd(server, getMACcommand).decode().strip()
    
    # ensure that the MAC address is somewhere in data.json
    if mac in data.ncnKeys:
        # ensure that the hostname's MAC in data.json matches reality
        if data.ncnList[server] == mac:
            passed += 1
    else:
        failed += 1
        
    # ensure that the mac exists in statics.conf
    if mac in statics:
        # check statics.conf
        # should find something like: dhcp-host=b8:59:9f:2b:2e:d2,10.252.0.7,ncn-s001,infinite
        # the ip is between the first commas
        try:
            search = statics[statics.find('dhcp-host=' + data.ncnList[server]):statics.find('\n',statics.find('dhcp-host=' + data.ncnList[server]))]    
            ip, hname = search[search.find(','):search.rfind(',')].split(',')[-2:]
            if mac == data.ncnList[hname]: 
                passed += 1
        except:
            print("Error in statics.conf")

    else:
        failed += 1
# There are two tests per ncn, so the number of tests passed should == number of keys * 2
if passed == len(data.ncnKeys) * 2:
    print("PASS")
else:
    print("FAIL")

