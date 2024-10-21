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
"""
This script executes iuf api endpoint testing.
"""


import requests
import os
from kubernetes import client, config
import base64
from keycloak import KeycloakOpenID
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import sys
import copy

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

def no_auth_list_stages(apis):
    print("w/o security API call: Try Api Call without token")
    stages = None
    try :
        stages = apis.get_stages()
    except Exception as e:
        print(e)
        
    if stages is not None:
        stage_list = [stage["name"] for stage in stages['stages']]
        print("Warning Api Working without token")
        print("List Stages")
        print("\n".join(stage_list))

def list_stages(apis):
    print("List Stages")
    try:
        stage_result = apis.get_stages()
        print(stage_result)
        stages = stage_result.json()
    except Exception as ex:
        print(ex)
        sys.exit(1)
    
    if stages is not None:
        stage_list = [stage["name"] for stage in stages['stages']]
        print("\n".join(stage_list))
    

def list_activities(apis):
    print("List Activities")
    try:
        activities_result = apis.get_activities()
        print(activities_result)
        activities = activities_result.json()
    except Exception as ex:
        print(ex)
        sys.exit(1)

    if activities is not None:
        act_list = sorted([act["name"] for act in activities])
        print("\n".join(act_list))

def activity_create(apis,activity):
    print(f"Attempting to create activity {activity}")
    payload = {
        "input_parameters": {},
        "name": activity
    }

    if not apis.activity_exists(activity):
        try:
            print(apis.post_activity(payload))
            print(f"Created activity: {activity}")
        except Exception as ex:
            print(f"Unable to create activity: {activity}")
            print(ex)
            sys.exit(1)
    else:
        print(f"Activity {activity} exists")

def activity_run(apis,activity):
    print(f"Attempting to run activity {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    payload = {
            "input_parameters": {'media_dir': '/automation-tests',
            'site_parameters': '',
            'limit_management_nodes': None,
            'limit_managed_nodes': ['Compute'],
            'managed_rollout_strategy': 'stage',
            'concurrent_management_rollout_percentage': 20,
            'media_host': 'ncn-m001',
            'concurrency': 0,
            'bootprep_config_managed': '',
            'bootprep_config_management': '',
            'stages': ['process-media'],
            'force': False},
            "name": activity,
        }

    try:
        print(apis.post_activity_history_run(activity, payload))
        print(f"Activity {activity} is Started")
    except Exception as ex:
        print(f"Unable to run activity {activity}")
        print(ex)
        sys.exit(1)

    # Generate site_parameters and patch the activity.
    patched_payload = copy.deepcopy(payload)
    #patched_payload["site_parameters"] = self.site_conf.site_params

    # Remove the "force" key from input_parameters for the patched
    # activity.
    patched_payload["input_parameters"].pop("force", None)
    print(f"Patch activity: {activity}")
    print(apis.patch_activity(activity, patched_payload))

def activity_abort(apis,activity):
    print(f"Attempting to abort activity {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    payload = {
            "input_parameters": {},
            "name": activity,
            "comment": "sending an abort",
            "force": None,
        }
    try:
        print(apis.abort_activity(activity, payload))
        print(f"Aborted activity: {activity}")
    except requests.ReadTimeout:
        print("Timed out sending an abort request.")
        print(f"Ensure the argo workflow for {activity} is not running.")
        sys.exit(1)
    except Exception as ex:
        print(f"Unable to abort activity: {activity}")
        print(ex)
        sys.exit(1)

def activity_resume(apis, activity):
    print(f"Attempting to resume activity {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    payload = {
            "input_parameters": {},
            "comment": "Restart activity ",
            "activity_name": activity,
            "force": False,
        }

    try:
        api_results = apis.post_resume(activity, payload)
        print(api_results)
        print(f"Resumed activity: {activity}")
    except Exception as ex:
        print(f"Unable to resume activity {activity}")
        print(ex)
        sys.exit(1)

