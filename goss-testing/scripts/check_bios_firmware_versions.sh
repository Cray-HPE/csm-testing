#!/usr/bin/env bash
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP.
#
# MIT License
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# Tests if BIOS and firmware versions meet or exceed the required versions
# Author: Jacob Salmela <jacob.salmela@hpe.com>

set -e
set -u
set -o pipefail

usage() {
  # Generates a usage line
  # Any line startng with with a #/ will show up in the usage line
  grep '^#/' "$0" | cut -c4-
}

#/ Usage: check_bios_firmware_versions.sh [-b | -h]
#/
#/    Checks the BIOS and firmware versions of all NCNs to see if they meet or exceed the requirements for a specific version of CSM
#/
#/    -b    Also execute /root/bin/bios-baseline.sh --check
#/
#/ Note: $BMC_USERNAME and $IPMI_PASSWORD must be set prior to running this script.
#/ 

# set_vars() sets some global variables used throughout the script
function set_vars() {

  if ! { [[ -f /var/www/ephemeral/configs/data.json ]] \
  || [[ "$HOSTNAME" == *pit ]] \
  || [[ "$HOSTNAME" == ncn-m001 ]] ;}; then

    echo "Run this from the PIT or ncn-m001"
    exit 1

  fi

  # Set a sane default username
  BMC_USERNAME=${USERNAME:-$(whoami)}

  if [[ -z ${IPMI_PASSWORD} ]] || [[ -z ${BMC_USERNAME} ]]; then

    echo "\$BMC_USERNAME and \$IPMI_PASSWORD must be set"
    exit 1

  fi

  VENDOR=
  BOARD_PRODUCT=

  # if this is running in pit-mode, check dnsmasq
  if [[ $HOSTNAME == *pit* ]]; then

    # safely read in the management node names from the hosts file into an array    
    IFS=$'\n' \
      read -r -d '' \
      -a NCN_BMCS \
      < <(grep -oP 'ncn-\w\d\d\d-mgmt' /etc/dnsmasq.d/statics.conf \
          | sort -u \
          && printf '\0')

  else

    # otherwise, check the hosts file
    IFS=$'\n' \
      read -r -d '' \
      -a NCN_BMCS \
      < <(grep -oP 'ncn-\w\d\d\d-mgmt' /etc/hosts \
          | sort -u \
          && printf '\0')

  fi

  # Detect the vendor so we can determine the correct firmware version needed
  # We don't typically mix and match hardware vendors, so whatever node this is running on (usually ncn-m001)
  # it's likely that the rest of the NCNs are of the same type
  VENDOR="$(ipmitool fru \
            | awk '/Board Mfg/ && !/Date/ {print $4}')"

  BOARD_PRODUCT=$(ipmitool fru \
                  | awk '/Board Product/')
}

# check_if_bmcs_are_reachable() performs a simple port scan to see if the bmcs are reachable
check_if_bmcs_are_reachable() {
  local portscan_file="/tmp/bmc_status"
  local bmc_ip=

  echo "Checking if BMCs are reachable..."
  # port scan all the ncns in the array as a check to see if they are reachable
  echo "${NCN_BMCS[*]}" \
    | nmap -iL - \
      -oG "$portscan_file" \
      -p 443 \
      1>/dev/null 
  
  for i in "${NCN_BMCS[@]}"
  do 
    if [[ "$i" == ncn-m001-mgmt ]]; then

      echo "$i will be executed locally"
      continue
    
    fi

    if eval grep -E "$i\\.\\*Up" "$portscan_file" 1>/dev/null; then

      echo "$i is reachable over port 443"

    else


      bmc_ip=$(host "$i" \
        | awk '{print $4}')

      if eval grep -E "$bmc_ip\\.\\*Up" "$portscan_file" 1>/dev/null; then

        echo "$bmc_ip is reachable over port 443"
        continue

      fi

      echo "$i might be down, exiting..."
      exit 1

    fi
  done
}

