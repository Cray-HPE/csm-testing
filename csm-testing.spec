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

%clean
rm -rf %{buildroot}%{livecd}
rm -rf %{buildroot}%{ncn}

%files
%defattr(755, root, root)
%{livecd}
%{ncn}

%changelog
