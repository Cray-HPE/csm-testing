# CT Testing

## Objectives

1. Pick resources to test against (e.g. pick which Node)
2. Notify about what is impacted
3. Run a sequence of operations: setup, test, teardown

## Sytle

1. Use yaml file extentions.
2. Use hyphens (-) as word separators in file names.
2. `*-setup.yaml` for a setup file.
3. `*-teardown.yaml` for a teardown file.
4. `*-ansible*.yaml` for an ansible file.

## Creating Tests

### Lifecycle of a test

1. Initialize
    1. Validate configuration
    2. Create the goss vars yaml file
2. Test - run one or more tests
    1. Setup
        - Create resources in CSM
    2. Run Tests
    3. Teardown
        - Remove resources created in 2.1
3. Generate Reports (Optional)


## Examples

Example: Calling goss and ansible directly:
```bash
$ csm-ct.py create-config
$ goss --vars var-dns.yaml -g goss-dns.yaml validate
$ ansible-playbook ~/csm-testing/ct-testing/tests/example-test-ansible-setup.yaml
$ goss --vars /var/tmp/csm-ct/config.yaml -g ~/csm-testing/ct-testing/tests/example-test.yaml validate
$ ansible-playbook ~/csm-testing/ct-testing/tests/example-test-ansible-teardown.yaml
```

Example: Using only the `csm-ct.py` script:
```bash
$ mkdir -p /var/tmp/csm-ct

$ csm-ct.py list
$ csm-ct.py create-config --out-dir /var/tmp/csm-ct

$ csm-ct.py run -t example-test -c /var/tmp/csm-ct/config.yaml
```
