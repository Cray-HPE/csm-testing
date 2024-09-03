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
This script executes iuf apis testing.
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
import shutil

FOLDER_NAME = "dummy-1.0.0" 
MEDIA_DIR = "/etc/cray/upgrade/csm/automation-tests"
tar_dir = "/opt/cray/tests/install/ncn/scripts/python/iuf_run_setup"

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
    global count , total_count 
    print("TEST CASE: w/o security API call: Try Api Call without token")
    stages = None
    try :
        stages = apis.get_stages()
    except Exception as e:
        print(f"INFO: {e}")
        count += 1
        
    if stages is not None:
        print("ERROR: Api Working without token")
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def list_stages(apis):
    global count , total_count 
    print("TEST CASE: List Stages")
    try:
        stage_result = apis.get_stages()
        print(stage_result)
        stages = stage_result.json()
    except Exception as ex:
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    
    if stages is not None:
        stage_list = [stage["name"] for stage in stages['stages']]
        print("\n".join(stage_list))
        count += 1
    else:
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    

def list_activities(apis):
    global count , total_count
    print("TEST CASE: List Activities")
    try:
        activities_result = apis.get_activities()
        print(activities_result)
        count += 1
        activities = activities_result.json()
    except Exception as ex:
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    if activities is not None:
        act_list = sorted([act["name"] for act in activities])
        print("\n".join(act_list)) 

def activity_create(apis,activity):
    global count , total_count
    print("TEST CASE: Create Activity")
    print(f"INFO: Attempting to create activity {activity}")
    payload = {
        "input_parameters": {},
        "name": activity
    }

    if not apis.activity_exists(activity):
        try:
            print(apis.post_activity(payload))
            print(f"INFO: Created activity: {activity}")
            count += 1
        except Exception as ex:
            print(f"ERROR: Unable to create activity: {activity}")
            print(f"ERROR: {ex}")
            print("~"*50)
            print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
            print("~"*50)
            sys.exit(1)
    else:
        print("WARNING: Skipping the test case: Create Activity")
        print(f"INFO: Activity {activity} already exists")

