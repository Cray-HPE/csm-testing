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

# Define which Python flavors python-rpm-macros will use (this can be a list).
# https://github.com/openSUSE/python-rpm-macros#terminology
%define pythons %(echo ${PYTHON_BIN})
%define py_version %(echo ${PY_VERSION})
%define py_minor_version %(echo ${PY_VERSION} | cut -d. -f2)

%define test_dir /opt/cray/tests
%define install_dir %{test_dir}/install
%define livecd %{install_dir}/livecd
%define ncn %{install_dir}/ncn
%define dat %{install_dir}/dat
%define logs %{install_dir}/logs

%define python_venv_name csm-testing-python-venv
%define python_venv_dir %{install_dir}/%{python_venv_name}
%define python_venv_bin %{python_venv_dir}/bin/python

Name: %(echo $NAME)
License: HPE Software License Agreement
Summary: Goss tests to test out installation set-up
Group: HPC
Version: %(echo $VERSION)
Release: 1
Source: %{name}-%{version}.tar.bz2
Vendor: HPE
BuildArchitectures: %(echo $ARCH)
# Using or statements in spec files requires RPM and rpm-build >= 4.13
BuildRequires: rpm-build >= 4.13
BuildRequires: (python%{python_version_nodots}-base or python3-base >= %{py_version})
BuildRequires: coreutils
BuildRequires: findutils
BuildRequires: sed

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

%if "%{py_version}" == "3.6"

BuildRequires: python3-pip
Requires: python3-boto3
Requires: python3-botocore
Requires: python3-kubernetes
Requires: python3-rados
Requires: python3-requests

%else

BuildRequires: python%{python_version_nodots}-pip
Requires: python%{python_version_nodots}-boto3
Requires: python%{python_version_nodots}-botocore
Requires: python%{python_version_nodots}-kubernetes
Requires: python%{python_version_nodots}-rados
Requires: python%{python_version_nodots}-requests

%endif

%description
Tests to test the set-up during installation.
They test both the LiveCD and NCN environment.

%prep
%setup -q

%build

%install

install -d -m 755 %{buildroot}%{dat}
install -d -m 755 %{buildroot}%{logs}

