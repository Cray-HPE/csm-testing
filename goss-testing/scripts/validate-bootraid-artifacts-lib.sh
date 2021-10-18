#!/usr/bin/env bash
set -eu
set -o pipefail

ARTIFACT_S3_PATH="${1}"

if [[ -z ${ARTIFACT_S3_PATH} ]]; then
	echo "Path to a kernel or initrd in S3 is required as an argument"
	# shellcheck disable=SC2154 # this is just an example command
	echo "Try 'cray bss bootparameters list --hosts ${xname} | awk '/kernel = /'"
	echo "and 'cray bss bootparameters list --hosts ${xname} | awk '/initrd = /'"
	exit 1
fi

# Stuff to cleanup on exit
REBOOT_NEEDED="false"

pit_check() {
	if [[ $HOSTNAME == *pit* ]]; then
		return 0
	else
		return 1
	fi
}

if ! eval pit_check; then
	# get the mount directory as it can vary between vintages: CSM 0.9.X uses /metal/boot, CSM 1.0 uses /metal/recovery
	BOOTRAID=$(awk '/LABEL=BOOTRAID/ {print $2}' /etc/fstab.metal)
else
	BOOTRAID=""
fi

cleanup() {
	if ! eval pit_check; then
		if eval mount | grep "${BOOTRAID}" >/dev/null; then
			umount "${BOOTRAID}"
		fi
	fi

	if [[ "$REBOOT_NEEDED" == "true" ]]; then
		echo "The new on-disk boot artifacts will not take effect until a restart of the machine."
	fi
}

trap 'echo Canceling $(basename "${0%.*}") ; cleanup ; exit 1' SIGINT

mount_bootraid() {
	if ! eval pit_check; then
		if ! eval mount | grep "${BOOTRAID}" >/dev/null; then
			# Mount the BOOTRAID partition
			mount -L BOOTRAID -T /etc/fstab.metal
		fi
	fi
}

expected_initrd_name() {
  local expected_name=""
	# find the name the grub config expects
	expected_name=$(grep initrdefi "${BOOTRAID}"/boot/grub2/grub.cfg | awk '{print $2}' | awk -F'/' '{print $NF}')
	echo "${expected_name}"
}

get_artifact_from_s3() {
	local artifact="${1}"
	local path="${2}"
  local liveos=/run/initramfs/live/LiveOS

	mount_bootraid

	echo "Getting $(basename "${artifact}") from s3 (${path})..."
	curl -s -o "${artifact}" http://rgw-vip.nmn/"${path/s3:\/\/}"

  if ! check_boot_artifact "${artifact}"; then
    echo "${artifact} is not a valid file type.  Is S3 working?"
    echo "Copying local artifacts from ${liveos}/$(basename "${artifact}")"

    if ! cp "${liveos}/$(basename "${artifact}")" "${artifact}"; then
      echo "Unable to find a valid artifact"
      exit 1
    fi
  
  fi

	REBOOT_NEEDED="true"
}

check_boot_artifact() {
	local artifact="$1"
	# check if the filesize is bigger than 92 or 217 (that is the size of an XML error message from s3)
	# or check if this is a filetype we expect for a kernel or initrd
	if ! [[ $(stat --format=%s "${artifact}") -gt 92 ]] || \
    ! [[ $(stat --format=%s "${artifact}") -gt 217 ]] ||
    ! [[ $(file --brief --mime-type "${artifact}") == application/octet-stream ]]; then
		return 1
	else
		return 0
	fi
}

# mount the raid
mount_bootraid

if [[ "${ARTIFACT_S3_PATH}" == *kernel* ]]; then
	printf "Examining kernel..."
	f="${BOOTRAID}/boot/kernel"
elif [[ "${ARTIFACT_S3_PATH}" == *initrd* ]]; then
	printf "Examining initrd..."
	f="${BOOTRAID}/boot/$(expected_initrd_name)"
else
	printf "Unknown artifact for this script."
	exit 1
fi

# Check first if the file exists on the BOOTRAID
# Sometimes it is not even there
if [[ -f "${f}" ]]; then

	# if the file is bad
	if ! eval check_boot_artifact "${f}"; then

    echo -e "\n${f} size is too small or not an expected file type ($(stat --format=%s "${f}"):$(file --brief --mime-type "${f}"))"

    echo "Removing faulty file (${f})"
		# remove the problematic file
		rm -f "${f}"

		# then get a known-good artifact from the path discovered in s3
		get_artifact_from_s3 "${f}" "${ARTIFACT_S3_PATH}"

		if [[ $(basename "${f}") == *initrd* ]]; then
			# Modify the filename if grub is expecting something else
			# Sometimes it was named initrd, other times it has been initrd.img.xz
			if [[ $(basename "${f}") != $(expected_initrd_name) ]]; then
				echo mv "${f}" "$(dirname "${f}")/$(expected_initrd_name)"
			fi

		fi

	else

		printf '%s is OK.\n' "$(basename "${f}")"

	fi

else

	echo '%s not found in BOOTRAID.' "$(basename "${f}")"

	get_artifact_from_s3 "${f}" "${ARTIFACT_S3_PATH}"

fi

cleanup