# enable_ilo_creds() injects the username/password into the ilorest config file
enable_ilo_creds() {
  local bmc_username="$1"
  local ipmi_password="$2"
  local cfgfile="/etc/ilorest/redfish.conf"

  if command -v ilorest > /dev/null; then
    
    if [[ -f "$cfgfile" ]]; then

      chmod 600 "$cfgfile"
      
      # Enable the username, uncommenting if needed
      sed -i "/^\(#username =\).*/s/^#//" "$cfgfile"
      sed -i "s/^\(username =\).*/username = $bmc_username/" "$cfgfile"
      
      # Enable the password, uncommenting if needed
      sed -i "/^\(#password =\).*/s/^#//" "$cfgfile"
      sed -i "s/^\(password =\).*/password = $ipmi_password/" "$cfgfile"
    
    else
    
      echo "No ilorest config file found."
      exit 1
    
    fi

  else

    echo "ilorest is not installed"
    exit 1
  
  fi
}

# does_fw_meet_req() compares a firmware version to a predefined requirement
does_fw_meet_req() {
  local fw_vers="$1"
  local bmc="$2"

  if [[ "$VENDOR" = *Marvell* ]] \
    || [[ "$VENDOR" = HP* ]] \
    || [[ "$VENDOR" = Hewlett* ]]; then

    case "$fw_vers" in
      2.44) echo "=====> $bmc: FW: $fw_vers OK" ;;
      *) echo "=====> $bmc: FW: $fw_vers Unsupported (expected 2.44)"
          ;;
    esac

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]]; then

    case $fw_vers in
      12.84.09) echo "=====> $bmc: FW: $fw_vers OK" ;;
      12.84*) echo "=====> $bmc: FW: $fw_vers OK" ;;
      *) echo "=====> $bmc: FW: $fw_vers Unsupported (expected 12.84*)"
          ;;
    esac

  fi 
}

# check_firmware_version() gets a firmware version and then checks if it meets or exceeds requirements
check_firmware_version() {
  local bmc="$1"
  local bmc_username="$2"
  local ipmi_password="$3"
  local fw_vers=

  if [[ "$VENDOR" = *"Marvell"* ]] \
    || [[ "$VENDOR" = "HP"* ]] \
    || [[ "$VENDOR" = "Hewlett"* ]]; then
    
    # add the credentials to the ilorest config file
    enable_ilo_creds "$bmc_username" "$ipmi_password"

    if [[ "$HOSTNAME" == *pit* ]] \
      || [[ "$bmc" == ncn-m001-mgmt ]]; then
      
      # login to the bmc locally if we're the pit or m001 
      ilorest --nologo login 1>/dev/null

    else

      # login to the bmc
      ilorest --nologo login "$bmc" 1>/dev/null

    fi

      fw_vers=$(ilorest --nologo \
        get \
        --selector Manager \
        FirmwareVersion \
        | awk -F 'v' '{print $2}' \
        | sed '/^[[:space:]]*$/d')
      
    # logout
    ilorest --nologo logout "$bmc" 1>/dev/null

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]]; then

    if [[ "$HOSTNAME" == *pit* ]] \
    || [[ "$bmc" == ncn-m001-mgmt ]]; then

      fw_vers=$(ipmitool \
          mc info \
          | awk '/Firmware Revision/ {print $4}')

    else

      fw_vers=$(ipmitool -I lanplus \
                -U "$bmc_username" \
                -E \
                -H "$bmc" \
                mc info \
                | awk '/Firmware Revision/ {print $4}')
    fi
  fi

  # check if the versions meet or exceed the requirements
  does_fw_meet_req "$fw_vers" "$bmc"
}

