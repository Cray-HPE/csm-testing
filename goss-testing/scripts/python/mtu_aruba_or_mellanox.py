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

"""
This script is meant to be run by Goss, checking the MTU on the spine switches
and printing "FAIL" if the MTU is less than the expected value. It is not written
to be run by humans, but can be.

It parses the sls_input_file.json file to get the switch 'Brand' and the HMN.yaml
file to get the switch IP address. These files are expected to be in
/var/www/ephemeral/prep/<environment>/. If they are not there, the test will fail.

Then, depending on the brand, the correct query is ececuted, the results are reteived,
parsed, and compared to the MTU values we got from Goss (or the command line).

It gets 4 arguments from Goss: The Aruba password, the Mellanox password, the Aruba MTU
and the Mellanox MTU. While the Aruba and Mellanox passwords are the same here and now,
that may not always be the case. The MTU settings on the switch brands is different.

"""

import json
import sys
import logging
import requests
import urllib3
import socket
import yaml
import re

# Some very light logging.
LOG_LEVEL=logging.INFO

#Dev vars - We need to get these from Goss
SLS_FILE = 'sls_input_file.json'
HMN_FILE = 'networks/HMN.yaml'
COOKIE_FILE = '/tmp/cookie'
# I need the environment name to find the files 
HOSTNAME = socket.gethostname()
HOSTNAME = HOSTNAME[:HOSTNAME.find('-')]
BASENAME = '/var/www/ephemeral/prep/' + HOSTNAME +'/'
#MELL_MTU = 9216
#ARUBA_MTU = 9198

# Start logging
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=LOG_LEVEL)
logging.info("Starting up")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_switch_info(hmn_file_name):
    #switch IPs
    spine_switches = {}
    with open(hmn_file_name, 'r') as f:
        HMN = yaml.load(f, Loader=yaml.FullLoader)
    for i in range(len(HMN['subnets'][0]['ip_reservations'])):
        switches = HMN['subnets'][0]['ip_reservations'][i]['name']
        if 'spine' in switches:
                ips = HMN['subnets'][0]['ip_reservations'][i]['ip_address']
                #switch_ips.append(ips)
                spine_switches[switches] = [ips, HMN['subnets'][0]['ip_reservations'][i]['comment']]
    #print('switch ips' ,switch_ips)
    return spine_switches

