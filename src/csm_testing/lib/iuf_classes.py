import requests
import os
from kubernetes import client, config
import base64
from keycloak import KeycloakOpenID
import urllib3
from csm_testing.lib.iuf_constants import MEDIA_DIR
from csm_testing.lib.iuf_common import media_dir_setup





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


class ApiInterface_no_token(object):
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
            token = None
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

    def get_stages(self):
        api_path = f"/stages"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

class ApiInterface(object):
    def __init__(self, apiurl="https://api-gw-service-nmn.local/apis", resource="/iuf/v1"):
        self.auth = Auth()
        self.apiurl = os.getenv("IUF_API_URL", apiurl)
        self.resource = os.getenv("IUF_API_URL_RESOURCE", resource)

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
    
    def activity_exists(self, activity):
        try:
            self.get_activity(activity)
            return True
        except:
            return False

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
            return api_path
        except requests.ReadTimeout as exc:
            raise exc
        except Exception as ex:
            raise

    def get_activities(self):
        api_path = f"/activities"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

    def get_stages(self):
        api_path = f"/stages"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

    def get_activity_sessions(self, activity):
        api_path = f"/activities/{activity}/sessions"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise
    
    def post_activity(self, payload):
        api_path = "/activities"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except:
            raise

    def patch_activity(self, activity, payload):
        api_path = f"/activities/{activity}"

        try:
            api_response = self.request("PATCH", api_path, payload)
            return api_response
        except:
            raise

    def abort_activity(self, activity, payload):
        api_path = f"/activities/{activity}/history/abort"
        try:
            api_response = self.request("POST", api_path, payload, timeout=90)
            return api_response
        except requests.ReadTimeout as exc:
            raise exc
        except Exception as ex:
            raise

    def post_activity_history_run(self, activity, payload):
        api_path = f"/activities/{activity}/history/run"

        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except:
            raise

    def post_resume(self, activity, payload):
        api_path = f"/activities/{activity}/history/resume"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except:
            raise


    def post_restart(self, activity, payload):
        api_path = f"/activities/{activity}/history/restart"
        try:
            api_response = self.request("POST", api_path, payload)
            return api_response
        except:
            raise

    def get_activity_history(self, activity):
        api_path = f"/activities/{activity}/history"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

    def get_activity_history_time(self, activity, time):
        api_path = f"/activities/{activity}/history/{time}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise

    def get_activity_session(self, activity,session_name):
        api_path = f"/activities/{activity}/sessions/{session_name}"
        try:
            api_response = self.request("GET", api_path)
            return api_response
        except:
            raise
