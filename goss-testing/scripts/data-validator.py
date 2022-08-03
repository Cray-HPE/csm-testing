#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
import re
import subprocess
import sys
import ipaddress
import socket
import json


def print_err(*a):
  print(*a, file = sys.stderr)


def get_data():
  """Get data from data.json or BSS.
  """
  hostname = socket.gethostname()

  if re.search("pit", hostname):
    try:
      print_err("\nRunning on pit node: %s. Querying data.json..." % (hostname))
      print_err("------------------------------------------------------------")
      with open("/var/www/ephemeral/configs/data.json", 'r') as file:
        return json.load(file)
    except Exception as e:
      print_err(str(e))
      return 1
  else:
    try:
      print_err("\nRunning on node: %s. Querying BSS..." % (hostname))
      print_err("------------------------------------------------------------")
      command = [ "cray", "bss", "bootparameters", "list", "--format", "json" ]
      bss_proc = subprocess.Popen(command, stdout=subprocess.PIPE)
      return json.loads(bss_proc.stdout.read())
    except Exception as e:
      print_err(str(e))
      return 1


def user_data(data):
  """Returns the 'user-data' blobs from data.json or BSS.
  """
  filtered_data = []

  # if we're using BSS data
  if isinstance(data, list):
    for blob in data:
        if isinstance(blob['cloud-init']['user-data'], dict):
          filtered_data.append(blob['cloud-init']['user-data'])

  # if we're using basecamp data
  elif isinstance(data, dict) and "Global" in data:
    for blob in data:
      if blob != "Global":
        filtered_data.append(data[blob]['user-data'])
  
  return filtered_data


def drill_down_data(data, desired_keys):
  for i in range(0, ( len(desired_keys) + 1), 1):
    if i == len(desired_keys):
      return saved_data
    if i == 0:
      saved_data = data[desired_keys[i]]
    if i != 0:
      saved_data = saved_data[desired_keys[i]]


def are_valid_ip_masks(data, desired_keys):
  """Checks that ip/mask or cidr is valid.
  """
  filtered_data = user_data(data)
  err = 0

  for blob in filtered_data:
    instance_hostname = blob['hostname']
    child_key = drill_down_data(blob, desired_keys)

    if not child_key:
      print_err("ERR: %s is not defined for: %s: " % (desired_keys, instance_hostname))
      err = 1
    else:
      for value in child_key:
        try:
          ipaddress.IPv4Network(value, strict=False)
        except ValueError:
          print_err("ERR: %s: '%s' is not a valid ip/mask in %s" % (instance_hostname, value, desired_keys))
          err = 1
  if err == 1:
    return err

def check_hostname_syntax(hostname):
  """Checks that a given hostname syntax is valid.
  """  
  if len(hostname) > 253:
      return False
  if hostname[-1] == ".":
      hostname = hostname[:-1]
  allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
  return all(allowed.match(x) for x in hostname.split("."))


def are_valid_hostnames(data, desired_keys):
  """Checks that a list of hostnames is defined and valid.
  """
  filtered_data = user_data(data)
  err = 0

  for blob in filtered_data:
    instance_hostname = blob['hostname']
    child_key = drill_down_data(blob, desired_keys)

    if not child_key:
      print_err("ERR: %s is not defined for: %s: " % (desired_keys, instance_hostname))
      err = 1
    else:
      for item in drill_down_data(blob, desired_keys):
        if not check_hostname_syntax(item):
          print_err("ERR: %s: '%s' is not a valid hostname in %s" % (instance_hostname, item, desired_keys))
          err = 1
  return err


def are_hosts_sane(data, desired_keys):
  """Checks if a value is sane for a given system.
     Needs to check more stuff.
  """
  filtered_data = user_data(data)
  target_list = []
  hosts_list = []
  err = 0

  if are_valid_hostnames(data, desired_keys):
    err = 1

  for blob in filtered_data:
    hosts_list.append(blob['hostname'])
    for value in drill_down_data(blob, desired_keys):
      target_list.append(value)
  # the following may or may not be bad configuration. TBD
  #    if value == blob['hostname']:
  #      print_err("WARN: %s: should not reference itself in %s" % (blob['hostname'], desired_keys))
  #      err = 1

  # Check that a host definition exists for nodes in peers/servers
  # needs to be fixed to not show items like ntp.hpecorp.net
  for i in set(target_list).difference(set(hosts_list)):
    if re.search("ncn-", i):
      print_err("WARN: %s: defined in %s, but host not defined in BSS / Basecamp" % (i, desired_keys))
      err = 1

  if err == 1:
    return err


def validate_ntp(data):
  err = 0
  if are_valid_ip_masks(data, ['ntp', 'allow']):
    err = 1
  if are_valid_ip_masks(data, ['ntp', 'allow']):
    err = 1
  if are_hosts_sane(data, ['ntp', 'servers']):
    err = 1
  return err


def boot_params(data):
  params_list = []
  another_list = []

  for blob in data:
    if "params" in blob:
      params_list += blob['params'].split()

  params_list = set(params_list)
  for i in sorted(params_list, key = str):
    another_list += i.split("=")

  another_list = set(another_list)
  for j in sorted(another_list, key = str):
    print(j)

if __name__ == "__main__":
  data = get_data()
  result = validate_ntp(data)
  sys.exit(result)
  #boot_params(data)
