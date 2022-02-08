# Goss Testing
Goss tests are being used to test out the LiveCD (a.k.a. PIT node) and Non-Compute Node (NCN) environments.

Some Goss tests are used at build-time for the LiveCD and NCN images. Other Goss tests
are used at runtime. 

The LiveCD runtime tests verify that the necessary services and infrastructure
are in place to allow the NCNs to boot successfully.

The NCN runtime tests verify that the necessary services have started to allow the
Shasta environment to operate successfully.

## Creating Goss Tests

Goss Manual: https://github.com/aelsabbahy/goss/blob/master/docs/manual.md

New Goss test files should be added to the directory `/goss-testing/tests` in this repo.

There are 4 test suite files which load external test files as includes, then merge them together before 
executing them. These files are:

**LiveCD Test Suites**
- `livecd-build-time-tests.yaml`
- `livecd-run-time-tests.yaml`

**NCN Test Suites**
- `ncn-build-time-tests.yaml`
- `ncn-run-time-tests.yaml`

If you would like your tests to run on the LiveCD or NCN nodes at either build time or run time, include
them in the appropriate file.

### Test File Naming Convention

Test files should be named using this convention: goss-[descriptive-name].yaml

Hyphens (-) should be used as word separators.

### Test Templating

Goss uses a Golang style templating model with variables loaded from variable files written
in Yaml. The variable files are located in the `/goss-testing/tests/vars` directory in this repo.

### Variable Files

In this repo there are two variable files containing all variables for LiveCD and NCN tests.

**LiveCD Variables:**
- `/vars/variables-livecd.yaml`

**NCN Variables:**
- `/vars/variables-ncn.yaml`

## Launching Goss Tests
Launching Goss tests is simple. 
You can specify a specific test file using the '-g' option.
You can specify a specific variable file using the '--vars' option.
Use the command 'render' to ask Goss to render a template file, which does 
nothing more than output the file to standard out.
Use the command 'validate' to run the test.

Example launches:
```bash
$ goss --vars var-dns.yaml -g goss-dns.yaml render
$ goss --vars var-dns.yaml -g goss-dns.yaml validate
```

## Goss Server

This repository contains all Goss test suites and the files required to build the Goss server systemd service. 

Goss server runs on the NCNs and provides a health check endpoint that can be accessed remotely using http. It is deployed as a systemd service, which is installed from an RPM package.

We can run multiple Goss servers to execute different suites of tests by adding the server start commands to the `start-goss-servers.sh`.

## Test Files Install Directory

The test files will be installed to the following locations:

- `/opt/cray/tests/install/ncn/tests`
- `/opt/cray/tests/install/pit/tests`

## Running Tests Locally

Use the following command to run a single test or a suite of tests on the local machine:

```bash
$ goss -g /opt/cray/tests/install/ncn/tests/[test_file.yaml] --vars /opt/cray/tests/install/ncn/vars/[variable_file.yaml] validate
```

## Running Tests Remotely

Use the following command to run a suite of tests on a remote machine where there is a running Goss server endpoint.

```bash
$ curl http://[ip-address-or-host-name]:[port-number]/[endpoint]
```
