#! /usr/bin/env python3

import sys, ipaddress, logging, subprocess

'''
This script expects to be called with the IP address to check as the first argument
And the qnd-1.4.sh script + path as the second
'''

# setup logging
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=logging.DEBUG)

if len(sys.argv) <=3:
    print("Incorrect number of arguments")
    sys.exit()
logging.debug("Passed args: %s", sys.argv)
thisIP = sys.argv[1].split('/')[0]
# workaround becasue v0.3.13 sends [.Arg.*] with the brackets
fileName = sys.argv[1].strip('[').strip(']')
passed = 0
failed = 0

f = open(fileName, 'r')
pl = f.read().split('\n')
# remove the export part
vals_list = [sub[7:] for sub in pl]
# remove the line at eof
vals_list.remove('')
net_list = ['mtl','nmn', 'hmn', 'can']
# A list of the ips we get from goss is needed
ips = []
ifaces_list = []

if len(sys.argv) < 4:
    logging.critical("Wrong number of arguments provided: %d", len(sys.argv))
    for arg in sys.argv:
        logging.critical('Args :' + arg)

def get_ip(interface):
    cmd = subprocess.Popen(['ip', 'addr', 'show', 'dev', interface],stdout=subprocess.PIPE )
    stdout, stderr = cmd.communicate()
    if stdout != '':
        ip_line = stdout.decode().split('\n')[2].strip()
        # couldn't cause this to happen in one line
        ip = ip_line[ip_line.find(' ') + 1:]
        ip = ip[:ip.find(' ')]
    return ip

def is_ip_between(ip, start_ip, end_ip):
    ips = ipaddress.ip_address(ip)
    start_ip = ipaddress.ip_address(start_ip)
    end_ip = ipaddress.ip_address(end_ip)
    if ips >= start_ip and ips <= end_ip:
        return "FAIL"
    else:
        return "PASS"

# make a list of the args we got from goss - from 2:
for li in sys.argv[2:]:
    logging.info(li)
    ifaces_list.append(li.strip('[').strip(']'))

for iface in ifaces_list:
    thisIP = get_ip(iface).split('/')[0]
    ips.append(thisIP)

    # iterate through the list looking for start end
    for net in net_list:
        starts = ends = ''
        for val in vals_list:
            if net + '_dhcp_start' in val:
                starts = val.split('=')[1]
            elif net + '_dhcp_end' in val:
                ends = val.split('=')[1]
        if starts != '':
            logging.info("is_ip_between call: %s, %s, %s",thisIP, starts, ends)
            if is_ip_between(thisIP, starts, ends) == 'PASS':
                passed += 1
    logging.info(ips)

if passed == len(net_list * len(ips)):
    print("PASS")
else:
    print("FAIL")

