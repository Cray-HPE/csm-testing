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
from typing import Tuple
import requests
from kubernetes import client, config
from keycloak import KeycloakOpenID


class AuthException(Exception):
    """A wrapper for raising an AuthException exception."""


class Auth:
    """Class to get the k8s secret and generate token for making API calls"""

    def __init__(self):
        self._token = None

    @classmethod
    def get_secrets(cls) -> Tuple[str, str]:
        """Reads secret for generating token

        Raises:
            AuthException

        Returns:
            Tuple[str, str]: token
        """
        try:
            config.load_kube_config()
            k8s_v1 = client.CoreV1Api()
            sec = k8s_v1.read_namespaced_secret("admin-client-auth", "default").data
            username = base64.b64decode(sec.get("client-id").strip()).decode("utf-8")
            password = base64.b64decode(sec.get("client-secret").strip()).decode(
                "utf-8"
            )
        except Exception as err:
            raise AuthException("Unable to load secrets from Kubernetes") from err

        return username, password

    @classmethod
    def get_token(cls, username, password):
        """Gets token for API calls

        Args:
            username (str): username from the secret
            password (str): password from the secret

        Raises:
            AuthException

        Returns:
            token
        """
        try:
            keycloak_openid = KeycloakOpenID(
                server_url="https://api-gw-service-nmn.local/keycloak/",
                client_id=username,
                realm_name="shasta",
                client_secret_key=password,
                verify=False,
            )

            token = keycloak_openid.token(grant_type="client_credentials")
        except Exception as err:
            raise AuthException("Unable to obtain token from Keycloak") from err

        return token["access_token"]

    @property
    def token(self):
        """Gets the token and update it in self._token

        Returns:
            str: token
        """
        if not self._token:
            username, password = self.get_secrets()
            self._token = self.get_token(username, password)

        return self._token


class ApiInterface:
    """Class contains all the API call functions"""

    def __init__(
        self,
        apiurl: str = "https://api-gw-service-nmn.local/apis",
        resource: str = "/iuf/v1",
    ):
        self.auth = Auth()
        self.apiurl = os.getenv("IUF_API_URL", apiurl)
        self.resource = os.getenv("IUF_API_URL_RESOURCE", resource)

    def request(self, method, path, payload=None, timeout=None):
        """Makes API request

        Args:
            method (str): method for the API request
            path (str): endpoint for the url
            payload : Defaults to None.
            timeout (int, optional): timeout for the request. Defaults to None.

        Returns:
            API response
        """
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
        try:
            if payload:
                result = getattr(requests, method_func)(
                    url, headers=headers, json=payload, verify=False, timeout=timeout
                )
            else:
                result = getattr(requests, method_func)(
                    url, headers=headers, verify=False, timeout=timeout
                )
        except Exception as err:
            print(err)
            raise

        # throw an exception for bad status codes
        result.raise_for_status()

        return result

    def activity_exists(self, activity):
        """Checks if the activity exists

        Args:
            activity (activity): name of IUF activity

        Returns:
            bool: If API call is successful then True, False otherwise
        """
        try:
            self.get_activity(activity)
            return True
        except HTTPError as err:
            print(err)
            return False

    def get_stages(self):
        """Gets all IUF stages

        Returns:
            API response containing list of IUF stages
        """
        api_path = "/stages"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity(self, activity):
        """Fetch details of a specific activity.

        Args:
            activity (str): Name of the IUF activity.

        Returns:
            API response containing activity details.
        """
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activities(self):
        """Fetch a list of all activities.

        Returns:
            API response containing a list of activities.
        """
        api_path = "/activities"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_sessions(self, activity):
        """Fetch sessions for a specific activity.

        Args:
            activity (str): Name of the IUF activity.

        Returns:
            API response containing activity sessions.
        """
        api_path = f"/activities/{activity}/sessions"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_activity(self, payload):
        """Create a new activity.

        Args:
            payload (dict): Data required to create the activity.

        Returns:
            API response after creating the activity.
        """
        api_path = "/activities"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def patch_activity(self, activity, payload):
        """Update an existing activity.

        Args:
            activity (str): Name of the IUF activity.
            payload (dict): Data required to update the activity.

        Returns:
            API response after updating the activity.
        """
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("PATCH", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def abort_activity(self, activity, payload):
        """Abort a specific activity.

        Args:
            activity (str): Name of the IUF activity.
            payload (dict): Data required to abort the activity.

        Returns:
            API response after aborting the activity.
        """
        api_path = f"/activities/{activity}/history/abort"
        try:
            api_response = self.request("POST", api_path, payload, timeout=90)
            return api_response
        except requests.ReadTimeout as exc:
            raise exc
        except HTTPError as err:
            print(err)
            raise

    def post_activity_history_run(self, activity, payload):
        """Run an activity and store it in history.

        Args:
            activity (str): Name of the IUF activity.
            payload (dict): Data required to run the activity.

        Returns:
            API response after running the activity.
        """
        api_path = f"/activities/{activity}/history/run"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_resume(self, activity, payload):
        """Resume a specific activity.

        Args:
            activity (str): Name of the IUF activity.
            payload (dict): Data required to resume the activity.

        Returns:
            API response after resuming the activity.
        """
        api_path = f"/activities/{activity}/history/resume"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def post_restart(self, activity, payload):
        """Restart a specific activity.

        Args:
            activity (str): Name of the IUF activity.
            payload (dict): Data required to restart the activity.

        Returns:
            API response after restarting the activity.
        """
        api_path = f"/activities/{activity}/history/restart"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_history(self, activity):
        """Fetch the history of a specific activity.

        Args:
            activity (str): Name of the IUF activity.

        Returns:
            API response containing the activity history.
        """
        api_path = f"/activities/{activity}/history"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_history_time(self, activity, time):
        """Fetch the history of an activity at a specific time.

        Args:
            activity (str): Name of the IUF activity.
            time (str): Specific time for fetching activity history.

        Returns:
            API response containing the activity history at the specified time.
        """
        api_path = f"/activities/{activity}/history/{time}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise

    def get_activity_session(self, activity, session_name):
        """Fetch details of a specific activity session.

        Args:
            activity (str): Name of the IUF activity.
            session_name (str): Name of the activity session.

        Returns:
            API response containing session details.
        """
        api_path = f"/activities/{activity}/sessions/{session_name}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except HTTPError as err:
            print(err)
            raise
