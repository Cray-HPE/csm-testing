#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
%define internal_dir %{test_dir}/internal

Name: %(echo $NAME)-internal
Provides: %(echo $NAME)-internal
License: HPE Software License Agreement
Summary: Internal Goss tests for CT pipeline
Group: HPC
Version: %(echo $VERSION)
Release: 1
Source: %{name}-%{version}.tar.bz2
Vendor: HPE
BuildArchitectures: %(echo $ARCH)
Requires: csm-testing
Requires: goss-servers

%description
Goss tests for use in the CT pipeline.
This package is intended for internal use only and not for use on customer systems.

%prep
%setup -q

%build

%install
install -d -m 755 %{buildroot}%{internal_dir}
cp -a goss-testing/internal/* %{buildroot}%{internal_dir}

%clean
rm -rf %{buildroot}%{internal_dir}

%files
%defattr(755, root, root)
%{internal_dir}

%postun
# remove /opt/cray/tests/internal to leave the system as it was
# since this is only used for internal testing, it does not need to remain
if [ $1 -eq 0 ]; then
  rm -rf %{internal_dir}
fi

%changelog

