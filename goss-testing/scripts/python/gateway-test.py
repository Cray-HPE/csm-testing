#! /usr/bin/env python3


import json
import sys
import logging
import requests
import urllib3
import yaml
import base64
import subprocess
import os.path

try:
  from kubernetes import client, config
except:
  client = None
  config = None


# Some very light logging.
LOG_LEVEL=logging.INFO

# Start logging
logging.basicConfig(filename='/tmp/' + sys.argv[0].split('/')[-1] + '.log',  level=LOG_LEVEL)
logging.info("Starting up")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GWException(Exception):
    """
    This is the base exception for all custom exceptions that can be raised from
    this application.
    """

def reachable(service):
    ret = os.system("ping -q -o -c 3 -W 3000 {} >/dev/null".format(service))
    if ret != 0:
        print("{} is NOT reachable".format(service))
        return False
    else:
        print("{} is reachable".format(service))
        return True

def get_admin_secret(k8sClientApi):
    """
    Get the admin secret from k8s for the api gateway - command line equivalent is:
    #`kubectl get secrets admin-client-auth -o jsonpath='{.data.client-secret}' | base64 -d`
    """

    try:
        sec = k8sClientApi.read_namespaced_secret("admin-client-auth", "default").data
        adminSecret = base64.b64decode(sec['client-secret'])
    except Exception as err:
        logging.error(f"An unanticipated exception occurred while retrieving k8s secrets {err}")
        raise GWException from None

    return adminSecret

def get_access_token(adminSecret, tokenNet, nmn_override):

    # get an access token from keycloak
    payload = {"grant_type":"client_credentials",
               "client_id":"admin-client",
               "client_secret":adminSecret}

    if TOKEN_NET == "nmnlb" and nmn_override:
        tokendomain = "api-gw-service-nmn.local"
    else:
        tokendomain = "auth.{}.{}".format(TOKEN_NET, SYSTEM_DOMAIN)

    url = "https://{}/keycloak/realms/shasta/protocol/openid-connect/token".format(tokendomain)
 
    if not reachable(tokendomain):
        return None
   
    try: 
      r = requests.post(url, data = payload, verify = False)
    except Exception as err:
        print("{}".format(err))
        logging.error(f"An unanticipated exception occurred while retrieving gateway token {err}")
        raise GWException from None

    # if the token was not provided, log the problem
    if r.status_code != 200:
        print("Error retrieving gateway token:  keycloak return code: {} text: {}".format(r.status_code,r.text))
        logging.error(f"Error retrieving gateway token: keycloak return code: {r.status_code}"
            f" text: {r.text}")
        raise GWException from None

    # pull the access token from the return data
    token = r.json()['access_token']

    print("Token successfully retrieved at {}\n".format(url))

    return token


def get_vs(service):

    result = None	
    try:
        logging.debug("Getting gateways for service {}.".format(service['name']))
        command_line = ['kubectl', 'get', 'vs', service['name'], '-n', service['namespace'], '-o', 'yaml']
        result = subprocess.check_output(command_line, stderr=subprocess.STDOUT).decode("utf8")
        logging.debug(result)

    except subprocess.CalledProcessError as err:
        logging.error(f"Could not get virtual service. Got exit code {err.returncode}. Msg: {err.output}")

    return result

def get_vs_gateways(vsyaml):

    vs = yaml.safe_load(vsyaml)
    gws = vs['spec']['gateways']
    return gws

