#
# MIT License
#
# (C) Copyright 2014-2022, 2024 Hewlett Packard Enterprise Development LP
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
Checks for duplicate IP addresses in the SMD EthernetInterface table and verifies that NCN/UAN
management network DNS entries resolve to only 1 IP address.
"""

import base64
import json
import logging
import subprocess
import sys
from urllib.parse import urljoin

from kubernetes import client, config
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIRequest:
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
        """
        Make the specified API request
        """
        if route.startswith('/'):
            route = route[1:]

        url = urljoin(self._base_url, route, allow_fragments=False)

        headers = kwargs.pop('headers', {})
        headers.update(self._headers)

        retry_strategy = Retry(total=10,
                               backoff_factor=0.1,
                               status_forcelist=[429, 500, 502, 503, 504],
                               method_whitelist=[
                                   "PATCH", "DELETE", "POST", "HEAD", "GET",
                                   "OPTIONS"
                               ])

        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        response = http.request(method=method,
                                url=url,
                                headers=headers,
                                **kwargs)

        if 'data' in kwargs:
            log.debug("%s %s with headers: %s and data: %s", method, url,
                      json.dumps(headers, indent=4),
                      json.dumps(kwargs['data'], indent=4))
        elif 'json' in kwargs:
            log.debug("%s %s with headers: %s and JSON: %s", method, url,
                      json.dumps(headers, indent=4),
                      json.dumps(kwargs['json'], indent=4))
        else:
            log.debug("%s %s with headers: %s", method, url,
                      json.dumps(headers, indent=4))

        log.debug("Response to %s %s => %d %s %s", method, url,
                  response.status_code, response.reason, response.text)

        return response

    def get(self, route, **kwargs):
        """
        Wrapper to __call__ for get requests
        """
        return self("GET", route, **kwargs)

    def post(self, route, **kwargs):
        """
        Wrapper to __call__ for post requests
        """
        return self("POST", route, **kwargs)


# globals
gw_api = APIRequest('https://api-gw-service-nmn.local')

log = logging.getLogger(__name__)
log.setLevel(logging.WARN)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


def token():
    """
    Obtain API access token
    """
    # setup kubernetes client
    config.load_kube_config()
    k8s_v1 = client.CoreV1Api()

    # get kubernetes admin secret
    secret = k8s_v1.read_namespaced_secret("admin-client-auth", "default").data

    # decode the base64 secret
    decoded_token = base64.b64decode(secret['client-secret']).decode('utf-8')

    # create post data to keycloak istio ingress
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': 'admin-client',
        'client_secret': decoded_token
    }

    # query keycloack
    token_url = '/keycloak/realms/shasta/protocol/openid-connect/token'
    token_resp = gw_api.post(token_url, data=token_data)
    access_token = token_resp.json()['access_token']
    # print (f'access_token')

    return access_token


def check_ip_set(headers) -> bool:
    """
    Parse SMD entries check for duplicate IPs.
    Return True if any duplicates found.
    Return Falee otherwise.
    """
    error_found = False

    # query SMD EthernetInterfaces
    smd_url = '/apis/smd/hsm/v2/Inventory/EthernetInterfaces'
    smd_resp = gw_api.get(smd_url, headers=headers)
    smd_ethernet_interfaces = smd_resp.json()

    ip_set = set()
    for smd_entry in smd_ethernet_interfaces:
        # print (smd_entry)
        if smd_entry['IPAddresses'] == '[]':
            continue
        ip_addresses = smd_entry['IPAddresses']
        for ips in ip_addresses:
            ipa = ips['IPAddress']
            # print (ipa)
            if ipa == '':
                continue
            if ipa not in ip_set:
                ip_set.add(ipa)
                continue
            log.error('Error: found duplicate IP: %s', ipa)
            error_found = True
            with subprocess.Popen(('nslookup', ipa),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as nslookup_cmd:
                output, _ = nslookup_cmd.communicate()
            print(output.decode('ascii'))
    return error_found


def get_sls_hardware(headers):
    """
    Query and return SLS hardware
    """
    # query SLS hardware
    sls_url = '/apis/sls/v1/hardware'
    sls_resp = gw_api.get(sls_url, headers=headers)
    return sls_resp.json()


def generate_hostname_list(sls_hardware):
    """
    Generate hostname list based on SLS hardware
    """
    hostname_list = []

    for hardware in sls_hardware:
        if 'ExtraProperties' not in hardware:
            continue
        if 'Role' not in hardware['ExtraProperties']:
            continue
        if hardware['ExtraProperties']['Role'] in {
                'Application', 'Management'
        }:
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}.nmn")
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}.can")
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}.hmn")
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}-mgmt")
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}.cmn")
            hostname_list.append(
                f"{hardware['ExtraProperties']['Aliases'][0]}.chn")
    return hostname_list


def main():  # pylint: disable=missing-function-docstring
    # request header passing token
    headers = {'Authorization': 'Bearer ' + token()}

    sls_hardware = get_sls_hardware(headers)

    error_found = check_ip_set(headers)

    hostname_list = generate_hostname_list(sls_hardware)

    for hostname in hostname_list:

        with subprocess.Popen(('dig', hostname, '+short'),
                              stdout=subprocess.PIPE) as dig_cmd:
            wc_cmd = subprocess.check_output(('wc', '-l'),
                                             stdin=dig_cmd.stdout)
        result = int(wc_cmd.decode('ascii').strip())
        if result > 1:
            error_found = True
            log.error('ERROR: %s has more than 1 DNS entry', hostname)
            with subprocess.Popen(('nslookup', hostname),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as nslookup_cmd:
                output, _ = nslookup_cmd.communicate()
            print(f"{output.decode('ascii')}")

    if error_found:
        log.error('ERRORS: see above output.')
        sys.exit(1)
    log.debug('No errors found.')
    sys.exit(0)


if __name__ == "__main__":
    main()
