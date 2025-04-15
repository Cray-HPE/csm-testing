ct_test
=========

Runs a goss file and formats the results for the DST pipeline.

Requirements
------------

- `csm-testing`
- `goss-servers`
- `csm-testing-internal`

Role Variables
--------------

- `goss_file`: the goss test file to run, usually passed as an extra var
- `api_results_file`: path to the existing DST results file (default: `/tmp/api-results.json`)
- `goss_output_file`: raw goss output from `goss validate -f json` (default: `/tmp/raw-goss-results.json`)
- `dst_formatted_output_file`: goss tests formatted for DST (default: `/tmp/dst-formatted-results.json`)
- `package_manager`: [apk, dpkg, pacman, rpm] (default: `rpm`)

Dependencies
------------


Example Playbook
----------------

    - name: run a goss test and format for dst pipeline
      hosts: localhost
      gather_facts: false
      roles:
        - ct_test

Using the correct `ANSIBLE_CONFIG` may be required so the role can be found:

```
export ANSIBLE_CONFIG=/opt/cray/tests/internal/ansible/ansible.cfg
ansible-playbook \
  -e goss_file=/opt/cray/tests/internal/tests/some_goss_test.yml \
  playbook.yml
```

License
-------

HPE Software License Agreement

Author Information
------------------

Hewlett Packard Enterprise Development LP
