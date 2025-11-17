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
    Returns:
        bool: True if deployment is healthy, False otherwise
    """
    logger.info("\n=== Checking RRS Deployment ===")

    # Check deployment exists
    cmd = 'kubectl get deployment cray-rrs -n rack-resiliency -o jsonpath="{.metadata.name}" 2>/dev/null'
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "cray-rrs":
        logger.error("FAILURE: cray-rrs deployment not found")
        return False

    logger.info("INFO: cray-rrs deployment exists")

    # Check pod status
    pod_cmd = ('kubectl get pods -n rack-resiliency '
               '-l app.kubernetes.io/instance=cray-rrs '
               '-o jsonpath="{.items[0].status.phase}" 2>/dev/null')
    pod_status, pod_returncode = run_command(pod_cmd)

    if pod_returncode != 0 or not pod_status:
        logger.error("FAILURE: Failed to get pod status")
        return False

    logger.info("Current pod status: %s", pod_status)

    if pod_status == "Running":
        logger.info("SUCCESS: cray-rrs pod is Running")
        return True

    logger.error(
        "FAILURE: cray-rrs pod status is %s (expected: Running)",
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
    Implements sequential gate logic - each check must pass before proceeding.
    """
    logger.info("=" * 60)
    logger.info("Running Rack Resiliency Service (RRS) Checks")
    logger.info("=" * 60)

    results = []
    skipped_tests = []

    # Gate 1: Check if RR is enabled
    logger.info("\n[Gate Check 1/6] Checking RRS Enablement...")
    rr_enabled = check_rrs_enabled()
    results.append(("RRS Enablement Check", rr_enabled))

    if not rr_enabled:
        # RR not enabled - verify deployment is in Pending/Init state (negative test)
        logger.info("\n[Negative Test] Verifying deployment state when RR is disabled...")
        deployment_state_ok = _check_deployment_when_disabled()
        results.append(("Deployment State Check (RR Disabled)", deployment_state_ok))
        
        skipped_tests = [
            "Kubernetes Zones Check",
            "Ceph Zones Check",
            "Helm Chart Check",
            "ConfigMaps Check",
            "Deployment Check",
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info("RRS Enablement Check: PASS (RR not enabled - expected)")
        logger.info(
            "Deployment State Check (RR Disabled): %s",
            "PASS" if deployment_state_ok else "FAIL"
        )
        for test in skipped_tests:
            logger.info("%s: SKIPPED", test)
        logger.info("\n" + "-" * 60)
        logger.info("Rack Resiliency is not enabled on this system")
        logger.info("This is expected behavior for systems without RR configured")
        logger.info("-" * 60)
        
        if deployment_state_ok:
            logger.info("\nTests completed (RR not enabled - deployment in expected state)")
            sys.exit(0)
        else:
            logger.error("\nTests failed (deployment not in expected Pending state)")
            sys.exit(1)

    # Gate 2: Check K8s zones
    logger.info("\n[Gate Check 2/6] Checking Kubernetes Zones...")
    k8s_zones_ok = check_k8s_zones()
    results.append(("Kubernetes Zones Check", k8s_zones_ok))

    if not k8s_zones_ok:
        skipped_tests = [
            "Ceph Zones Check",
            "Helm Chart Check",
            "ConfigMaps Check",
            "Deployment Check",
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.warning("\nK8s zones not configured - skipping remaining tests")
        _print_summary(results, skipped_tests)
        sys.exit(1)

    # Gate 3: Check Ceph zones
    logger.info("\n[Gate Check 3/6] Checking Ceph Zones...")
    ceph_zones_ok = check_ceph_zones()
    results.append(("Ceph Zones Check", ceph_zones_ok))

    if not ceph_zones_ok:
        skipped_tests = [
            "Helm Chart Check",
            "ConfigMaps Check",
            "Deployment Check",
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.warning("\nCeph zones not configured - skipping remaining tests")
        _print_summary(results, skipped_tests)
        sys.exit(1)

    # Gate 4: Check Helm chart
    logger.info("\n[Gate Check 4/6] Checking Helm Chart...")
    helm_ok = check_helm_chart()
    results.append(("Helm Chart Check", helm_ok))

    if not helm_ok:
        skipped_tests = [
            "ConfigMaps Check",
            "Deployment Check",
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.warning("\nHelm chart not deployed - skipping remaining tests")
        _print_summary(results, skipped_tests)
        sys.exit(1)

    # Gate 5: Check ConfigMaps
    logger.info("\n[Gate Check 5/6] Checking ConfigMaps...")
    configmaps_ok = check_configmaps()
    results.append(("ConfigMaps Check", configmaps_ok))

    if not configmaps_ok:
        skipped_tests = [
            "Deployment Check",
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.warning("\nConfigMaps not found - skipping remaining tests")
        _print_summary(results, skipped_tests)
        sys.exit(1)

    # Gate 6: Check deployment
    logger.info("\n[Gate Check 6/6] Checking Deployment...")
    deployment_ok = check_deployment()
    results.append(("Deployment Check", deployment_ok))

    if not deployment_ok:
        skipped_tests = [
            "Zones List Check",
            "Critical Services List Check",
            "Critical Services Status Check",
        ]
        logger.warning("\nDeployment not healthy - skipping remaining tests")
        _print_summary(results, skipped_tests)
        sys.exit(1)

    # All gates passed - run remaining validation checks
    logger.info("\nAll gate checks passed - running validation checks...")

    validation_checks = [
        ("Zones List Check", check_zones_list),
        ("Critical Services List Check", check_critical_services_list),
        ("Critical Services Status Check", check_critical_services_status),
    ]

    for check_name, check_func in validation_checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Exception in %s: %s", check_name, exc)
            results.append((check_name, False))

    # Print summary
    _print_summary(results, [])

    # Exit with error if any checks failed
    failed = sum(1 for _, result in results if not result)
    if failed > 0:
        sys.exit(1)

    logger.info("\nAll RRS checks passed!")
    sys.exit(0)


def _print_summary(results, skipped_tests):
    """
    Print summary of test results.
    Args:
        results: List of tuples (test_name, result)
        skipped_tests: List of test names that were skipped
    """
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

    for test_name in skipped_tests:
        logger.info("%s: SKIPPED", test_name)

    logger.info("\n%s", "-" * 60)
    logger.info(
        "Total: %d | Passed: %d | Failed: %d | Skipped: %d",
        len(results) + len(skipped_tests),
        passed,
        failed,
        len(skipped_tests)
    )
    logger.info("-" * 60)


def _check_deployment_when_disabled():
    """
    Check deployment state when RR is disabled.
    Expects deployment to be in Pending or NotFound state.
    Returns:
        bool: True if deployment is in expected state, False otherwise
    """
    logger.info("=== Checking Deployment State (RR Disabled) ===")
    
    # Check if deployment exists
    cmd = 'kubectl get deployment cray-rrs -n rack-resiliency -o jsonpath="{.metadata.name}" 2>/dev/null'
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "cray-rrs":
        logger.info("INFO: cray-rrs deployment not found (expected when RR disabled)")
        return True

    logger.info("INFO: cray-rrs deployment exists")

    # Check pod status
    pod_cmd = ('kubectl get pods -n rack-resiliency '
               '-l app.kubernetes.io/instance=cray-rrs '
               '-o jsonpath="{.items[0].status.phase}" 2>/dev/null')
    pod_status, pod_returncode = run_command(pod_cmd)

    if pod_returncode != 0 or not pod_status:
        logger.info("INFO: No pod found (expected when RR disabled)")
        return True

    logger.info("Current pod status: %s", pod_status)

    if pod_status == "Pending":
        logger.info(
            "SUCCESS: Deployment is in Pending state as expected "
            "(RR disabled)"
        )
        return True

    logger.error(
        "FAILURE: When RR is disabled, deployment should be Pending or NotFound, "
        "but found: %s",
        pod_status
    )
    return False


if __name__ == "__main__":
    main()
