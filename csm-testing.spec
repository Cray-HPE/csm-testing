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

%define test_dir /opt/cray/tests
%define install_dir %{test_dir}/install
%define livecd %{install_dir}/livecd
%define ncn %{install_dir}/ncn
%define dat %{install_dir}/dat
%define logs %{install_dir}/logs

Name: %(echo $NAME)
License: HPE Software License Agreement
Summary: Goss tests to test out installation set-up
Group: HPC
Version: %(echo $VERSION)
Release: 1
Source: %{name}-%{version}.tar.bz2
Vendor: HPE
BuildArchitectures: %(echo $ARCH)
BuildRequires: systemd-rpm-macros

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
install -d -m 755 %{buildroot}%{livecd}/automated/python/lib
cp -a goss-testing/automated/*            %{buildroot}%{livecd}/automated
cp -a goss-testing/automated/python/*     %{buildroot}%{livecd}/automated/python
cp -a goss-testing/automated/python/lib/* %{buildroot}%{livecd}/automated/python/lib
chmod +x -R %{buildroot}%{livecd}/automated/

# automated - ncn
install -d -m 755 %{buildroot}%{ncn}/automated/python/lib
cp -a goss-testing/automated/*            %{buildroot}%{ncn}/automated
cp -a goss-testing/automated/python/*     %{buildroot}%{ncn}/automated/python
cp -a goss-testing/automated/python/lib*  %{buildroot}%{ncn}/automated/python/lib
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
cat goss-testing/vars/variables-livecd.yaml >> %{buildroot}%{livecd}/vars/variables-livecd.yaml

# vars - ncn
install -d -m 755 %{buildroot}%{ncn}/vars
install -m 644 goss-testing/vars/vars-packages.yaml         %{buildroot}%{ncn}/vars
install -T -m 644 goss-testing/vars/variables-common.yaml   %{buildroot}%{ncn}/vars/variables-ncn.yaml
cat goss-testing/vars/variables-ncn.yaml >> %{buildroot}%{ncn}/vars/variables-ncn.yaml

# script files - livecd
install -d -m 755 %{buildroot}%{livecd}/scripts/python/lib
cp -a goss-testing/scripts/*            %{buildroot}%{livecd}/scripts
cp -a goss-testing/scripts/python/*     %{buildroot}%{livecd}/scripts/python
cp -a goss-testing/scripts/python/lib/* %{buildroot}%{livecd}/scripts/python/lib
chmod +x -R %{buildroot}%{livecd}/scripts/

# script files - ncn
install -d -m 755 %{buildroot}%{ncn}/scripts/python/lib
cp -a goss-testing/scripts/*            %{buildroot}%{ncn}/scripts
cp -a goss-testing/scripts/python/*     %{buildroot}%{ncn}/scripts/python
cp -a goss-testing/scripts/python/lib/* %{buildroot}%{ncn}/scripts/python/lib
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

%clean
rm -rf %{buildroot}%{dat}
rm -rf %{buildroot}%{livecd}
rm -rf %{buildroot}%{ncn}
# Remove log directories only if empty
rmdir %{buildroot}%{logs} || true

%files
%defattr(755, root, root)
%{dat}
%{logs}
%{livecd}
%{ncn}

%changelog

%package -n goss-servers
Summary: Goss Health Check Endpoint Service
Requires: goss

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
