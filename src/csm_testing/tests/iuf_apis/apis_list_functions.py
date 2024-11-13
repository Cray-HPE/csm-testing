import sys



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
