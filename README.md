# Overview
This repository contains tests. 

## Goss Testing
Goss tests are being used to test out the LiveCD and Non-Compute Node (NCN) environments.

Some goss tests are used at build-time for the LiveCD and NCN images. Other goss tests
are used at run-time. 

The LiveCD run-time tests test that the necessary services and infrastructure
are in place to allow the NCNs to boot successfully.

The NCN run-time tests test that the necessary services have started to allow the
Shasta environment to operate successfully.

### Running Remote Run-Time Tests

Run the NCN run-time Goss test suite at the following endpoint:

> http://[ip-or-hostname]:8080/ncn-tests-all

The endpoint can be queried from LiveCD or other nodes with access to the NCN. The response
format will be in JSON.