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

  # Allow for output of documentation when needed
  rc=0

  DL325_FW="2.46"
  DL385_FW="2.46"

  DL325_BIOS="v2.52"
  DL385_BIOS="v2.52"

  # Taken from HFP-firmware-22.05 but leaving here for reference in this code
  # Appropriate versions to use for CSM v1.2 or HPCM as of 2/2/2022 unless otherwise indicated by your
  # software installation manual:

  #     HPE_EX425 4 node compute blades -   BIOS 1.6.3, MTN_CCNC 1.7.6.4 Node Controller (NC)
  #     HPE_EX235N                          BIOS 1.2.1, MTN_CCNC 1.7.6.4 Node Controller (NC)
  #     HPE_EX235a                          BIOS 1.3.6, MTN_CCNC 1.7.6.4 Node Controller (NC)
  #     HPE_EX420				            BIOS 1.0.0, MTN_CCNC 1.7.6.4 Node Controller (NC)
  #     HPE_EX235_NV                        FPGA NVIDIA 2.7.1
  #     HPE_XL675d-Gen10Plus                BIOS 2.52, HPE_ILO5 version 2.46
  #     HPE_XL645d-Gen10Plus                BIOS 2.52, HPE_ILO5 version 2.46
  #     HPE_DL325_A43                       BIOS 2.52, HPE_ILO5 version 2.46
  #     HPE_DL385_A42                       BIOS 2.52, HPE_ILO5 version 2.46
  #     GB_SVR_1264UP_C17_C21 - Gigabyte NCN's, BIOS/BMC package C27  (Note: required upgrade prior to install of Shasta 1.4.0 or later)
  #     GB_SVR_5264_C20 - Gigabyte UAN's, AN's BIOS/BMC package C27
  #     GB_SVR_3264_C20 - Gigabyte Compute nodes, BIOS/BMC package C27

  # Allow for output of documentation when needed, 1 is yes, 0 is no
  DOCS=0
  # Links for documentation
  FIRMWARE_DOCS=
  BIOS_DOCS=
  CSM_DOCS="https://github.com/Cray-HPE/docs-csm/blob/release/1.2/operations/index.md#update-firmware-with-fas"
  HFP_DOCS="Documentation in the HFP-firmware tarball"

  # Set a sane default username
  BMC_USERNAME=${USERNAME:-$(whoami)}

  if [[ -z ${IPMI_PASSWORD} ]] || [[ -z ${BMC_USERNAME} ]]; then

    echo "\$BMC_USERNAME and \$IPMI_PASSWORD must be set"
    exit 1

  fi

  # get the fru info once since ipmi is slow
  echo "Checking vendor..."
  fru=
  fru="$(ipmitool fru)"

  VENDOR=
  BOARD_PRODUCT=

  # Detect the vendor so we can determine the correct firmware version needed
  # We don't typically mix and match hardware vendors, so whatever node this is running on (usually ncn-m001)
  # it's likely that the rest of the NCNs are of the same type
  VENDOR="$(echo "$fru" \
            | awk '/Board Mfg/ && !/Date/ {print $4}')"

  BOARD_PRODUCT=$(echo "$fru" \
                  | awk '/Board Product/')

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

      >&2 echo "$i might be down..."

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

   if [[ "$BOARD_PRODUCT" == *"DL325"* ]]; then
      case "$fw_vers" in
        "${DL325_FW}") echo "=====> $bmc: FW: $fw_vers OK" ;;
        *) echo "=====> $bmc: FW: $fw_vers Unsupported (expected ${DL325_FW})"
          DOCS=1
          rc=1
            ;;
      esac
    elif [[ "$BOARD_PRODUCT" == *"DL385"* ]]; then
      case "$fw_vers" in
        "${DL385_FW}") echo "=====> $bmc: FW: $fw_vers OK" ;;
        *) echo "=====> $bmc: FW: $fw_vers Unsupported (expected ${DL385_FW})"
          DOCS=1
          rc=1
            ;;
      esac
    fi

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]]; then

    case $fw_vers in
      12.84.09) echo "=====> $bmc: FW: $fw_vers OK" ;;
      12.84*) echo "=====> $bmc: FW: $fw_vers OK" ;;
      *) echo "=====> $bmc: FW: $fw_vers Unsupported (expected 12.84*)"
         DOCS=1
         rc=1
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

    # get the firmware version, filter on the know name "iLO 5" 
    fw_vers=$(ilorest --nologo \
      get \
      Version \
      --selector SoftwareInventory \
      --filter Name="iLO 5" \
      | awk -F '=' '{print $2}' \
      | sed '/^[[:space:]]*$/d' \
      | awk '{print $1}')


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
        "${DL325_BIOS}") echo "=====> $bmc: BIOS: $bios_vers OK" ;;
        *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected ${DL325_BIOS})"
           DOCS=1
           rc=1
            ;;
      esac

    elif [[ "$BOARD_PRODUCT" == *"DL385"* ]]; then

      case "$bios_vers" in
        # these are the versions that are compatible
        "${DL385_BIOS}") echo "=====> $bmc: BIOS: $bios_vers OK" ;;
        *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected ${DL385_BIOS})"
           DOCS=1
           rc=1
            ;;
      esac

    fi

  elif [[ "$VENDOR" == "GIGA"*"BYTE" ]]; then

    case "$bios_vers" in
      C17) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
      C21) echo "=====> $bmc: BIOS: $bios_vers OK" ;;
      *) echo "=====> $bmc: BIOS: $bios_vers Unsupported (expected C17 or C21)"
         DOCS=1
         rc=1
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

    # get the bios version, filter on the know name "System ROM" 
    bios_vers=$(ilorest --nologo \
      get \
      Version \
      --selector SoftwareInventory \
      --filter Name="System ROM" \
      | awk -F '=' '{print $2}' \
      | awk '{print $2}' \
      | sed '/^[[:space:]]*$/d')

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

  if [[ "$VENDOR" = *"Marvell"* ]] \
    || [[ "$VENDOR" = "HP"* ]] \
    || [[ "$VENDOR" = "Hewlett"* ]]; then
    if [[ "$i" == *"ncn-m001"* ]]; then
      # login locally
      ilorest --nologo login 1>/dev/null
    else
      # login to the remote bmc 
      ilorest --nologo login "$i" 1>/dev/null
    fi

  fi

  check_firmware_version "$i" \
    "$BMC_USERNAME" \
    "$IPMI_PASSWORD"

  check_bios_version "$i" \
    "$BMC_USERNAME" \
    "$IPMI_PASSWORD"

  if [[ "$VENDOR" = *"Marvell"* ]] \
    || [[ "$VENDOR" = "HP"* ]] \
    || [[ "$VENDOR" = "Hewlett"* ]]; then
    ilorest --nologo logout 1>/dev/null
  fi

done

if [[ $BASELINE = Y ]]; then
  /root/bin/bios-baseline.sh --check || rc=1
fi

if [[ "$DOCS" -ne 0 ]]; then
  echo "See the following for documentation on firmware/BIOS updates:"
  if [[ -n "${CSM_DOCS}" ]];then echo "- ${CSM_DOCS}";fi
  if [[ -n "${HFP_DOCS}" ]];then echo "- ${HFP_DOCS}";fi
  if [[ -n "${FIRMWARE_DOCS}" ]];then echo "- ${FIRMWARE_DOCS}";fi
  if [[ -n "${BIOS_DOCS}" ]];then echo "- ${BIOS_DOCS}";fi
fi

# We exit 0 because goss not only checks for our return code, but also checks stdout
# to see if any BIOS or firmware versions are unsupported
[[ $rc -eq 0 ]] && echo "PASS" || echo "FAIL"
exit $rc
