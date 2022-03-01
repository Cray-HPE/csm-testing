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