import sys
import copy
import requests


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
            "input_parameters": { media_dir: media_dir,
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
