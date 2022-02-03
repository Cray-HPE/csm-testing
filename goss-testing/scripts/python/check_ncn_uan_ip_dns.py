#!/usr/bin/env python3

# Copyright 2014-2021 Hewlett Packard Enterprise Development LP
import base64
import subprocess
import json
import sys
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urljoin
from kubernetes import client, config



class APIRequest(object):
    """

    Example use:
        api_request = APIRequest('http://api.com')
        response = api_request('GET', '/get/stuff')

        print (f"response.status_code")
        print (f"{response.status_code}")
        print()
        print (f"response.reason")
        print (f"{response.reason}")
        print()
        print (f"response.text")
        print (f"{response.text}")
        print()
        print (f"response.json")
        print (f"{response.json()}")
    """

    def __init__(self, base_url, headers=None):
        if not base_url.endswith('/'):
            base_url += '/'
        self._base_url = base_url

        if headers is not None:
            self._headers = headers
        else:
            self._headers = {}

    def __call__(self, method, route, **kwargs):

        if route.startswith('/'):
            route = route[1:]

        url = urljoin(self._base_url, route, allow_fragments=False)

        headers = kwargs.pop('headers', {})
        headers.update(self._headers)

        retry_strategy = Retry(
            total=10,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["PATCH", "DELETE", "POST", "HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        response = http.request(method=method, url=url, headers=headers, **kwargs)

        if 'data' in kwargs:
            log.debug(f"{method} {url} with headers:"
                      f"{json.dumps(headers, indent=4)}"
                      f"and data:"
                      f"{json.dumps(kwargs['data'], indent=4)}")
        elif 'json' in kwargs:
            log.debug(f"{method} {url} with headers:"
                      f"{json.dumps(headers, indent=4)}"
                      f"and JSON:"
                      f"{json.dumps(kwargs['json'], indent=4)}")
        else:
            log.debug(f"{method} {url} with headers:"
                      f"{json.dumps(headers, indent=4)}")
        log.debug(f"Response to {method} {url} => {response.status_code} {response.reason}"
                  f"{response.text}")

        return response


# globals
gw_api = APIRequest('https://api-gw-service-nmn.local')

log = logging.getLogger(__name__)
log.setLevel(logging.WARN)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


def token():
    # setup kubernetes client
    config.load_kube_config()
    v1 = client.CoreV1Api()

    # get kubernetes admin secret
    secret = v1.read_namespaced_secret("admin-client-auth", "default").data

    # decode the base64 secret
    token = base64.b64decode(secret['client-secret']).decode('utf-8')

    # create post data to keycloak istio ingress
    token_data = {'grant_type': 'client_credentials', 'client_id': 'admin-client', 'client_secret': token}

    # query keycloack
    token_url = '/keycloak/realms/shasta/protocol/openid-connect/token'
    token_resp = gw_api('POST', token_url, data=token_data)
    access_token = token_resp.json()['access_token']
    # print (f'access_token')

    return access_token

def main():

    error_found = False

    bearer_token = token()
    # request header passing token
    headers = {'Authorization': 'Bearer ' + bearer_token}

    # query SMD EthernetInterfaces
    smd_url = '/apis/smd/hsm/v2/Inventory/EthernetInterfaces'
    smd_resp = gw_api('GET', smd_url, headers=headers)
    smd_ethernet_interfaces = smd_resp.json()

    # query SLS hardware
    sls_url = '/apis/sls/v1/hardware'
    sls_resp = gw_api('GET', sls_url, headers=headers)
    sls_hardware = sls_resp.json()

    ip_set = set()
    for smd_entry in smd_ethernet_interfaces:
        # print (smd_entry)
        if smd_entry['IPAddresses'] != '[]':
            ip_addresses = smd_entry['IPAddresses']
            for ips in ip_addresses:
                ip = ips['IPAddress']
                # print (ip)
                if ip != '':
                    if ip in ip_set:
                        log.error(f'Error: found duplicate IP: {ip}')
                        error_found = True
                        nslookup_cmd = subprocess.Popen(('nslookup', ip), stdout=subprocess.PIPE,
                                                        stderr=subprocess.PIPE)
                        output, errors = nslookup_cmd.communicate()
                        print("output.decode('ascii')")
                    else:
                        ip_set.add(ip)

    hostname_list = []

    for i in range(len(sls_hardware)):
        if 'ExtraProperties' in sls_hardware[i]:
            if 'Role' in sls_hardware[i]['ExtraProperties'] and (
                    sls_hardware[i]['ExtraProperties']['Role'] == 'Application' or sls_hardware[i]['ExtraProperties'][
                'Role'] == 'Management'):
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '.nmn')
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '.can')
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '.hmn')
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '-mgmt')
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '.cmn')
                hostname_list.append(sls_hardware[i]['ExtraProperties']['Aliases'][0] + '.chn')

    for hostname in hostname_list:

        dig_cmd = subprocess.Popen(('dig', hostname, '+short'), stdout=subprocess.PIPE)
        wc_cmd = subprocess.check_output(('wc', '-l'), stdin=dig_cmd.stdout)
        result = int(wc_cmd.decode('ascii').strip())
        if result > 1:
            error_found = True
            log.error(f'ERROR: {hostname} has more than 1 DNS entry')
            nslookup_cmd = subprocess.Popen(('nslookup', hostname), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, errors = nslookup_cmd.communicate()
            print(f"{output.decode('ascii')}")

    if error_found:
        log.error('ERRORS: see above output.')
        sys.exit(1)
    else:
        log.debug('No errors found.')
        sys.exit(0)

if __name__ == "__main__":
    main()