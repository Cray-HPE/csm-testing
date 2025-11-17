#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
This script runs checks for Rack Resiliency Service (RRS).
"""

import base64
import json
import logging
import subprocess
import sys

import yaml

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(command):
    """
    Function to run a shell command and return output and return code.
    Args:
        command (str): Command to execute
    Returns:
        tuple: (output, returncode)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False
        )
        return result.stdout.strip(), result.returncode
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to run command '%s': %s", command, exc)
        return "", 1


def check_rrs_enabled():
    """
    Check if Rack Resiliency is enabled in customizations.yaml.
    This is the gate test - if RR is not enabled, subsequent tests will be skipped.
    Returns:
        bool: True if enabled, False otherwise
    """
    logger.info("\n=== Checking RRS Enablement ===")
    cmd = 'kubectl get secrets -n loftsman site-init -o jsonpath="{.data.customizations\\.yaml}"'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("Failed to retrieve customizations.yaml from site-init secret")
        return False

    try:
        customizations = yaml.safe_load(base64.b64decode(output))
        rr_enabled = customizations.get('spec', {}).get('kubernetes', {}).get(
            'services', {}).get('rack-resiliency', {}).get('enabled', False)

        if rr_enabled:
            logger.info("SUCCESS: Rack Resiliency is enabled")
            return True

        logger.info("INFO: Rack Resiliency is not enabled on this system")
        logger.info("NEGATIVE TEST PASS: Subsequent tests will be skipped")
        return False
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse customizations.yaml: %s", exc)
        return False


def check_k8s_zones():
    """
    Check if Kubernetes topology zones are configured.
    Returns:
        bool: True if zones are configured, False otherwise
    """
    logger.info("\n=== Checking Kubernetes Zones ===")
    cmd = 'kubectl get nodes -L topology.kubernetes.io/zone --no-headers'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("Failed to get Kubernetes nodes")
        return False

    zone_count = 0
    for line in output.split('\n'):
        if line.strip():
            parts = line.split()
            if len(parts) >= 6 and parts[5]:  # Zone is the 6th column
                zone_count += 1

    if zone_count > 0:
        logger.info("SUCCESS: Found %d nodes with zone labels", zone_count)
        return True

    logger.warning("WARNING: No Kubernetes zones found")
    return False


def check_ceph_zones():
    """
    Check if Ceph zones (racks) are configured.
    Returns:
        bool: True if zones are configured, False otherwise
    """
    logger.info("\n=== Checking Ceph Zones ===")
    cmd = 'ceph osd tree | grep rack'
    output, returncode = run_command(cmd)

    if returncode == 0 and output:
        rack_count = len(output.split('\n'))
        logger.info("SUCCESS: Found %d Ceph racks/zones", rack_count)
        return True

    logger.warning("WARNING: No Ceph racks/zones found")
    return False


def check_helm_chart():
    """
    Check if cray-rrs Helm chart is deployed.
    Returns:
        bool: True if chart is deployed, False otherwise
    """
    logger.info("\n=== Checking RRS Helm Chart ===")
    cmd = 'helm ls -n rack-resiliency -o json'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("Failed to list Helm charts in rack-resiliency namespace")
        return False

    try:
        charts = json.loads(output)
        for chart in charts:
            if chart.get('name') == 'cray-rrs':
                status = chart.get('status')
                if status == 'deployed':
                    logger.info(
                        "SUCCESS: cray-rrs Helm chart is deployed (status: %s)",
                        status
                    )
                    return True

                logger.error(
                    "FAILURE: cray-rrs chart status is %s (expected: deployed)",
                    status
                )
                return False

        logger.error(
            "FAILURE: cray-rrs Helm chart not found in rack-resiliency namespace"
        )
        return False
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse Helm output: %s", exc)
        return False