# automated - livecd
install -d -m 755 %{buildroot}%{livecd}/automated/python
cp -a goss-testing/automated/*            %{buildroot}%{livecd}/automated
chmod +x -R %{buildroot}%{livecd}/automated/

# automated - ncn
install -d -m 755 %{buildroot}%{ncn}/automated/python
cp -a goss-testing/automated/*            %{buildroot}%{ncn}/automated
chmod +x -R %{buildroot}%{ncn}/automated/

# tests - livecd
install -d -m 755 %{buildroot}%{livecd}/tests
install -m 755 goss-testing/tests/livecd/*.yaml    %{buildroot}%{livecd}/tests
install -m 755 goss-testing/tests/common/*.yaml    %{buildroot}%{livecd}/tests

# tests - ncn
install -d -m 755 %{buildroot}%{ncn}/tests
install -m 755 goss-testing/tests/ncn/*.yaml                %{buildroot}%{ncn}/tests
install -m 755 goss-testing/tests/common/*.yaml             %{buildroot}%{ncn}/tests

# build-testing
install -d -m 755 %{buildroot}%{livecd}/build-testing
install -m 755 build-testing/*                     %{buildroot}%{livecd}/build-testing

# vars - livecd
install -d -m 755 %{buildroot}%{livecd}/vars
install -m 644 goss-testing/vars/vars-packages.yaml         %{buildroot}%{livecd}/vars
install -T -m 644 goss-testing/vars/variables-common.yaml   %{buildroot}%{livecd}/vars/variables-livecd.yaml
sed -i 's:@PYTHON_BIN_PATH@:%{python_venv_bin}:g' %{buildroot}%{livecd}/vars/variables-livecd.yaml
cat goss-testing/vars/variables-livecd.yaml >> %{buildroot}%{livecd}/vars/variables-livecd.yaml

# vars - ncn
install -d -m 755 %{buildroot}%{ncn}/vars
install -m 644 goss-testing/vars/vars-packages.yaml         %{buildroot}%{ncn}/vars
install -T -m 644 goss-testing/vars/variables-common.yaml   %{buildroot}%{ncn}/vars/variables-ncn.yaml
sed -i 's:@PYTHON_BIN_PATH@:%{python_venv_bin}:g' %{buildroot}%{ncn}/vars/variables-ncn.yaml
cat goss-testing/vars/variables-ncn.yaml >> %{buildroot}%{ncn}/vars/variables-ncn.yaml

# script files - livecd
install -d -m 755 %{buildroot}%{livecd}/scripts/python
cp -a goss-testing/scripts/*            %{buildroot}%{livecd}/scripts
chmod +x -R %{buildroot}%{livecd}/scripts/

# script files - ncn
install -d -m 755 %{buildroot}%{ncn}/scripts/python
cp -a goss-testing/scripts/*            %{buildroot}%{ncn}/scripts
chmod +x -R %{buildroot}%{ncn}/scripts/

# test suites - livecd
install -d -m 755 %{buildroot}%{livecd}/suites
cp -a goss-testing/suites/common-*      %{buildroot}%{livecd}/suites
cp -a goss-testing/suites/livecd-*      %{buildroot}%{livecd}/suites

# test suites - ncn
install -d -m 755 %{buildroot}%{ncn}/suites
cp -a goss-testing/suites/common-*      %{buildroot}%{ncn}/suites
cp -a goss-testing/suites/ncn-*         %{buildroot}%{ncn}/suites

# goss-servers config file
install -m 644 goss-testing/dat/*       %{buildroot}%{dat}

# goss-servers files
install -D -m 0755 -t %{buildroot}%{_sbindir}           systemd/start-goss-servers.sh
install -D -m 0644 -t %{buildroot}%{_unitdir}           systemd/goss-servers.service
install -D -m 0644 -t %{buildroot}%{_unitdir}-preset/   systemd/90-goss-servers.preset

# Create our Python virtual env, to use when executing Python scripts
%python_exec -m venv --system-site-packages %{buildroot}%{python_venv_dir}

# Install csm-testing module + dependencies into virtual env
%{buildroot}%{python_venv_bin} -m pip install --upgrade pip setuptools --no-cache --ignore-installed -c constraints.txt
%{buildroot}%{python_venv_bin} -m pip install csm_testing*.whl -r requirements.txt --disable-pip-version-check --no-cache --ignore-installed

# List what is in the virtual env, for the purposes of build logging
%{buildroot}%{python_venv_bin} -m pip list --format freeze --local

# Remove build tools to decrease the virtualenv size.
# Also remove packages that we wish to inherit from system Python
./remove-python-packages.sh %{buildroot}%{python_venv_bin} pip setuptools

# Remove __pycache__ directories  to decrease the virtualenv size.
find %{buildroot}%{python_venv_dir} -type d -name __pycache__ -exec rm -rvf {} \; -prune

# Fix the virtualenv scripts, ensure VIRTUAL_ENV points to the installed location on the system.
find %{buildroot}%{python_venv_dir}/bin -type f | xargs -t -i sed -i 's:%{buildroot}%{python_venv_dir}:%{python_venv_dir}:g' {}

# Create symlinks for Python test scripts
./create-python-script-symlinks.sh %{buildroot} %{python_venv_dir} test %{livecd}/scripts/python %{ncn}/scripts/python

# Create symlinks for Python tool scripts
./create-python-script-symlinks.sh %{buildroot} %{python_venv_dir} tool %{livecd}/automated/python %{ncn}/automated/python

%clean
rm -rf %{buildroot}%{dat}
rm -rf %{buildroot}%{livecd}
rm -rf %{buildroot}%{ncn}
rm -rf %{buildroot}%{python_venv_dir}
# Remove log directories only if empty
rmdir %{buildroot}%{logs} || true
# Remove overall installl directory and test directory, if empty
rmdir %{buildroot}%{install_dir} || true
rmdir %{buildroot}%{test_dir} || true

%files
%defattr(755, root, root)
%{dat}
%{logs}
%{livecd}
%{ncn}
%{python_venv_dir}

%post
# Restart goss-servers service, if installed and running
if systemctl is-active goss-servers; then
  systemctl try-restart goss-servers
fi

%changelog

%package -n goss-servers
Summary: Goss Health Check Endpoint Service
BuildArchitectures: %(echo $ARCH)
BuildRequires: systemd-rpm-macros

Requires: awk
Requires: bash
Requires: bind-utils
Requires: coreutils
Requires: goss
Requires: grep
Requires: hostname
Requires: iproute2
Requires: systemd

# The rest of these requirements are really for csm-testing, but we do not include csm-testing
# in our node images, only goss-servers. We want to make sure these requirements are included
# in the node images, so we list them here as well.
Requires: curl
Requires: diff
Requires: findutils
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
Requires: util-linux
Requires: util-linux-systemd

Requires: (python%{python_version_nodots}-base or python3-base >= %{py_version})

%if "%{py_version}" == "3.6"

Requires: python3-boto3
Requires: python3-botocore
Requires: python3-kubernetes
Requires: python3-rados
Requires: python3-requests

%else

Requires: python%{python_version_nodots}-boto3
Requires: python%{python_version_nodots}-botocore
Requires: python%{python_version_nodots}-kubernetes
Requires: python%{python_version_nodots}-rados
Requires: python%{python_version_nodots}-requests

%endif

# helps when installing a program whose unit files makes use of a feature only available in a newer systemd version
# If the program is installed on its own, it will have to make do with the available features
# If a newer systemd package is planned to be installed in the same transaction as the program,
# it can be beneficial to have systemd installed first, so that the features have become available by the time program is installed and restarted
%{?systemd_ordering}

%pre -n goss-servers
%service_add_pre goss-servers.service

%post -n goss-servers
%service_add_post goss-servers.service

%preun -n goss-servers
%service_del_preun goss-servers.service

%postun -n goss-servers
%service_del_postun goss-servers.service

%description -n goss-servers
Sets up a systemd service for running Goss health check servers

%files -n goss-servers
%{_sbindir}/start-goss-servers.sh
%{_unitdir}/goss-servers.service
%{_unitdir}-preset/90-goss-servers.preset
