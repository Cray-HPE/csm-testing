
import sys
from .apis_activity_functions import count, total_count

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
