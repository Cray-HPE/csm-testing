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

# Install tests
install -d -m 755 %{buildroot}%{livecd}/vars
install -d -m 755 %{buildroot}%{livecd}/tests
install -d -m 755 %{buildroot}%{ncn}/vars
install -d -m 755 %{buildroot}%{ncn}/tests
install -m 644 goss-testing/tests/*.yaml  %{buildroot}%{livecd}/tests
install -m 644 goss-testing/vars/*.yaml   %{buildroot}%{livecd}/vars
install -m 644 goss-testing/tests/*.yaml  %{buildroot}%{ncn}/tests
install -m 644 goss-testing/vars/*.yaml   %{buildroot}%{ncn}/vars

# Install goss-server files
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

%package goss-server
Summary: Goss Health Check Endpoint Service

%description goss-server
Sets up a systemd service for running Goss health check servers

%files goss-server
/usr/sbin/start-goss-servers.sh
/etc/systemd/system/goss-servers.service