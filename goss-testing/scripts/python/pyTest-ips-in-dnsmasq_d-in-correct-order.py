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
import ipaddress
import sys
import logging, datetime

'''
Simple script to ensure that the dhcp-range in the /etc/dnsmasq.d/{net}.conf files
  are in the correct order. This error was encountered on surtur and caused problems
The location of the files is already known, as well as the file names. If that changes
  this script will break. Because of the number of files in dnsmasq.d this is the only
  way this check can be accomplished (Can't check all files in the directory)

Note: It's possible to get the filenames from GOSS variables, so if the names change,
  which is a concern, they would only need to be changed in the variables file.

USAGE: pyTest-dhcp-reange-in-dnsmasq_d-in-correct-order.py
Goss will search the output for the word FAIL

'''

def now():
    # convenience function because it'll be used for logging
    return str(datetime.datetime.now())

# In case we want to make this script more user-friendly and add argparse or configparser
# CRITICAL 50, ERROR 40, WARNING 30, INFO 20, DEBUG 10, NOTSET 0
l_lvl = logging.INFO
# Start the logger
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=l_lvl)
logging.info(now()+" Starting up")

fileDir = "/etc/dnsmasq.d/"
fileNames = ['CAN', 'NMN', 'HMN', 'mtl' ]
contents =[] 

if __name__ == '__main__':
    # Iterate over the list of filenames and try to open the file
    for fileName in fileNames:
        # clear the start and end strings
        logging.info(now()+" Checking %s.", fileDir+fileName)
        start = end = ''
        try:
            f = open(fileDir+fileName+".conf", 'r')
            #contents = f.read().split('\n')
        except:
            logging.critical(now()+" Couldn't open %s.", fileDir+fileName+'.conf')
            print("Unable to open file: "+fileName+".conf")
            sys.exit(1)

        # if the contents of the file !NULL - read the file line-by-line 
        # and check if the line contains 'dhcp-range'
        # it's a really good bet that the format of that line will not change
        line = f.readline()
        while line:
            logging.debug(now() + " line from %s: %s", fileName, line.strip())
            # If the line continas 'dhcp-range' extract the start and end addresses
            if 'dhcp-range' in line:
                start = line.split(',')[1]
                end = line.split(',')[2]
                logging.debug("Start IP = %s, End IP = %s.", start, end)
            line = f.readline()

            # If we found the start IP, ensure that it is less than the end IP
        if start:
            # They really should be valid ip addresses, but using try/except just in case
            try:
                start_ip = ipaddress.ip_address(start)
                end_ip = ipaddress.ip_address(end)
            except:
                logging.critical(now()+" Could not convert either start = %s or end = %s to IP addresses.", start, end)
                print("FAIL: Conversion of strings to IP addresses failed")
                sys.exit(2)

            if start_ip < end_ip:
                print("PASS")
            else:
                logging.error( now()+" The file %s failed. Start IP (%s) >= End IP (%s).", fileDir + fileName + ".conf", start, end)
                print("FAIL for file:" + fileDir + fileName + ".conf")
        else:
            print("FAIL - no starting IP address found")