def activity_restart(apis,activity):
    print(f"Attempting to restart activity {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)

    payload = {
            "input_parameters": {},
            "comment": "Restart activity ",
            "activity_name": activity,
            "force": False,
        }

    try:
        api_results = apis.post_restart(activity, payload)
        print(api_results)
        print(f"Restarted activity: {activity}")
    except Exception as ex:
        print(f"Unable to restart activity: {activity}")
        print(ex)
        sys.exit(1)

def get_sessions(apis, activity):
    print(f"Get Sessions for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"Sessions for activity: {activity}")
        sessions = sessions_result.json()
    except Exception as ex:
        print(f"Unable to get sessions for activity: {activity}")
        print(ex)
        sys.exit(1)

    if sessions is not None:
        session_list = [session["name"] for session in sessions]
        print("\n".join(session_list))
    else :
        print(f"Sessions not found for activity: {activity}")
        sys.exit(1)

def get_workflows(apis, activity):
    print(f"Get Workflows for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"Workflows for activity: {activity}")
        sessions = sessions_result.json()
    except Exception as ex:
        print(f"Unable to get workflows for activity: {activity}")
        print(ex)
        sys.exit(1)

    if sessions is not None:
        session_workflows = [session["workflows"] for session in sessions]
        workflow_list = []
        for session_workflow in  session_workflows:
            for workflow in session_workflow:
                workflow_list.append(workflow['id'])
        print("\n".join(workflow_list))
    else :
        print(f"workflows not found for activity: {activity}")
        sys.exit(1)

def activity_products(apis,activity):
    print(f"Get Products for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)

    try:
        products_result = apis.get_activity(activity)
        print(products_result)
        products = products_result.json()['products']
        print("Product Installed")
        
    except Exception as ex:
        print(f"Unable to get Products for activity: {activity}")
        print(ex)
        sys.exit(1)
    
    if products is not None:
        for product in products:
            print(f"{product['name']}: {product['version']}")
    else:
        print(f"No products found for activity: {activity}")
        sys.exit(1)


def get_history(apis, activity):
    print(f"Get history for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    try:
        history = apis.get_activity_history(activity)
    except Exception as ex:
        print(f"Unable to get history for activity: {activity}")
        print(ex)
        sys.exit(1)

    if history is not None:
        print(history)
    else :
        print("History not found for activity: {activity}")
        sys.exit(1)

def get_history_time(apis, activity):
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    try:
        history = apis.get_activity_history(activity).json()
    except Exception as ex:
        print(f"Unable to get history for activity: {activity}")
        print(ex)
        sys.exit(1)
    if history is not None:
        time = history[0]['start_time']
    else :
        print("History not found")
        sys.exit(1)

    print(f"Get history/time for activity: {activity} , time:{time}")
    try:
        history_time = apis.get_activity_history_time(activity,time)
    except Exception as ex:
        print(f"Unable to get history/time for activity: {activity} , time:{time}")
        print(ex)
        sys.exit(1)

    if history_time is not None:
        print(history_time)
    else :
        print("history/time for activity: {activity} , time:{time} not found")
        sys.exit(1)

def get_activity_session(apis, activity):
    if not apis.activity_exists(activity):
        print(f"Activity {activity} does not exist.")
        sys.exit(1)
    sessions = apis.get_activity_sessions(activity).json()
    if sessions is not None:
        session = sessions[0]["name"]
    else :
        print(f"Sessions not found for activity: {activity}")
        sys.exit(1)

    print(f"Get activity/session for activity: {activity} , session:{session}")

    try:
        session = apis.get_activity_session(activity,session)
        print(session)
    except Exception as ex:
        print(f"Unable to get activity/session for activity: {activity} , session:{session}")
        print(ex)
        sys.exit(1)

if __name__ == "__main__":
    activity = "sample"

    apis_no_token= ApiInterface_no_token()

    no_auth_list_stages(apis_no_token)
    print("*"*50)

    apis= ApiInterface()
    tok = apis.auth.token
    
    list_stages(apis)
    print("*"*50)

    list_activities(apis)
    print("*"*50)

    activity_create(apis, activity)
    print("*"*50)

    activity_run(apis,activity)
    print("*"*50)
    time.sleep(3)

    activity_abort(apis, activity)
    print("*"*50)
    time.sleep(3)

    activity_resume(apis, activity)
    print("*"*50)
    time.sleep(3)

    activity_abort(apis, activity)
    print("*"*50)
    time.sleep(3)

    activity_restart(apis, activity)
    print("*"*50)

    get_sessions(apis, activity)
    print("*"*50)

    get_workflows(apis, activity)
    print("*"*50)

    activity_products(apis, activity)
    print("*"*50)
    
    get_history(apis, activity)
    print("*"*50)

    get_history_time(apis, activity)
    print("*"*50)

    get_activity_session(apis, activity)