def get_results(ip_address, brand):
    #Only two possibilities for this test - either Mellanox or Aruba
    fail = False;
    if brand == 'Mellanox':
        print("Mellanox test")
        # Copied almost whole-cloth from https://stash.us.cray.com/projects/CASMNET/repos/network_troubleshooting/browse/mellanox/check_mlag.py#30
        
        PASSWD = PASS_MELL
        spine = "https://{}/admin/launch?script=".format(ip_address)
        action = "rh&template=json-request&action=json-login"
        login_body = {"username": "admin", "password": PASSWD } # JSON object
        session = requests.session()
        #create a session and get the session ID cookie
        logging.debug("spine = {}, action = {}, json = {}".format(spine, action, json))
        response = session.post(url = spine + action,
                            json = login_body,
                            verify = False) # Do not verify self-signed certs

        # TODO - better exception handling
        response.raise_for_status() # Throw an exception if HTTP response is not 200

        response_body = json.loads(response.text) # Convert JSON to python object
        if not response.text or \
            'status' not in response_body or \
            response_body['status'] != 'OK':
            print('Error {}'.format(response.text))
            logging.ERROR('Error in get_results: {}'.format(response.text))
            sys.exit()

        # If the above passes then we're logged in and session cookie is available
        # NOTE:  technically the session cookie is still in our open requests session!
        session_tuple = ()
        for item in  session.cookies.items():
            if 'session' in item:
                session_tuple = item
                logging.debug(item, "Cookie == " + str(item[1]))

        if not session_tuple:
            print('Error no session ID returned or found')
            logging.ERROR('Error in get_results: no session ID returned or found')
            sys.exit()

        #define the switch commands
        action = "json"
        cmd = { "cmd": "show interface status" } 

        #posts command to the switch.
        logging.debug( spine + action + str(cmd) )
        cmd_response = session.post(url = spine + action,
                            json = cmd,
                            #cookies = session_tuple,
                            verify = False) # Do not verify self-signed certs
        #print("cmd_response = ", cmd_response.text)

        payload = json.loads(cmd_response.text)
        for iface in payload['data']:
            if re.search("^Mpo", iface):
                mtu = payload['data'][iface][0]['MTU']
                if int(mtu) < MELL_MTU:
                    fail = True
                    print("FAIL")

    elif brand == 'Aruba':
        print("Aruba test")
        PASSWD = PASS_ARUBA
        creds = {"username": "admin", "password": PASSWD}

        session = requests.Session()
        try:
            login = session.post(f"https://{ip_address}/rest/v10.04/login", data=creds, verify=False)
            #get running config
            config = session.get(f"https://{ip_address}/rest/v10.04/fullconfigs/running-config")
            running_config = config.json()
            #get hostname of switch
            hostname = session.get(f"https://{ip_address}/rest/v10.04/system")
            my_hostname = hostname.json()
            my_hostname1 = (my_hostname['hostname'])
            if 'spine' not in my_hostname1:
                print(my_hostname1 , " is not a spine switch")
                logging.error("spine not in {}".format(my_hostname1))

            # The check
            for iface in running_config['Interface']:
                # We only care about 'up' interfaces and those with an admin key
                # Make sure the admin key is there
                # Unfortunately, python won't do 'nested_key in dict' and I found 1 interface w/o user_config 
                if 'user_config' in running_config['Interface'][iface]:
                    # Now we can ensure that the admin and mtu keys exist
                    if 'admin' in running_config['Interface'][iface]['user_config'] and 'mtu' in running_config['Interface'][iface]['user_config']:
                        # After all that - see if it is 'up'
                        if running_config['Interface'][iface]['user_config']['admin'] == "up":
                            if int(running_config['Interface'][iface]['user_config']['mtu']) < ARUBA_MTU:
                                print("FAIL")
                                fail = True
                            
        finally:
            logout = session.post(f"https://{ip_address}/rest/v10.04/logout")
            # print(f"This is the logout code: {logout.status_code}")

    else:
        logging.error("Unrecognized brand in data passed to 'get_results': {}".format(brand))
        sys.exit(1)

    return fail

if __name__ == '__main__':

    # We're expecting Goss to send us:
    # The Aruba password and the Mellanox password. While these are the same now, it may not always be so.
    # We also need the MTU of both brands as they are not the same
    lArgv = len(sys.argv)
    if lArgv >= 3 and lArgv < 5: # assume a human is running it
        ARUBA_MTU = 9198
        MELL_MTU = 9216
        PASS_ARUBA = sys.argv[1]
        PASS_MELL = sys.argv[2]
    elif lArgv < 3:
        print("The Aruba and Mellanox admin passwords (both) are required to run this script")
        logging.critical("Passwords were not received as arguments")
        sys.exit(1)
    elif lArgv == 5: # We got the args from Goss
        PASS_ARUBA = sys.argv[1]
        PASS_MELL = sys.argv[2]
        ARUBA_MTU = int(sys.argv[3])
        MELL_MTU = int(sys.argv[4])
    else:
        print("Wrong number of arguments. Usage: mtu_aruba_or_mellanox.py aruba_password mellanox_password aruba_mtu mellanox_mtu")
        logging.critical("Wrong number of arguments passed. Args = {}.".format(sys.argv))
        sys.exit(1)

    # Setting up the needed files
    SLS_FILE = BASENAME + SLS_FILE
    HMN_FILE = BASENAME + HMN_FILE
    
    with open(SLS_FILE, 'r') as f:
        payload = f.read().strip()
    data = json.loads(payload)

    data_hw = data['Hardware']
    data_net = data['Networks']

    # A list of dictionaries of the data in the switches part of the file - dictionary looks like:
    # [{'Name': 'sw-spine-001', 'IPAddress': '10.254.0.2', 'Comment': 'x3000c0h24s1'},
    switches = data_net['HMN']['ExtraProperties']['Subnets'][0]['IPReservations']

    for switch in switches:
        if 'spine' in switch['Name']:
            switch_name = switch['Name']
            switch_xname = switch['Comment']
            switch_IP_addr = get_switch_info(HMN_FILE)[switch_name][0]
            switch_brand = data_hw[switch_xname]['ExtraProperties']['Brand']
            logging.debug(switch_name, switch_IP_addr, switch_xname, switch_brand)
            results = get_results(switch_IP_addr, switch_brand)