def check_deployment():
    """
    Check if cray-rrs deployment and pod are running.
    Validates that pod state matches prerequisites (zones and configmaps).
    This function consolidates all negative testing for missing prerequisites.
    Returns:
        bool: True if deployment state is correct based on prerequisites
    """
    logger.info("\n=== Checking RRS Deployment ===")

    # Check deployment exists
    cmd = 'kubectl get deployment cray-rrs -n rack-resiliency -o jsonpath="{.metadata.name}" 2>/dev/null'
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "cray-rrs":
        logger.error("FAILURE: cray-rrs deployment not found")
        return False

    logger.info("INFO: cray-rrs deployment exists")

    # Check prerequisites: K8s zones, Ceph zones, and ConfigMaps
    logger.info("Checking prerequisites (K8s zones, Ceph zones, and ConfigMaps)...")

    # Check K8s zones
    k8s_cmd = 'kubectl get nodes -L topology.kubernetes.io/zone --no-headers 2>/dev/null'
    k8s_output, _ = run_command(k8s_cmd)
    k8s_zone_count = 0
    for line in k8s_output.split('\n'):
        if line.strip():
            parts = line.split()
            if len(parts) >= 6 and parts[5]:
                k8s_zone_count += 1

    # Check Ceph racks
    ceph_cmd = 'ceph osd tree 2>/dev/null | grep rack'
    ceph_output, ceph_returncode = run_command(ceph_cmd)
    ceph_rack_count = len(ceph_output.split('\n')) if ceph_returncode == 0 and ceph_output else 0

    # Check ConfigMaps
    static_cmd = ('kubectl get configmap rrs-mon-static -n rack-resiliency '
                  '-o jsonpath="{.metadata.name}" 2>/dev/null')
    static_cm, static_returncode = run_command(static_cmd)
    static_exists = (static_returncode == 0 and static_cm == "rrs-mon-static")

    dynamic_cmd = ('kubectl get configmap rrs-mon-dynamic -n rack-resiliency '
                   '-o jsonpath="{.metadata.name}" 2>/dev/null')
    dynamic_cm, dynamic_returncode = run_command(dynamic_cmd)
    dynamic_exists = (dynamic_returncode == 0 and dynamic_cm == "rrs-mon-dynamic")

    logger.info("K8s zones: %d", k8s_zone_count)
    logger.info("Ceph racks: %d", ceph_rack_count)
    logger.info("rrs-mon-static ConfigMap: %s", "Found" if static_exists else "NotFound")
    logger.info("rrs-mon-dynamic ConfigMap: %s", "Found" if dynamic_exists else "NotFound")

    # Check pod status
    pod_cmd = ('kubectl get pods -n rack-resiliency '
               '-l app.kubernetes.io/instance=cray-rrs '
               '-o jsonpath="{.items[0].status.phase}" 2>/dev/null')
    pod_status, pod_returncode = run_command(pod_cmd)

    if pod_returncode != 0 or not pod_status:
        pod_status = "NotFound"

    logger.info("Current pod status: %s", pod_status)

    # Determine expected state based on prerequisites
    prerequisites_met = (
        k8s_zone_count > 0 and
        ceph_rack_count > 0 and
        static_exists and
        dynamic_exists
    )

    if not prerequisites_met:
        # Prerequisites NOT met - deployment should be in Init state
        logger.info("Prerequisites NOT met - expecting Init state")
        
        # List which prerequisites are missing
        missing = []
        if k8s_zone_count == 0:
            missing.append("K8s zones")
        if ceph_rack_count == 0:
            missing.append("Ceph zones")
        if not static_exists:
            missing.append("rrs-mon-static ConfigMap")
        if not dynamic_exists:
            missing.append("rrs-mon-dynamic ConfigMap")
        logger.info("Missing prerequisites: %s", ", ".join(missing))
        
        # Should be in Init state (Pending or NotFound)
        if pod_status in ["Pending", "NotFound"]:
            logger.info(
                "NEGATIVE TEST PASS: Deployment is in Init state as expected "
                "(prerequisites not met)"
            )
            return True

        logger.error(
            "NEGATIVE TEST FAIL: Deployment should be in Init state when prerequisites "
            "are not met, but found: %s",
            pod_status
        )
        return False

    # Prerequisites met - deployment should be Running
    logger.info("Prerequisites met - expecting Running state")
    if pod_status == "Running":
        logger.info("SUCCESS: Deployment is Running as expected (all prerequisites met)")
        return True

    logger.error(
        "FAILURE: Deployment should be Running when prerequisites are met, "
        "but found: %s",
        pod_status
    )
    return False


def check_configmaps():
    """
    Check if required RRS ConfigMaps exist and are valid.
    Returns:
        bool: True if ConfigMaps are valid, False otherwise
    """
    logger.info("\n=== Checking RRS ConfigMaps ===")

    # Check rrs-mon-static
    cmd = ('kubectl get configmap rrs-mon-static -n rack-resiliency '
           '-o jsonpath="{.metadata.name}" 2>/dev/null')
    static_cm, static_returncode = run_command(cmd)

    # Check rrs-mon-dynamic
    cmd = ('kubectl get configmap rrs-mon-dynamic -n rack-resiliency '
           '-o jsonpath="{.metadata.name}" 2>/dev/null')
    dynamic_cm, dynamic_returncode = run_command(cmd)

    static_exists = (static_returncode == 0 and static_cm == "rrs-mon-static")
    dynamic_exists = (dynamic_returncode == 0 and dynamic_cm == "rrs-mon-dynamic")

    if not static_exists or not dynamic_exists:
        logger.warning("WARNING: Required ConfigMaps not found")
        logger.info("rrs-mon-static: %s", "Found" if static_exists else "NotFound")
        logger.info("rrs-mon-dynamic: %s", "Found" if dynamic_exists else "NotFound")
        return False

    logger.info("INFO: rrs-mon-static ConfigMap exists")
    logger.info("INFO: rrs-mon-dynamic ConfigMap exists")

    # Validate rrs-mon-static contains critical services configuration
    cmd = ('kubectl get configmap rrs-mon-static -n rack-resiliency '
           '-o jsonpath="{.data.critical-service-config\\.json}"')
    output, returncode = run_command(cmd)

    if returncode != 0 or not output:
        logger.error(
            "FAILURE: critical-service-config.json not found in rrs-mon-static"
        )
        return False

    try:
        config = json.loads(output)
        if "critical_services" in config:
            logger.info("SUCCESS: RRS ConfigMaps are valid")
            return True

        logger.error("FAILURE: critical_services not found in configuration")
        return False
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse ConfigMap data: %s", exc)
        return False


