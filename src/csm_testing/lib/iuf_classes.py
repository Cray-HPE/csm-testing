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

"""
Defining class for API calls
"""
import os
import base64
from urllib.error import HTTPError
import requests
from kubernetes import client, config  # pylint: disable=import-error
from keycloak import KeycloakOpenID  # pylint: disable=import-error


class AuthException(Exception):
    """A wrapper for raising an AuthException exception."""


class Auth:  # pylint: disable=missing-class-docstring
    def __init__(self):  # pylint: disable=missing-function-docstring
        self._token = None

    def get_secrets(self):  # pylint: disable=missing-function-docstring,R0201
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()  # pylint: disable=invalid-name
            sec = v1.read_namespaced_secret("admin-client-auth", "default").data
            username = base64.b64decode(sec.get("client-id").strip()).decode("utf-8")
            password = base64.b64decode(sec.get("client-secret").strip()).decode(
                "utf-8"
            )
        except: # pylint: disable=raise-missing-from
            raise AuthException(
                "Unable to load secrets from Kubernetes"
            )

        return username, password

    def get_token(
        self, username, password
    ):  # pylint: disable=missing-function-docstring,R0201
        try:
            keycloak_openid = KeycloakOpenID(
                server_url="https://api-gw-service-nmn.local/keycloak/",
                client_id=username,
                realm_name="shasta",
                client_secret_key=password,
                verify=False,
            )

            token = keycloak_openid.token(grant_type="client_credentials")
        except: # pylint: disable=raise-missing-from
            raise AuthException("Unable to obtain token from Keycloak")

        return token["access_token"]

    @property
    def token(self):  # pylint: disable=missing-function-docstring
        if not self._token:
            username, password = self.get_secrets()
            self._token = self.get_token(username, password)

        return self._token


class ApiInterface:  # pylint: disable=missing-class-docstring
    def __init__(
        self,
        apiurl: str = "https://api-gw-service-nmn.local/apis",
        resource: str = "/iuf/v1",
    ):  # pylint: disable=missing-function-docstring
        self.auth = Auth()
        self.apiurl = os.getenv("IUF_API_URL", apiurl)
        self.resource = os.getenv("IUF_API_URL_RESOURCE", resource)
        self.token = self.auth.token

    def request(
        self, method, path, payload=None, timeout=None, token=None
    ):  # pylint: disable=missing-function-docstring, too-many-arguments
        method = method.upper()
        assert method in ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]

        url = self.apiurl + self.resource + path

        headers = {}
        try:
            token = self.auth.token
            headers["Authorization"] = f"Bearer {token}"
        except AuthException:
            if "gw-service" in self.apiurl:
                raise

        method_func = method.lower()

        if payload:
            result = getattr(requests, method_func)(
                url, headers=headers, json=payload, verify=False, timeout=timeout
            )
        else:
            result = getattr(requests, method_func)(
                url, headers=headers, verify=False, timeout=timeout
            )

        # throw an exception for bad status codes
        result.raise_for_status()

        return result

    def activity_exists(self, activity):  # pylint: disable=missing-function-docstring
        try:
            self.get_activity(activity)
            return True
        except HTTPError as err:
            print(err)
            return False

    def get_activity(self, activity):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activities(self):  # pylint: disable=missing-function-docstring
        api_path = "/activities"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_sessions(
        self, activity
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/sessions"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_activity(self, payload):  # pylint: disable=missing-function-docstring
        api_path = "/activities"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def patch_activity(
        self, activity, payload
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("PATCH", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def abort_activity(
        self, activity, payload
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history/abort"
        try:
            api_response = self.request("POST", api_path, payload, timeout=90)
            return api_response
        except requests.ReadTimeout as exc:
            raise exc
        except HTTPError as err:
            print(err)
            raise

    def post_activity_history_run(
        self, activity, payload
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history/run"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_resume(
        self, activity, payload
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history/resume"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_restart(
        self, activity, payload
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history/restart"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_history(
        self, activity
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_history_time(
        self, activity, time
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/history/{time}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_session(
        self, activity, session_name
    ):  # pylint: disable=missing-function-docstring
        api_path = f"/activities/{activity}/sessions/{session_name}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise
