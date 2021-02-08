# Copyright 2020 Hewlett Packard Enterprise Development LP

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
install -d -m 644 %{buildroot}%{livecd}/automated
install -d -m 644 %{buildroot}%{livecd}/tests
install -d -m 644 %{buildroot}%{livecd}/vars
install -d -m 644 %{buildroot}%{ncn}/automated
install -d -m 644 %{buildroot}%{ncn}/tests
install -d -m 644 %{buildroot}%{ncn}/vars
install -m 644 goss-testing/automated/*         %{buildroot}%{livecd}/automated
install -m 644 goss-testing/tests/livecd/*.yaml %{buildroot}%{livecd}/tests
install -m 644 goss-testing/tests/common/*.yaml %{buildroot}%{livecd}/tests
install -m 644 goss-testing/vars/*.yaml         %{buildroot}%{livecd}/vars
install -m 644 goss-testing/automated/*         %{buildroot}%{ncn}/automated
install -m 644 goss-testing/tests/ncn/*.yaml    %{buildroot}%{ncn}/tests
install -m 644 goss-testing/tests/common/*.yaml %{buildroot}%{ncn}/tests
install -m 644 goss-testing/vars/*.yaml         %{buildroot}%{ncn}/vars
# Install script files
install -d -m 755 %{buildroot}%{livecd}/scripts
install -d -m 755 %{buildroot}%{livecd}/scripts/python
install -d -m 755 %{buildroot}%{livecd}/scripts/python/lib
install -d -m 755 %{buildroot}%{ncn}/scripts
install -d -m 755 %{buildroot}%{ncn}/scripts/python
install -d -m 755 %{buildroot}%{ncn}/scripts/python/lib
# Install test suites
install -d -m 644 %{buildroot}%{livecd}/suites
install -d -m 644 %{buildroot}%{ncn}/suites
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
install -m 755 goss-servers.service %{buildroot}/etc/systemd/system/

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

%description -n goss-servers
Sets up a systemd service for running Goss health check servers

%files -n goss-servers
/usr/sbin/start-goss-servers.sh
/etc/systemd/system/goss-servers.service
