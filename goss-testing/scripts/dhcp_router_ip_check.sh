#!/usr/bin/env bash
#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
# This script is meant to be run by a Goss test. It compares the inet and IP
# addresses of network interfaces against the router IP that is configured
# for it in DHCP to validate they are not the same.
#

result="PASS"
for arg in "$@"
do
  testif=$(echo $arg | sed 's/[][]//g')
  echo "Checking $testif"
  #shellcheck disable=SC2034
  inet_ip=$(ip addr show $testif | awk '/inet / {gsub(/\/.*/,"",$2); print $2}')
  #shellcheck disable=SC2034
  router_ip=$(nmap --script broadcast-dhcp-discover -e $testif 2>/dev/null | grep -i router | awk '{print $NF}')

  #shellcheck disable=SC2050
  if [[ '$inet_ip' == '$router_ip' ]];then
      echo "Test failed for $testif"
      result="FAIL"
  fi
done

echo $result
exit
