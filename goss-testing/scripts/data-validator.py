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


def get_data():
  hostname = socket.gethostname()
  try:
    if re.search("pit", hostname):
      print("Running on pit node: %s. Querying data.json..." % (hostname))
      json_data_obj = open("/var/www/ephemeral/configs/data.json", 'r')
      json_data = json_data_obj.read()
      json_data_obj.close()
    else:
      print("Running on node: %s. Querying BSS..." % (hostname))
      command = [ "cray", "bss", "bootparameters", "list", "--format", "json" ]
      bss_proc = subprocess.Popen(command, stdout=subprocess.PIPE)
      json_data = bss_proc.stdout.read()
  except subprocess.CalledProcessError as e:
    print(e.stderr)

  try:
    json_serialized = json.loads(json_data)
    return json_serialized
  except ValueError as e:
   print("Failed to parse json.")
   print(e)


def user_data(data):
  # returns the 'user-data' blob from BSS or basecamp
  filtered_data = []

  # if we're using BSS data
  if isinstance(data, list):
    for blob in data:
        if isinstance(blob['cloud-init']['user-data'], dict):
          if "ntp" in blob['cloud-init']['user-data']:
            filtered_data.append(blob['cloud-init']['user-data'].copy())

  # if we're using basecamp data
  elif isinstance(data, dict):
    for blob in data:
      if blob != "Global":
        if "ntp" in data[blob]['user-data']:
          filtered_data.append(data[blob]['user-data'].copy())
  
  return filtered_data


def is_valid_hostname(hostname):
    if len(hostname) > 253:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def is_valid_cidrs(data, desired_key):
  filtered_data = user_data(data)

  for blob in filtered_data:
    ntp_blob = blob['ntp']
    ntp_key = ntp_blob[desired_key]
    ntp_blob_hostname = blob['hostname']

    if not ntp_key:
      print("%s: '%s' is not defined" % (ntp_blob_hostname, desired_key))
      next

    for cidr in ntp_key:
      try:
        ipaddress.ip_network(cidr)
      except ValueError:
        print("%s: '%s' is not a valid cidr in the %s list" % (ntp_blob_hostname, cidr, desired_key))


def is_valid_hostnames(data, desired_key):
  filtered_data = user_data(data)

  for blob in filtered_data:
    ntp_blob = blob['ntp']
    ntp_key = ntp_blob[desired_key]
    ntp_blob_hostname = blob['hostname']

    if not ntp_key:
      print("ntp -> %s not defined for: %s: " % (desired_key, ntp_blob_hostname))
      next

    for item in ntp_key:
      if is_valid_hostname(item):
        pass
      else:
        print("%s: '%s' is not a valid hostname in the %s list." % (ntp_blob_hostname, item, desired_key))


if __name__ == "__main__":
  data = get_data()
  is_valid_cidrs(data, "allow")
  is_valid_hostnames(data, "servers")
  is_valid_hostnames(data, "peers")