def activity_run(apis,activity,media_dir):
    global count , total_count
    print("TEST CASE: Run Activity")
    print(f"INFO: Attempting to run activity {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    payload = {
            "input_parameters": { media_dir: '/etc/cray/upgrade/csm/automation-tests',
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
    print("TEST CASE: Patch Activity")
    try:
        print(apis.post_activity_history_run(activity, payload))
        count += 1 
        print(f"INFO: Activity {activity} is started")

        # Generate site_parameters and patch the activity.
        patched_payload = copy.deepcopy(payload)
        #patched_payload["site_parameters"] = self.site_conf.site_params

        # Remove the "force" key from input_parameters for the patched
        # activity.
        patched_payload["input_parameters"].pop("force", None)
        print(f"INFO: Patch activity: {activity}")
        print(apis.patch_activity(activity, patched_payload))
        count += 1

    except Exception as ex:
        print(f"ERROR: Unable to run activity {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def activity_abort(apis,activity):
    global count , total_count
    print("TEST CASE: Abort Activity")
    print(f"INFO: Attempting to abort activity {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    payload = {
            "input_parameters": {},
            "name": activity,
            "comment": "sending an abort",
            "force": None,
        }
    try:
        print(apis.abort_activity(activity, payload))
        print(f"INFO: Aborted activity: {activity}")
        count += 1
    except requests.ReadTimeout:
        print("ERROR: Timed out sending an abort request.")
        print(f"ERROR: Ensure the argo workflow for {activity} is not running.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    except Exception as ex:
        print(f"ERROR: Unable to abort activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def activity_resume(apis, activity):
    global count , total_count
    print("TEST CASE: Resume Activity")
    print(f"INFO: Attempting to resume activity {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
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
        print(f"INFO: Resumed activity: {activity}")
        count += 1
    except Exception as ex:
        print(f"ERROR: Unable to resume activity {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def activity_restart(apis,activity):
    global count , total_count
    print("TEST CASE: Restart Activity")
    print(f"INFO: Attempting to restart activity {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
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
        print(f"INFO: Restarted activity: {activity}")
        count += 1
    except Exception as ex:
        print(f"ERROR: Unable to restart activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def get_sessions(apis, activity):
    global count , total_count
    print("TEST CASE: Get Sessions")
    print(f"INFO: Get Sessions for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"INFO: Sessions for activity: {activity}")
        sessions = sessions_result.json()
    except Exception as ex:
        print(f"ERROR: Unable to get sessions for activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    if sessions is not None:
        session_list = [session["name"] for session in sessions]
        print("\n".join(session_list))
        count += 1
    else :
        print(f"ERROR: Sessions not found for activity: {activity}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def get_workflows(apis, activity):
    global count , total_count
    print("TEST CASE: Get Workflows")
    print(f"INFO: Get Workflows for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    try:
        sessions_result = apis.get_activity_sessions(activity)
        print(sessions_result)
        print(f"INFO: Workflows for activity: {activity}")
        sessions = sessions_result.json()
    except Exception as ex:
        print(f"ERROR: Unable to get workflows for activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    if sessions is not None:
        session_workflows = [session["workflows"] for session in sessions]
        workflow_list = []
        for session_workflow in  session_workflows:
            for workflow in session_workflow:
                workflow_list.append(workflow['id'])
        print("\n".join(workflow_list))
        count += 1
    else :
        print(f"ERROR: workflows not found for activity: {activity}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def activity_products(apis,activity):
    global count , total_count
    print("TEST CASE: Get Products")
    print(f"INFO: Get Products for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    try:
        products_result = apis.get_activity(activity)
        print(products_result)
        products = products_result.json()['products']
        print("Product Installed")
        
    except Exception as ex:
        print(f"ERROR: Unable to get Products for activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    
    if products is not None:
        for product in products:
            print(f"{product['name']}: {product['version']}")
        count += 1
    else:
        print(f"ERROR: No products found for activity: {activity}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)


def get_history(apis, activity):
    global count , total_count
    print("TEST CASE: Get History")
    print(f"INFO: Get history for activity: {activity}")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    try:
        history = apis.get_activity_history(activity)
    except Exception as ex:
        print(f"ERROR: Unable to get history for activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    if history is not None:
        print(history)
        count += 1
    else :
        print("ERROR: History not found for activity: {activity}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def get_history_time(apis, activity):
    global count , total_count
    print("TEST CASE: Get History/time")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    try:
        history = apis.get_activity_history(activity).json()
    except Exception as ex:
        print(f"ERROR: Unable to get history for activity: {activity}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    if history is not None:
        time = history[0]['start_time']
    else :
        print("ERROR: History not found")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    print(f"INFO: Get history/time for activity: {activity} , time:{time}")
    try:
        history_time = apis.get_activity_history_time(activity,time) 
    except Exception as ex:
        print(f"ERROR: Unable to get history/time for activity: {activity} , time:{time}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    if history_time is not None:
        print(history_time)
        count += 1
    else :
        print("ERROR: history/time for activity: {activity} , time:{time} not found")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

def get_activity_session(apis, activity):
    global count , total_count
    print("TEST CASE: Get Activity Session")
    if not apis.activity_exists(activity):
        print(f"ERROR: Activity {activity} does not exist.")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)
    sessions = apis.get_activity_sessions(activity).json()
    if sessions is not None:
        session = sessions[0]["name"]
    else :
        print(f"ERROR: Sessions not found for activity: {activity}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

    print(f"INFO: Get activity/session for activity: {activity} , session:{session}")

    try:
        session = apis.get_activity_session(activity,session)
        print(session)
        count += 1 
    except Exception as ex:
        print(f"ERROR: Unable to get activity/session for activity: {activity} , session:{session}")
        print(f"ERROR: {ex}")
        print("~"*50)
        print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
        print("~"*50)
        sys.exit(1)

if __name__ == "__main__":

    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        print(f"INFO: Directory {MEDIA_DIR} created successfully.")
    except OSError as e:
        print(f"ERROR: Failed creating directory {MEDIA_DIR}: {e}")
        sys.exit(1)
    
    try:
        shutil.copy(f"{tar_dir}/{FOLDER_NAME}.tar.gz", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/product_vars.yaml", MEDIA_DIR)
        shutil.copy(f"{tar_dir}/management-bootprep.yaml", MEDIA_DIR)
        print(f"INFO: Files copied successfully to {MEDIA_DIR}.")
    except IOError as e:
        print(f"ERROR: Failed copying files: {e}")
        sys.exit(1)


    count = 0
    total_count = 15
    activity = sys.argv[1]
    print("INFO: This is the activity: {}".format(activity))

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

    activity_run(apis,activity,MEDIA_DIR)
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
    print("*"*50)

    print("~"*50)
    print("INFO: Total test cases passed: {} test cases skipped: {}".format(count,total_count-count))
    print("~"*50)