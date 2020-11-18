# Goss Tests

## Naming Conventions
Some goss tests are templates that need a variable file to fill out the template. 
A naming convention has been used to identify tests and variable files.

* Variable files: vars-<descriptive name>.yaml
* Test files: goss-<descriptive name>.yaml

Often, the tests that are templates are paired with a variable file that has the 
same descriptive name. For example, vars-dns.yaml and goss-dns.yaml are a pair. 
This pairing does not always follow that rule. Sometimes, variable files contain
generic data that may be applicable to multiple tests. A comment will appear at
the beggining of test that needs a specific variable file.


## Launching Goss tests
Launching goss tests is simple. 
You can specify a specific test file using the '-g' option.
You can specify a specific variable file using the '--vars' option.
Use the command 'render' to ask goss to render a template file, which does 
nothing more than output the file to standard out.
Use the command 'validate' to run the test.

Example launches:
goss --vars var-dns.yaml -g goss-dns.yaml render
goss --vars var-dns.yaml -g goss-dns.yaml validale