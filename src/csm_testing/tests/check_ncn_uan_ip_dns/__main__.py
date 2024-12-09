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
    token_resp = gw_api('POST', token_url, data=token_data)
    access_token = token_resp.json()['access_token']
    # print (f'access_token')

    return access_token


def main():  # pylint: disable=missing-function-docstring
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
            nslookup_cmd = subprocess.Popen(('nslookup', ipa),
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
            output, _ = nslookup_cmd.communicate()
            print(output.decode('ascii'))

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

    for hostname in hostname_list:

        dig_cmd = subprocess.Popen(('dig', hostname, '+short'),
                                   stdout=subprocess.PIPE)
        wc_cmd = subprocess.check_output(('wc', '-l'), stdin=dig_cmd.stdout)
        result = int(wc_cmd.decode('ascii').strip())
        if result > 1:
            error_found = True
            log.error('ERROR: %s has more than 1 DNS entry', hostname)
            nslookup_cmd = subprocess.Popen(('nslookup', hostname),
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)
            output, _ = nslookup_cmd.communicate()
            print(f"{output.decode('ascii')}")

    if error_found:
        log.error('ERRORS: see above output.')
        sys.exit(1)
    log.debug('No errors found.')
    sys.exit(0)


if __name__ == "__main__":
    main()
