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
import sys, ipaddress, logging, subprocess

'''
USAGE: pyTest-ip-not-in-ip-pools.py GOSS.VARS.ALL-INTERFACES
Re-write of the original script
This version of Goss passes the list in an ugly fashion "[bond0, vlan002...]" so
  the script needs to account for this and the prettier way future versions pass them
This script will now get the ip pools from /etc/dnsmasq.d/*.conf
The file names are in a hard-coded list in this script - this may be better done using goss variables
It will then check to make sure they are in the proper order in the conf file (CASMINST-<need ticket>)
Then check to make sure the IP(using subprocess) of this instance is not in the pool
'''

# setup logging
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=logging.INFO)
logging.info("Starting up")

if len(sys.argv) <2:
    print("Incorrect number of arguments")
    sys.exit()
logging.debug("Passed args: %s", sys.argv)

# workaround becasue v0.3.13 sends [.Arg.*] with the brackets
#fileName = sys.argv[2].strip('[').strip(']')
passed = 0
failed = 0

net_list = ['mtl','NMN', 'HMN', 'CAN']

ips = []
ifaces_list = []

def get_ip(interface):
    logging.debug("Getting ip address for %s", interface)
    cmd = subprocess.Popen(['ip', 'addr', 'show', 'dev', interface],stdout=subprocess.PIPE )
    stdout, stderr = cmd.communicate()
    logging.debug("stdout == %s, stderr == %s", stdout, stderr)
    if stdout != '':
        ip_line = stdout.decode().split('\n')[2].strip()
        # couldn't cause this to happen in one line
        ip = ip_line[ip_line.find(' ') + 1:]
        ip = ip[:ip.find(' ')]
        logging.info("IP address of %s = %s", interface, ip)
    return ip

def is_ip_between(ip, start_ip, end_ip, file):
    # convert them for easy testing
    logging.debug("Trying to convert ip %s start_ip %s end_ip %s", ip, start_ip, end_ip)
    try:
        ips = ipaddress.ip_address(ip)
        start_ip = ipaddress.ip_address(start_ip)
        end_ip = ipaddress.ip_address(end_ip)
    except:
        logging.critical("Could not convert %s or %s or %s to an IP address", ip, start_ip, end_ip)
        print("Couldn't convert an ip to IPaddress. See the log for details")
        sys.exit(0)

    # Sometimes they get swapped
    if start_ip > end_ip:
        start_ip, end_ip = end_ip, start_ip

    if ips >= start_ip and ips <= end_ip:
        print("Failed: This IP is in the pool range.")
        print("This IP = ", ips, "Pool start IP = ", start_ip, "Pool end IP = ", end_ip)
        logging.error("This IP = ", ips, "Pool start IP = ", start_ip, "Pool end IP = ", end_ip)
        return "FAIL"
    else:
        return "PASS"

def get_start_last_from_dnsmask_d(fileName):
    f = open('/etc/dnsmasq.d/'+fileName+'.conf')
    data = f.read().split('\n')
    for line in data:
        if 'dhcp-range' in line:
            start = line.split(',')[1]
            end = line.split(',')[2]
    return start, end

# make a list of the args we got from goss - from 2:
logging.debug("Running through args %s", sys.argv[1:])
for li in sys.argv[1:]:
    logging.info("Arguments from goss: %s",li)
    ifaces_list.append(li.strip('[').strip(']'))

for iface in ifaces_list:
    logging.debug("Getting IP address for %s", iface)
    thisIP = get_ip(iface).split('/')[0]
    ips.append(thisIP)

    # iterate through the list looking for start end
    for net in net_list:
        starts = ends = ''
        starts, ends = get_start_last_from_dnsmask_d(net)

        if starts != '':
            logging.info("is_ip_between call: %s, %s, %s",thisIP, starts, ends)
            if is_ip_between(thisIP, starts, ends, net) == 'PASS':
                passed += 1
            else:
                print("Test failed for "+net+".conf")
    logging.debug(ips)

if passed == len(net_list * len(ips)):
    print("PASS")
else:
    print("FAIL")

