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
"""Shared Python function library: Kubernetes"""

import logging
from typing import Any

import kubernetes
import kubernetes.client
import kubernetes.client.api
import kubernetes.config


# To help for type hinting in other modules
CoreV1API = kubernetes.client.api.core_v1_api.CoreV1Api
V1ClientConfiguration = kubernetes.client.configuration.Configuration
V1ConfigMap = kubernetes.client.models.v1_config_map.V1ConfigMap
V1Secret = kubernetes.client.models.v1_secret.V1Secret
V1Service = kubernetes.client.models.v1_service.V1Service


def get_configuration() -> V1ClientConfiguration:
    """
    Creates a default Kubernetes configuration and returns it.
    """
    logging.debug("Loading Kubernetes configuration")
    kubernetes.config.load_kube_config()
    logging.debug("Getting default copy of Kubernetes configuration")
    return kubernetes.client.Configuration().get_default_copy()


def get_api_client() -> CoreV1API:
    """
    Creates a Kubernetes API client and returns it.
    """
    logging.debug("Initializing Kubernetes client")
    k8s_config = get_configuration()
    logging.debug("Setting client default Kubernetes configuration")
    kubernetes.client.Configuration.set_default(k8s_config)
    return kubernetes.client.api.core_v1_api.CoreV1Api()


class Client:
    """
    Kubernetes API client object. Takes care of the setup steps and provides simplified API calls.
    """
    def __init__(self):
        self.client = get_api_client()

    def get_config_map(self, name: str, namespace: str) -> V1ConfigMap:
        """
        Wrapper for read_namespaced_config_map function
        """
        configmap_label = f"{namespace}/{name} Kubernetes configmap"
        logging.debug("Getting %s", configmap_label)
        return self.client.read_namespaced_config_map(name=name, namespace=namespace)

    def get_config_map_data(self, name: str, namespace: str) -> Any:
        """
        Calls get_config_map function, then extracts the data field from the response.
        """
        configmap_label = f"{namespace}/{name} Kubernetes configmap"
        configmap = self.get_config_map(name=name, namespace=namespace)
        return configmap.data

    def get_secret(self, name: str, namespace: str) -> V1Secret:
        """
        Wrapper for read_namespaced_secret function
        """
        secret_label = f"{namespace}/{name} Kubernetes secret"
        logging.debug("Getting %s", secret_label)
        return self.client.read_namespaced_secret(name=name, namespace=namespace)

    def get_secret_data(self, name: str, namespace: str) -> Any:
        """
        Calls get_secret function, then extracts the data field from the response.
        """
        secret_label = f"{namespace}/{name} Kubernetes secret"
        secret = self.get_secret(name=name, namespace=namespace)
        return secret.data

    def get_service(self, name: str, namespace: str) -> V1Service:
        """
        Wrapper for read_namespaced_service function
        """
        service_label = f"{namespace}/{name} Kubernetes service"
        logging.debug("Getting %s", service_label)
        return self.client.read_namespaced_service(name=name, namespace=namespace)
