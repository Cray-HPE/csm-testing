@Library("dst-shared@release/shasta-1.4") _

def skipSuccess = false

rpmBuild(
    specfile: "csm-testing.spec",
    product: "csm",
    target_node: "ncn",
    fanout_params : ["sle15sp2"],
    send_events: "csm-testing",
    channel: "metal-ci-alerts"
)