# does_bios_meet_req() checks a version string to see if it meets or exceeds the requirement
does_bios_meet_req() {
  local bios_vers="$1"

  if [[ "$VENDOR" = *"Marvell"* ]] \
    || [[ "$VENDOR" = "HP"* ]] \
    || [[ "$VENDOR" = "Hewlett"* ]]; then

    if [[ "$BOARD_PRODUCT" == *"DL325"* ]]; then

      case "$bios_vers" in
        A43) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
        *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected A43)"
            ;;
      esac

    elif [[ "$BOARD_PRODUCT" == *"DL385"* ]]; then

      case "$bios_vers" in
        # these are the versions that are compatible
        A42) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
        *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected A42)"
            ;;
      esac

    fi

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]]; then

    case "$bios_vers" in
      C17) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
      C21) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
      *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected C17 or C21)"
          ;;
    esac
  fi
}

# check_bios_version() gets a BIOS version and then checks if it meets or exceeds requirements
check_bios_version() {
  local bmc="$1"
  local bmc_username="$2"
  local ipmi_password="$3"
  local bios_vers=

  if [[ "$VENDOR" = *"Marvell"* ]] \
    || [[ "$VENDOR" = "HP"* ]] \
    || [[ "$VENDOR" = "Hewlett"* ]]; then

    # add the credentials to the ilorest config file
    enable_ilo_creds "$bmc_username" "$ipmi_password"

    if [[ "$HOSTNAME" == *pit* ]] \
      || [[ "$bmc" == ncn-m001-mgmt ]]; then
      
      # login to the bmc locally if we're the pit or m001 
      ilorest --nologo login 1>/dev/null

    else

      # login to the bmc
      ilorest --nologo login "$bmc" 1>/dev/null

    fi

      # get the bios version
      bios_vers=$(ilorest --nologo \
        get \
        --selector System \
        Oem/Hpe/Bios/Current/Family \
        | awk -F '=' '{print $2}' \
        | sed '/^[[:space:]]*$/d')

    # logout
    ilorest --nologo logout "$bmc" 1>/dev/null

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]];then

    if [[ "$HOSTNAME" == *pit* ]] \
    && [[ "$bmc" == ncn-m001-mgmt ]]; then

      # Extract the IP from ncn-m001's BMC, which is configured with a site IP
      bmc=$(ipmitool lan print \
          | awk '$1 ~ /^IP$/ && !/Source/ {print $4}' \
          | sed '/\n/!s/[0-9.]\+/\n&\n/;/^\([0-9]\{1,3\}\.\)\{3\}[0-9]\{1,3\}\n/P;D')

    fi

    # get the bios version from the redfish API
    bios_vers=$(curl "https://$bmc/redfish/v1/Systems/Self" \
        --insecure \
        -L \
        -s \
        -u "${bmc_username}":"${ipmi_password}" \
        | jq .BiosVersion \
        | tr -d '"')

  fi

  # check if the versions meet or exceed the requirements
  does_bios_meet_req "$bios_vers" "$bmc"
}

USAGE=N
BASELINE=N
while getopts "bh" opt; do
  case ${opt} in
    h)
      USAGE=Y
      ;;
   b)
      BASELINE=Y
      ;;
   \? )
     usage
     echo
     echo "Invalid option: -$OPTARG" 1>&2
     exit 1
     ;;
  esac
done
shift $((OPTIND -1))

if [[ $USAGE = Y ]]; then
  usage
  exit 0
fi

# Setup variables
set_vars

# Check if the BMCs are reachable before continuing
check_if_bmcs_are_reachable

# for each BMC
for i in "${NCN_BMCS[@]}"
do 
  
  check_firmware_version "$i" \
    "$BMC_USERNAME" \
    "$IPMI_PASSWORD"

  check_bios_version "$i" \
    "$BMC_USERNAME" \
    "$IPMI_PASSWORD"
    
done

if [[ $BASELINE = Y ]]; then
  /root/bin/bios-baseline.sh --check
  exit $?
fi

# We exit 0 because goss not only checks for our return code, but also checks stdout
# to see if any BIOS or firmware versions are unsupported
exit 0