if __name__ == '__main__':

    numarg = len(sys.argv)
    test_defn_file = "./gateway-test-defn.yaml"

    if numarg < 3: 
      print("Usage: {} <system-domain> <token-network>".format(sys.argv[0]))
      print("       {} <system-domain> <token-network> [<admin-secret>]".format(sys.argv[0]))
      logging.critical("Wrong number of arguments passed. Args = {}.".format(sys.argv))
      sys.exit(1)

    if not os.path.exists(test_defn_file):
      print("{} does not exist".format(test_defn_file))
      logging.critical("{} does not exist.".format(test_defn_file))
      sys.exit(1)

    SYSTEM_DOMAIN = (sys.argv[1]).lower() 
    TOKEN_NET = (sys.argv[2]).lower()
    if numarg == 4:
      ADMIN_SECRET = sys.argv[3]

    with open(test_defn_file, 'r') as f:
        svcs = yaml.load(f, Loader=yaml.FullLoader)

    if not any(d['name'] == TOKEN_NET for d in svcs['networks']):
      print("{} is not a valid network".format(sys.argv[2]))
      logging.critical("{} is not a valid network".format(sys.argv[2]))
      sys.exit(1)

    # initialize k8s if we are running from an NCN
    if os.path.exists("/bin/craysys"):
      config.load_kube_config()
      k8sClientApi = client.CoreV1Api()
      ADMIN_SECRET = get_admin_secret(k8sClientApi)

    mytok = get_access_token(ADMIN_SECRET, TOKEN_NET, svcs['use-api-gw-override'])
 
    if not mytok:
      sys.exit(1)

    for net in svcs['networks']:

      netname = net['name'].lower()
      if netname.lower() == "nmnlb" and svcs['use-api-gw-override']:
         domain = "api-gw-service-nmn.local"
      else:
         domain = "api.{}.{}".format(netname, SYSTEM_DOMAIN)

      if not reachable(domain):
         continue 

      print("\n------------- {} -------------------".format(domain))

      for i in range(len(svcs['ingress_api_services'])):
        svcname = svcs['ingress_api_services'][i]['name']
        svcpath = svcs['ingress_api_services'][i]['path']
        svcport = svcs['ingress_api_services'][i]['port']
        svcexp = svcs['ingress_api_services'][i]['expected-result']

        if svcport == 443:
            scheme = "https"
        else:
            scheme = "http"

        url = scheme + "://" + domain + "/" + svcpath 

        # Getting the gateways from the Virtual Service definitions
        # This can only be done if we are running the tests from an NCN
        # The best way I could find to determine if we are running on an NCN is to see if craysys is installed.
        # There may be a better way
        if os.path.exists("/bin/craysys"):
            vsyaml = get_vs(svcs['ingress_api_services'][i])
            if vsyaml is None:
               print("SKIP - [" + svcname + "]: " + url + " - virtual service not found")
               continue
        
            svcgws = get_vs_gateways(vsyaml)

        # Otherwise, we get the gateways from the test defininition file (which may become stale)
        else:
            if "gateways" in svcs['ingress_api_services'][i]:
                svcgws = svcs['ingress_api_services'][i]['gateways']
            else:
                print("SKIP - [" + svcname + "]: " + url + " - gateways not found")
                continue

        if net['gateway'] not in svcgws:
          svcexp = 404
        # if the token we have does not match the network we are testing, we expect a 403
        # CMN tokens will work with NMN and vice versa, because they are using the same gateway in 1.2.
        elif TOKEN_NET == "cmn" and netname != TOKEN_NET and netname != "nmnlb":
          svcexp = 403
        elif TOKEN_NET == "nmnlb" and netname != TOKEN_NET and netname != "cmn":
          svcexp = 403
        elif TOKEN_NET not in ["cmn","nmnlb"] and TOKEN_NET != netname:
          svcexp = 403

        headers = {
            'Authorization': "Bearer " + mytok
        }

   
        try:    
            response = requests.request("GET", url, headers=headers, verify = False)
        except Exception as err:
            print("{}".format(err))
            logging.error(f"An unanticipated exception occurred while retrieving k8s secrets {err}")
            break
    
        if response.status_code == svcexp:
            print("PASS - [" + svcname + "]: " + url + " - " + str(response.status_code))
        else:
            print("FAIL - [" + svcname + "]: " + url + " - " + str(response.status_code))

