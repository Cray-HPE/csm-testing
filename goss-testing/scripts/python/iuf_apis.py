#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2024 Hewlett Packard Enterprise Development LP
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

import requests
import os
from kubernetes import client, config
import base64
from keycloak import KeycloakOpenID

class AuthException(Exception):
    """A wrapper for raising an AuthException exception."""
    pass

class Auth():
    def __init__(self):
        self._token = None
    
    def get_secrets(self):
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()
            sec = v1.read_namespaced_secret("admin-client-auth", "default").data
            username = base64.b64decode(sec.get("client-id").strip()).decode('utf-8')
            password = base64.b64decode(sec.get("client-secret").strip()).decode('utf-8')
        except:
            raise AuthException("Unable to load secrets from Kubernetes")

        return username, password
    
    def get_token(self, username, password):
        try:
            keycloak_openid = KeycloakOpenID(server_url="https://api-gw-service-nmn.local/keycloak/",
                                    client_id=username,
                                    realm_name="shasta",
                                    client_secret_key=password,
                                    verify=False)

            token = keycloak_openid.token(grant_type="client_credentials")
        except:
            raise AuthException("Unable to obtain token from Keycloak")

        return token["access_token"]

    @property
    def token(self):
        if not self._token:
            username, password = self.get_secrets()
            self._token = self.get_token(username, password)

        return self._token
    

class ApiInterface(object):
    def __init__(self, apiurl="https://api-gw-service-nmn.local/apis", resource="/iuf/v1"):
        self.auth = Auth()
        self.apiurl = os.getenv("IUF_API_URL", apiurl)
        self.resource = os.getenv("IUF_API_URL_RESOURCE", resource)

    def activity_exists(self, activity):
        try:
            self.get_activity(activity)
            return True
        except:
            return False

    def request(self, method, path, payload=None, timeout=None):
        method = method.upper()
        assert method in ['GET', 'HEAD', 'DELETE', 'POST', 'PUT',
                          'PATCH', 'OPTIONS']

        url=self.apiurl + self.resource + path

        headers = dict()
        try:
            token = self.auth.token
            headers["Authorization"] = f"Bearer {token}"
        except:
            if "gw-service" in self.apiurl:
                raise
            else:
                # if we're not using the "official" api and don't get a token just try without it.  Mostly for local testing.
                pass

        method_func = method.lower()
        try:
            if payload:
                result = getattr(requests, method_func)(url, headers=headers, json=payload, verify=False, timeout=timeout)
            else:
                result = getattr(requests, method_func)(url, headers=headers, verify=False, timeout=timeout)
        except:
            raise

        # throw an exception for bad status codes
        result.raise_for_status()

        return result

    def get_activity(self, activity):
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

    def abort_activity(self, activity, payload):
        api_path = f"/activities/{activity}/history/abort"
        try:
            api_response = self.request("POST", api_path, payload, timeout=90)
        except requests.ReadTimeout as exc:
            raise exc
        except Exception as ex:
            raise

if __name__ == "__main__":
    apis= ApiInterface()

    activities = apis.get_activities().json()
    if activities is not None:
            act_list = sorted([act["name"] for act in activities])
    print("\n".join(act_list))