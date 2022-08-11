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
import os


def print_err(*a):
  print(*a, file = sys.stderr)


def get_data():
  """Get data from data.json or BSS.
  """

  hostname = socket.gethostname()

  if os.path.isfile("/etc/pit-release"):
    try:
      print_err(f"\nRunning on pit node: {hostname}. Querying data.json...")
      print_err("------------------------------------------------------------")
      with open("/var/www/ephemeral/configs/data.json", 'r') as file:
        return json.load(file)
      with open("data.json", 'r') as file:
        return json.load(file)
    except Exception as e:
      print_err(str(e))
      sys.exit(1)
  else:
    try:
      print_err(f"\nRunning on node: {hostname}. Querying BSS...")
      print_err("------------------------------------------------------------")
      command = [ "cray", "bss", "bootparameters", "list", "--format", "json" ]
      bss_proc = subprocess.Popen(command, stdout=subprocess.PIPE)
      return json.loads(bss_proc.stdout.read())
    except Exception as e:
      print_err(str(e))
      sys.exit(1)


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
  """Returns target data.
  """

  for i in range(0, ( len(desired_keys) + 1), 1):
    if i == len(desired_keys):
      return saved_data

    if i == 0:
      if desired_keys[i] in data:
        saved_data = data[desired_keys[i]]
      else:
        print(f"ERR: {data['hostname']}: {desired_keys[i]} field not present. Looking for {desired_keys}.")
        return 1

    elif i != 0:
      if saved_data and desired_keys[i] in saved_data:
        saved_data = saved_data[desired_keys[i]]
      else:
        print(f"ERR: {data['hostname']}: {desired_keys} field not present. Looking for {desired_keys}.")
        return 1


def are_valid_ip_masks(data, desired_keys):
  """Checks that IP/mask or CIDR is valid.
  """

  filtered_data = user_data(data)
  err = 0

  for blob in filtered_data:
    instance_hostname = blob['hostname']
    child_key = drill_down_data(blob, desired_keys)
    if child_key == 1: return 1

    if not child_key:
      print_err(f"ERR: {desired_keys} is not defined for: {instance_hostname}")
      err = 1

    else:
      for value in child_key:
        try:
          ipaddress.IPv4Network(value, strict=False)
        except ValueError:
          print_err(f"ERR: {instance_hostname}: '{value}' is not a valid IP/mask in {desired_keys}")
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
    if child_key == 1: return 1

    if not child_key:
      print_err(f"ERR: {desired_keys} is not defined for: {instance_hostname}: ")
      err = 1

    else:
      for item in drill_down_data(blob, desired_keys):
        if not check_hostname_syntax(item):
          print_err(f"ERR: {instance_hostname}: '{item}' is not a valid hostname in {desired_keys}")
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

  if are_valid_hostnames(data, desired_keys): return 1

  for blob in filtered_data:
    hosts_list.append(blob['hostname'])
    for value in drill_down_data(blob, desired_keys):
      target_list.append(value)
  # the following may or may not be bad configuration. TBD
  #    if value == blob['hostname']:
  #      print_err(f"WARN: {blob['hostname']}: should not reference itself in {desired_keys}")
  #      err = 1

  # Check that a host definition exists for nodes in peers/servers
  # needs to be fixed to not show items like ntp.hpecorp.net
  for i in set(target_list).difference(set(hosts_list)):
    if re.search("ncn-", i):
      print_err(f"WARN: {i}: defined in {desired_keys}, but host not defined in BSS / Basecamp")
      err = 1

  if err == 1:
    return err


def validate_ntp(data):
  """Check ntp data.
  """

  err = 0
  if are_valid_ip_masks(data, ['ntp', 'allow']): err = 1
  if are_hosts_sane(data, ['ntp', 'peers']): err = 1
  if are_hosts_sane(data, ['ntp', 'servers']): err = 1
  return err


def boot_params(data):
  """Confirm that params required for booting are
     present.
  """

  err = 0
  ncn_params = [
	"biosdevname=1",
	"console=tty0",
	"console=ttyS0,115200",
	"crashkernel=[0-9]*M",
	"ds=",
	"hostname=",
	"ifname=mgmt0",
	"ifname=mgmt1",
	"initrd=initrd.img.xz",
	"iommu=pt",
	"log_buf_len=1",
	"metal.server=",
	"pcie_ports=native",
	"psi=1",
	"rd.auto=1",
	"rd.bootif=0",
	"rd.dm=0",
	"rd.live.overlay.overlayfs=1",
	"rd.live.overlay.thin=1",
	"rd.live.overlay=LABEL=ROOTRAID",
	"rd.live.ram=0",
	"rd.live.squashimg=",
	"rd.luks.crypttab=0",
	"rd.lvm.conf=0",
	"rd.lvm=1",
	"rd.md.conf=1",
	"rd.md.waitclean=1",
	"rd.md=1",
	"rd.multipath=0",
	"rd.neednet=0",
	"rd.net.dhcp.retry=5",
	"rd.net.timeout.carrier=120",
	"rd.net.timeout.iflink=120",
	"rd.net.timeout.ifup=120",
	"rd.net.timeout.ipv6auto=0",
	"rd.net.timeout.ipv6dad=0",
	"rd.peerdns=0",
	"rd.retry=10",
	"rd.shell",
	"rd.skipfsck",
	"rd.writable.fsimg=0",
	"root=live:LABEL=SQFSRAID",
	"rootfallback=LABEL=BOOTRAID",
	"transparent_hugepage=never"
	]

  worker_params     = [ "rd.luks=0\s+" ]
  storage_params    = [ "rd.luks\s+" ]
  management_params = [ "rd.luks\s+" ]

  for blob in data:
    if "params" in blob and blob['cloud-init']['user-data'] is not None:
      hostname = blob['cloud-init']['user-data']['hostname']

      if re.search("ncn-w", hostname):
        mod_params = ncn_params
        mod_params = mod_params + worker_params

      elif re.search("ncn-s", hostname):
        mod_params = ncn_params
        mod_params = mod_params + storage_params

      elif re.search("ncn-m", hostname):
        mod_params = ncn_params
        mod_params = mod_params + management_params

      for param in mod_params:
        if not re.search(param, blob['params']):
          print_err(f"{hostname}: {param} not found in boot params")
          err = 1

  if err == 1:
    return err

if __name__ == "__main__":
  err = 0
  data = get_data()

  if len(data) != 0:
    if isinstance(data, list):
      if boot_params(data): err = 1
    if validate_ntp(data): err = 1
  else:
    print_err("No data to process. json object is empty.")

  sys.exit(err)
