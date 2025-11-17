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

        logger.error("FAILURE: Rack Resiliency is not enabled")
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

    logger.error("FAILURE: No Kubernetes zones found")
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

    if returncode != 0 or not output:
        logger.error("FAILURE: No Ceph racks/zones found")
        return False

    rack_count = len(output.split('\n'))
    logger.info("SUCCESS: Found %d Ceph racks/zones", rack_count)
    return True


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
    cmd = 'kubectl get deployment cray-rrs -n rack-resiliency -o jsonpath="{.metadata.name}"'
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "cray-rrs":
        logger.error("FAILURE: cray-rrs deployment not found")
        return False

    logger.info("INFO: cray-rrs deployment exists")

    # Check pod status
    cmd = ('kubectl get pods -n rack-resiliency '
           '-l app.kubernetes.io/instance=cray-rrs '
           '-o jsonpath="{.items[0].status.phase}"')
    output, returncode = run_command(cmd)

    if returncode != 0:
        logger.error("Failed to get pod status")
        return False

    if output == "Running":
        logger.info("SUCCESS: cray-rrs pod is Running")
        return True

    logger.error(
        "FAILURE: cray-rrs pod status is %s (expected: Running)",
        output
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
           '-o jsonpath="{.metadata.name}"')
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "rrs-mon-static":
        logger.error("FAILURE: rrs-mon-static ConfigMap not found")
        return False

    logger.info("INFO: rrs-mon-static ConfigMap exists")

    # Check rrs-mon-dynamic
    cmd = ('kubectl get configmap rrs-mon-dynamic -n rack-resiliency '
           '-o jsonpath="{.metadata.name}"')
    output, returncode = run_command(cmd)

    if returncode != 0 or output != "rrs-mon-dynamic":
        logger.error("FAILURE: rrs-mon-dynamic ConfigMap not found")
        return False

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
    """
    logger.info("=" * 60)
    logger.info("Running Rack Resiliency Service (RRS) Checks")
    logger.info("=" * 60)

    checks = [
        ("RRS Enablement Check", check_rrs_enabled),
        ("Kubernetes Zones Check", check_k8s_zones),
        ("Ceph Zones Check", check_ceph_zones),
        ("Helm Chart Check", check_helm_chart),
        ("Deployment Check", check_deployment),
        ("ConfigMaps Check", check_configmaps),
        ("Zones List Check", check_zones_list),
        ("Critical Services List Check", check_critical_services_list),
        ("Critical Services Status Check", check_critical_services_status),
    ]

    results = []
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
