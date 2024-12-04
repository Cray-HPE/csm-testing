# Overview

This repository contains Goss test files, Goss variable files and code for the `goss-servers`
systemd service, which provides a run-time Goss testing endpoint on nodes where it is
installed.

## Goss Testing

Goss tests are being used to test the LiveCD (a.k.a. PIT node) and Non-Compute Node (NCN) environments.

Some Goss tests are used at build-time for the LiveCD and NCN images. Other Goss tests
are used at runtime. 

The LiveCD runtime tests verify that the necessary services and infrastructure
are in place to allow the NCNs to boot successfully.

The NCN runtime tests verify that the necessary services have started to allow the
Shasta environment to operate successfully.

### Running Remote Run-Time Tests

Run the NCN runtime Goss test suite at the following endpoint:

> http://[ip-or-hostname-of-ncn]:8080/ncn-tests-all

The endpoint can be queried from the LiveCD or other nodes with access to the NCN. The response
format will be in JSON.

## Python Code

All csm-testing Python tests and utiltities are packaged into the csm-testing package, installed into a
virtual environment on the system. The source code for all of this is under [`src/csm_testing`](src/csm_testing).

### Python Version

See [Jenkinsfile.github](Jenkinsfile.github) and [pyproject.toml](pyproject.toml) for details on which Python
version is used. Currently version 3.6 is used because:

1. It is available on all NCNs
2. This is the version that has been used to run all of the csm-testing Python code so far (i.e. it has not been tested on newer Python versions)
3. One of the Python dependencies (`rados`) is not available for any other Python versions.

### Python Tests

All test scripts should be created as submodules under [`src/csm_testing/tests`](src/csm_testing/tests). The test
submodule should include a `__main__.py` file which contains a `main()` function with the following signature:

```python
def main() -> int:
    """
    Returns 0 on success.
    Returns non-0 on failure.
    """
```

When the RPM is built, each test submodule will have a link created in the following two locations (note the
lack of a `.py` extension):

- `/opt/cray/tests/install/livecd/scripts/python/<submodule_name>`
- `/opt/cray/tests/install/ncn/scripts/python/<submodule_name>`

### Python Tools

All utility scripts should be created as submodules under [`src/csm_testing/tools`](src/csm_testing/tools).
These submodules have the same `__main__.py` requirement as the [Python Tests](#python-tests).

When the RPM is built, each tool submodule will have a link created in the following two locations (note the
lack of a `.py` extension):

- `/opt/cray/tests/install/livecd/automated/python/<submodule_name>`
- `/opt/cray/tests/install/ncn/automated/python/<submodule_name>`

### Python Library

Helper submodules that are not directly invoked as scripts should be created under
[`src/csm_testing/lib`](src/csm_testing/lib].

### Python Requirements

If additional Python packages are required, add them to [requirements.txt](requirements.txt), along
with version constraints on that package (and any dependencies it pulls in) in [constraints.txt](constraints.txt).
These will be installed into the virtual environment when the RPM is built.

Note that for a few dependencies, the dependency is fulfilled by inheriting the package from the system Python
installation. This should not normally be done. If it does need to be done, be sure to list the required system
Python package in the [csm-testing-requirements.spec](inc/csm-testing-requirements.spec) file (along with applicable
version constraints, if any). Also be sure to update [requirements.txt](requirements.txt) -- see that file for details
on how to list a package that is being inherited from the system Python installation.
