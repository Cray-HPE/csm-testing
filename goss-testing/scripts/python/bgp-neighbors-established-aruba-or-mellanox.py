#! /usr/bin/env python3

"""
This script is meant to be run by Goss, checking the BGP neighbors of a switch,
and printing "FAIL" if the neighbor connection is not established. It is not written
to be run by humans, but can be.

It parses the sls_input_file.json file to get the switch 'Brand' and the HMN.yaml
file to get the switch IP address. These files are expected to be in
/var/www/ephemeral/prep/<environment>/. If they are not there, the test will fail.

Then, depending on the brand, the correct query is ececuted, the results are reteived,
parsed, and compared to the expected results.

It gets 2 arguments from Goss: The Aruba password, the Mellanox password While the Aruba
and Mellanox passwords are the same here and now, that may not always be the case.

"""

import json
import sys
import subprocess
import logging
import requests
import urllib3
import socket
import yaml
import re

from pathlib import Path

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
        cmd = { "cmd": "show ip bgp summary" }

        #posts command to the switch.
        logging.debug( spine + action + str(cmd) )
        cmd_response = session.post(url = spine + action,
                            json = cmd,
                            #cookies = session_tuple,
                            verify = False) # Do not verify self-signed certs
        #print("cmd_response = ", cmd_response.text)

        #print(cmd_response.text)
        payload = json.loads(cmd_response.text)
        #print(payload['data'][1])
        for neighbor in payload['data'][1]:
            if 'established' in payload['data'][1][neighbor][0]['State/PfxRcd'].lower() :
                print("Pass")
            else:
                print("FAIL")
                fail = True

    elif brand == 'Aruba':
        # The Aruba portion is a little more complex. We first need to get the neighbors.
        # Aruba kindly provides the necessary endpoint for status query in those results.
        # We then get the response from each neighbor, checking for 'Established'
        print("Aruba test")
        PASSWD = PASS_ARUBA
        creds = {"username": "admin", "password": PASSWD}

        session = requests.Session()
        try:
            login = session.post(f"https://{ip_address}/rest/v10.04/login", data=creds, verify=False)
            #get all neighbors
            config = session.get(f"https://{ip_address}/rest/v10.04/system/vrfs/default/bgp_routers/65533/bgp_neighbors")
            payload = config.json()
            #get hostname of switch
            hostname = session.get(f"https://{ip_address}/rest/v10.04/system")
            my_hostname = hostname.json()
            my_hostname1 = (my_hostname['hostname'])
            if 'spine' not in my_hostname1:
                print(my_hostname1 , " is not a spine switch")
                logging.error("spine not in {}".format(my_hostname1))

            # The check
            # The results we got back are IP.Address : api_endpoint
            for key in payload.keys():
                ns = session.get(f"https://{ip_address}"+ payload[key])
                neighbor_status = ns.json()
                if 'Established' not in neighbor_status['status']['bgp_peer_state']:
                    print("FAIL")
                    fail = True
                else:
                    print("Pass")

        finally:
            logout = session.post(f"https://{ip_address}/rest/v10.04/logout")
            # print(f"This is the logout code: {logout.status_code}")

    else:
        logging.error("Unrecognized brand in data passed to 'get_results': {}".format(brand))
        sys.exit(1)

    return fail

def get_switch_info_from_config_map():
    spine_switches = {}
    try:
        logging.info(f"Getting switch IPs from configmap")
        command_line = ['kubectl', 'get', 'cm', '-n', 'metallb-system', '-o', 'yaml', 'config']
        response = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        logging.debug(response)
        configmap = yaml.safe_load(response)
        for resource_name in configmap["data"]:
            resource = yaml.safe_load(configmap["data"][resource_name])
            for peer in resource["peers"]:
                spine_switches[peer["peer-address"]] = peer["peer-address"]
    except subprocess.CalledProcessError as err:
        logging.error(f"Could not retrieve metallb configmap. Got exit code {err.returncode}. Msg: {err.output}")
        pass

    return spine_switches


if __name__ == '__main__':

    #
    # We're expecting Goss to send us:
    # The Aruba password and the Mellanox password. While these are the same now, it may not always be so.
    #
    lArgv = len(sys.argv)
    if lArgv < 3:
        print("The Aruba and Mellanox admin passwords (both) are required to run this script")
        logging.critical("Passwords were not received as arguments")
        sys.exit(1)
    elif lArgv == 3: # We got the args from Goss
        PASS_ARUBA = sys.argv[1]
        PASS_MELL = sys.argv[2]
    else:
        print("Wrong number of arguments. Usage: bgp-neighbors-established-aruba-or-mellanox.py aruba_password mellanox_password")
        logging.critical("Wrong number of arguments passed. Args = {}.".format(sys.argv))
        sys.exit(1)

    # Setting up the needed files
    SLS_FILE = BASENAME + SLS_FILE
    HMN_FILE = BASENAME + HMN_FILE

    sls_file = Path(SLS_FILE)
    if sls_file.is_file():

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
                # assigning to the variable 'results' in case we want to do something else in the future.
                # Goss will fail when it sees 'FAIL' in STDOUT in the get_results function
                results = get_results(switch_IP_addr, switch_brand)
    else:
        #
        # No sls file -- let's get config from kubernetes
        #
        switches=get_switch_info_from_config_map()
        for switch in switches:
            logging.debug(switch)
            try:
                #
                # We will first see if we can talk Aruba
                #
                results = get_results(switch, 'Aruba')
            except ValueError:
                #
                # Failed to talk Aruba, let's try Mellanox
                #
                results = get_results(switch, 'Mellanox')
