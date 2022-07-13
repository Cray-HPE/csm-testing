# Contributing

The git-tags file follows semver (no prefixing or suffixing with anything, only `vX.Y.Z`).

Incrementing is easy (X.Y.Z):
- X when something dramatic occurs such as overhaul or changes that break compatibility on a large scale
- Y when a feature comes in; a new thing, a new piece, or modification to existing code as RFE
- Z for hotfix or small changes

The git-hash is used to differentiate between versions, i.e. increment how often you want but remember the hash makes this the full RPM version unique (along with any other DST artifact).
