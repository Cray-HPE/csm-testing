# (C) Copyright 2020, 2022 Hewlett Packard Enterprise Development LP.
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


%define test_dir /opt/cray/tests
%define install_dir %{test_dir}/install
%define livecd %{install_dir}/livecd
%define ncn %{install_dir}/ncn

Name: csm-testing
License: HPE Software License Agreement
Summary: Goss tests to test out installation set-up
Group: HPC
Version: %(cat .rpm_version)
Release: %(echo ${BUILD_METADATA})
Source: %{name}-%{version}.tar.bz2
Vendor: HPE
BuildArchitectures: noarch

%description
Tests to test the set-up during installation.
They test both the LiveCD and NCN environment.

%prep
%setup -q

%build

%install

# Install testing files
install -d -m 755 %{buildroot}%{livecd}/automated
install -d -m 755 %{buildroot}%{livecd}/tests
install -d -m 755 %{buildroot}%{livecd}/vars
install -d -m 755 %{buildroot}%{livecd}/build-testing
install -d -m 755 %{buildroot}%{ncn}/automated
install -d -m 755 %{buildroot}%{ncn}/tests
install -d -m 755 %{buildroot}%{ncn}/vars
install -m 755 goss-testing/automated/*         %{buildroot}%{livecd}/automated
install -m 755 goss-testing/tests/livecd/*.yaml %{buildroot}%{livecd}/tests
install -m 755 goss-testing/tests/common/*.yaml %{buildroot}%{livecd}/tests
install -m 755 goss-testing/vars/*.yaml         %{buildroot}%{livecd}/vars
install -m 755 build-testing/*                  %{buildroot}%{livecd}/build-testing
install -m 755 goss-testing/automated/*         %{buildroot}%{ncn}/automated
install -m 755 goss-testing/tests/ncn/*.yaml    %{buildroot}%{ncn}/tests
install -m 755 goss-testing/tests/common/*.yaml %{buildroot}%{ncn}/tests
install -m 755 goss-testing/vars/*.yaml         %{buildroot}%{ncn}/vars
# Install script files
install -d -m 755 %{buildroot}%{livecd}/scripts
install -d -m 755 %{buildroot}%{livecd}/scripts/python
install -d -m 755 %{buildroot}%{livecd}/scripts/python/lib
install -d -m 755 %{buildroot}%{ncn}/scripts
install -d -m 755 %{buildroot}%{ncn}/scripts/python
install -d -m 755 %{buildroot}%{ncn}/scripts/python/lib
# Install test suites
install -d -m 755 %{buildroot}%{livecd}/suites
install -d -m 755 %{buildroot}%{ncn}/suites
# Copy files
cp -a goss-testing/scripts/*            %{buildroot}%{livecd}/scripts
cp -a goss-testing/scripts/python/*     %{buildroot}%{livecd}/scripts/python
cp -a goss-testing/scripts/python/lib/* %{buildroot}%{livecd}/scripts/python/lib
cp -a goss-testing/suites/livecd-*      %{buildroot}%{livecd}/suites
cp -a goss-testing/scripts/*            %{buildroot}%{ncn}/scripts
cp -a goss-testing/scripts/python/*     %{buildroot}%{ncn}/scripts/python
cp -a goss-testing/scripts/python/lib/* %{buildroot}%{ncn}/scripts/python/lib
cp -a goss-testing/suites/ncn-*         %{buildroot}%{ncn}/suites
chmod +x -R %{buildroot}%{ncn}/scripts/
chmod +x -R %{buildroot}%{livecd}/scripts/
chmod +x -R %{buildroot}%{ncn}/automated/

# Install goss-servers files
mkdir -p %{buildroot}/usr/sbin
mkdir -p %{buildroot}/etc/systemd/system/
install -m 755 start-goss-servers.sh %{buildroot}/usr/sbin/
install -m 644 goss-servers.service %{buildroot}/etc/systemd/system/

%clean
rm -rf %{buildroot}%{livecd}
rm -rf %{buildroot}%{ncn}

%files
%defattr(755, root, root)
%{livecd}
%{ncn}

%changelog

%package -n goss-servers
Summary: Goss Health Check Endpoint Service

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
/usr/sbin/start-goss-servers.sh
/etc/systemd/system/goss-servers.service
