#
# MIT License
#
# (C) Copyright 2020-2024 Hewlett Packard Enterprise Development LP
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

# This is just a list of requirements (but not build requirements) for the csm-testing RPM
# It is included by the main csm-testing spec file. Any variables/macros used in here are
# defined in the main spec file

# Many of these requires are for various commands/tools used in shell scripts
Requires: awk
Requires: bash
Requires: bind-utils
Requires: coreutils
Requires: curl
Requires: diff
Requires: findutils
Requires: goss
Requires: grep
Requires: hostname

# yq version 3 is used, which is provided by hpe-yq 4 or 3 <= yq < 4
Requires: ((hpe-yq >= 4) or ((yq >= 3) and (yq < 4)))

Requires: ipmitool
Requires: iproute2
Requires: jq >= 1.6
Requires: (kubectl or kubernetes-client-provider)
Requires: nmap
Requires: openssh-clients
Requires: pdsh
Requires: rpm >= 4.13
Requires: sed
Requires: systemd
Requires: util-linux
Requires: util-linux-systemd

Requires: (python%{python_version_nodots}-base or python3-base >= %{py_version})

Requires: %{py_rpm_prefix}-boto3
Requires: %{py_rpm_prefix}-botocore
Requires: %{py_rpm_prefix}-certifi
Requires: %{py_rpm_prefix}-chardet
Requires: %{py_rpm_prefix}-idna
Requires: %{py_rpm_prefix}-kubernetes
Requires: %{py_rpm_prefix}-rados
Requires: %{py_rpm_prefix}-requests
Requires: %{py_rpm_prefix}-urllib3
