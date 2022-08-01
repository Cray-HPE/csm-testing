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
        print("\nRunning on pit node: %s. Querying data.json..." % (hostname))
        print("------------------------------------------------------------")
        with open("/var/www/ephemeral/configs/data.json", 'r') as file:
          return json.load(file)
    except ValuError as e:
      print_err(str(e))
  else:
    try:
      print("\nRunning on node: %s. Querying BSS..." % (hostname))
      print("------------------------------------------------------------")
      command = [ "cray", "bss", "bootparameters", "list", "--format", "json" ]
      bss_proc = subprocess.Popen(command, stdout=subprocess.PIPE)
      return json.loads(bss_proc.stdout.read())
    except ValueError as e:
      print_err("Failed to parse json.")
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
          if "ntp" in blob['cloud-init']['user-data']:
            filtered_data.append(blob['cloud-init']['user-data'].copy())

  # if we're using basecamp data
  elif isinstance(data, dict) and "Global" in data:
    for blob in data:
      if blob != "Global":
        if "ntp" in data[blob]['user-data']:
          filtered_data.append(data[blob]['user-data'].copy())
  
  return filtered_data


def is_valid_ip_mask(data, desired_key):
  """Checks that ip/mask is valid.
  """
  filtered_data = user_data(data)

  for blob in filtered_data:
    ntp_blob = blob['ntp']
    ntp_key = ntp_blob[desired_key]
    ntp_blob_hostname = blob['hostname']

    if not ntp_key:
      print_err("%s: '%s' is not defined" % (ntp_blob_hostname, desired_key))
    else:
      for ip_mask in ntp_key:
        try:
          ipaddress.IPv4Network(ip_mask, strict=False)
        except ValueError:
          print_err("%s: '%s' is not a valid ip/mask in the %s list" % (ntp_blob_hostname, ip_mask, desired_key))


def check_hostname_syntax(hostname):
  """Checks that a given hostname syntax is valid.
  """  
  if len(hostname) > 253:
      return False
  if hostname[-1] == ".":
      hostname = hostname[:-1]
  allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
  return all(allowed.match(x) for x in hostname.split("."))


def is_valid_hostnames(data, desired_key):
  """Checks that a list of hostnames is defined and valid.
  """
  filtered_data = user_data(data)

  for blob in filtered_data:
    ntp_blob = blob['ntp']
    ntp_key = ntp_blob[desired_key]
    ntp_blob_hostname = blob['hostname']

    if not ntp_key:
      print_err("ntp -> %s not defined for: %s: " % (desired_key, ntp_blob_hostname))
    else:
      for item in ntp_key:
        if not check_hostname_syntax(item):
          print_err("%s: '%s' is not a valid hostname in the %s list." % (ntp_blob_hostname, item, desired_key))


def are_values_sane(data, desired_key):
  """Checks if a value is sane for a given system.
     Needs to check more stuff.
  """
  filtered_data = user_data(data)
  target_list = []
  hosts_list = []

  is_valid_hostnames(data, desired_key)

  # Check that a node isn't using itself
  for blob in filtered_data:
    hosts_list.append(blob['hostname'])
    for value in blob['ntp'][desired_key]:
      target_list.append(value)
      if value == blob['hostname']:
        print_err("%s: should not use %s in %s" % (blob['hostname'], value, desired_key))

  # Check that a host definition exists for nodes in peers/servers
  # needs to be fixed to not show items like ntp.hpecorp.net
  for i in set(target_list).difference(set(hosts_list)):
    print_err("%s: defined in %s, but host not defined in BSS / Basecamp" % (i, desired_key))


if __name__ == "__main__":
  data = get_data()
  is_valid_ip_mask(data, "allow")
  are_values_sane(data, "peers")
  are_values_sane(data, "servers")
