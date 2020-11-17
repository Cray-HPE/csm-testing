@Library('dst-shared') _

def skipSuccess = false

rpmBuild(
    specfile: "csm-testing.spec",
    product: "shasta-standard,shasta-premium",
    target_node: "ncn",
    send_events: "csm-testing",
    channel: "metal-ci-alerts"
)