def check_zones_list():
    """
    Check if 'cray rrs zones list' command works.
    Returns:
        bool: True if command succeeds, False otherwise
    """
    logger.info("\n=== Checking RRS Zones List ===")
    cmd = 'cray rrs zones list --format json'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("FAILURE: 'cray rrs zones list' command failed")
        return False

    try:
        zones = json.loads(output)
        zone_count = len(zones.get('Zones', []))
        logger.info(
            "SUCCESS: 'cray rrs zones list' returned %d zones",
            zone_count
        )
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse zones list output: %s", exc)
        return False


def check_critical_services_list():
    """
    Check if 'cray rrs criticalservices list' command works.
    Returns:
        bool: True if command succeeds, False otherwise
    """
    logger.info("\n=== Checking RRS Critical Services List ===")
    cmd = 'cray rrs criticalservices list --format json'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("FAILURE: 'cray rrs criticalservices list' command failed")
        return False

    try:
        services = json.loads(output)
        if "critical_services" in services:
            namespaces = services["critical_services"].get("namespace", {})
            service_count = sum(len(v) for v in namespaces.values())
            logger.info(
                "SUCCESS: 'cray rrs criticalservices list' returned %d services",
                service_count
            )
            return True

        logger.warning("No critical services found")
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse critical services output: %s", exc)
        return False


def check_critical_services_status():
    """
    Check if 'cray rrs criticalservices status list' command works.
    Returns:
        bool: True if command succeeds, False otherwise
    """
    logger.info("\n=== Checking RRS Critical Services Status ===")
    cmd = 'cray rrs criticalservices status list --format json'
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error(
            "FAILURE: 'cray rrs criticalservices status list' command failed"
        )
        return False

    try:
        status = json.loads(output)
        service_count = len(status.get('critical_services_status', []))
        logger.info(
            "SUCCESS: 'cray rrs criticalservices status list' returned "
            "status for %d services",
            service_count
        )
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse critical services status output: %s", exc)
        return False


def main():
    """
    Main function to run all RRS checks.
    Implements skip logic when RR is not enabled.
    """
    logger.info("=" * 60)
    logger.info("Running Rack Resiliency Service (RRS) Checks")
    logger.info("=" * 60)

    # First check if RR is enabled - this is the gate check
    logger.info("\nRunning gate check...")
    rr_enabled = check_rrs_enabled()

    if not rr_enabled:
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info("RRS Enablement Check: SKIPPED (RR not enabled)")
        logger.info("All subsequent checks: SKIPPED (RR not enabled)")
        logger.info("\n" + "-" * 60)
        logger.info("Rack Resiliency is not enabled on this system")
        logger.info("This is expected behavior for systems without RR configured")
        logger.info("-" * 60)
        logger.info("\nTests completed (RR not enabled - no failures)")
        sys.exit(0)

    # RR is enabled - run all checks
    checks = [
        ("Kubernetes Zones Check", check_k8s_zones),
        ("Ceph Zones Check", check_ceph_zones),
        ("Helm Chart Check", check_helm_chart),
        ("Deployment Check", check_deployment),
        ("ConfigMaps Check", check_configmaps),
        ("Zones List Check", check_zones_list),
        ("Critical Services List Check", check_critical_services_list),
        ("Critical Services Status Check", check_critical_services_status),
    ]

    results = [("RRS Enablement Check", True)]  # Already passed
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Exception in %s: %s", check_name, exc)
            results.append((check_name, False))

    # Print summary
    logger.info("\n%s", "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    passed = 0
    failed = 0
    for check_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info("%s: %s", check_name, status)
        if result:
            passed += 1
        else:
            failed += 1

    logger.info("\n%s", "-" * 60)
    logger.info("Total: %d | Passed: %d | Failed: %d",
                len(results), passed, failed)
    logger.info("-" * 60)

    # Exit with error if any checks failed
    if failed > 0:
        sys.exit(1)

    logger.info("\nAll RRS checks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
