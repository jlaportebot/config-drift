"""Parser for Kubernetes resources."""

from pathlib import Path
from typing import Any

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.parsers.base import ConfigParser, ParseResult


class KubernetesParser(ConfigParser):
    """Parser for Kubernetes cluster resources."""

    # Resource kinds to fetch
    RESOURCE_KINDS = [
        "ConfigMap",
        "Secret",
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Service",
        "Ingress",
        "PersistentVolume",
        "PersistentVolumeClaim",
        "ServiceAccount",
        "Role",
        "RoleBinding",
        "ClusterRole",
        "ClusterRoleBinding",
        "NetworkPolicy",
        "ResourceQuota",
        "LimitRange",
        "HorizontalPodAutoscaler",
        "CronJob",
        "Job",
    ]

    @property
    def source_type(self) -> ConfigSource:
        return ConfigSource.KUBERNETES

    @property
    def supported_formats(self) -> list[ConfigFormat]:
        return [ConfigFormat.YAML]

    def __init__(self, kubeconfig: str | None = None, context: str | None = None):
        self.kubeconfig = kubeconfig
        self.context = context
        self._api_client = None

    def _get_api_client(self):
        if self._api_client is None:
            if self.kubeconfig:
                config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            else:
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config(context=self.context)
            self._api_client = client.ApiClient()
        return self._api_client

    def parse(self, source: str | Path = "", **kwargs) -> ParseResult:
        """Parse Kubernetes resources from cluster.

        Args:
            source: Ignored for Kubernetes (uses cluster connection)
            **kwargs:
                namespaces: List of namespaces to scan (default: all)
                kinds: List of resource kinds to fetch (default: all RESOURCE_KINDS)
                label_selector: Label selector string
        """
        namespaces = kwargs.get("namespaces")
        kinds = kwargs.get("kinds", self.RESOURCE_KINDS)
        label_selector = kwargs.get("label_selector")

        configs = []
        errors = []

        try:
            api_client = self._get_api_client()

            # Get namespaces to scan
            if not namespaces:
                v1 = client.CoreV1Api(api_client)
                ns_list = v1.list_namespace(label_selector=label_selector)
                namespaces = [ns.metadata.name for ns in ns_list.items]

            for ns in namespaces:
                for kind in kinds:
                    try:
                        resources = self._fetch_resources(api_client, kind, ns, label_selector)
                        for resource in resources:
                            parsed = self._parse_resource(resource, ns)
                            if parsed:
                                configs.append(parsed)
                    except ApiException as e:
                        if e.status != 404:  # Ignore not found (API group not available)
                            errors.append(f"Error fetching {kind} in {ns}: {e}")
                    except Exception as e:
                        errors.append(f"Error parsing {kind} in {ns}: {e}")

        except Exception as e:
            errors.append(f"Kubernetes connection error: {e}")

        return ParseResult(configs=configs, errors=errors)

    def _fetch_resources(self, api_client, kind: str, namespace: str, label_selector: str | None):
        """Fetch resources of a given kind from a namespace."""
        # This is simplified - in practice you'd use dynamic client for all resource types
        # For now, handle common types via specific APIs
        v1 = client.CoreV1Api(api_client)
        apps_v1 = client.AppsV1Api(api_client)
        networking_v1 = client.NetworkingV1Api(api_client)
        rbac_v1 = client.RbacAuthorizationV1Api(api_client)
        batch_v1 = client.BatchV1Api(api_client)
        autoscaling_v2 = client.AutoscalingV2Api(api_client)

        kind_lower = kind.lower()

        if kind_lower == "configmap":
            return v1.list_namespaced_config_map(namespace, label_selector=label_selector).items
        if kind_lower == "secret":
            return v1.list_namespaced_secret(namespace, label_selector=label_selector).items
        if kind_lower == "service":
            return v1.list_namespaced_service(namespace, label_selector=label_selector).items
        if kind_lower == "persistentvolumeclaim":
            return v1.list_namespaced_persistent_volume_claim(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "serviceaccount":
            return v1.list_namespaced_service_account(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "resourcequota":
            return v1.list_namespaced_resource_quota(namespace, label_selector=label_selector).items
        if kind_lower == "limitrange":
            return v1.list_namespaced_limit_range(namespace, label_selector=label_selector).items
        if kind_lower == "deployment":
            return apps_v1.list_namespaced_deployment(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "statefulset":
            return apps_v1.list_namespaced_stateful_set(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "daemonset":
            return apps_v1.list_namespaced_daemon_set(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "ingress":
            return networking_v1.list_namespaced_ingress(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "networkpolicy":
            return networking_v1.list_namespaced_network_policy(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "role":
            return rbac_v1.list_namespaced_role(namespace, label_selector=label_selector).items
        if kind_lower == "rolebinding":
            return rbac_v1.list_namespaced_role_binding(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "horizontalpodautoscaler":
            return autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(
                namespace, label_selector=label_selector
            ).items
        if kind_lower == "cronjob":
            return batch_v1.list_namespaced_cron_job(namespace, label_selector=label_selector).items
        if kind_lower == "job":
            return batch_v1.list_namespaced_job(namespace, label_selector=label_selector).items

        return []

    def _parse_resource(self, resource, namespace: str) -> ParsedConfig | None:
        """Convert Kubernetes resource to ParsedConfig."""
        try:
            # Convert to dict, removing managed fields
            resource_dict = self._sanitize_resource(resource.to_dict())
            raw_yaml = yaml.dump(resource_dict, sort_keys=False)

            return self._create_parsed_config(
                content=resource_dict,
                resource_id=f"{resource.kind}/{resource.metadata.name}",
                namespace=namespace,
                labels=resource.metadata.labels or {},
                annotations=resource.metadata.annotations or {},
                raw_content=raw_yaml,
            )
        except Exception:
            return None

    def _sanitize_resource(self, resource: dict) -> dict:
        """Remove Kubernetes-managed fields that change automatically."""
        fields_to_remove = [
            "status",
            "metadata.uid",
            "metadata.resourceVersion",
            "metadata.generation",
            "metadata.creationTimestamp",
            "metadata.managedFields",
            "metadata.selfLink",
        ]

        def remove_fields(obj: Any, prefix: str = "") -> Any:
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    if full_key not in fields_to_remove and not any(
                        full_key.startswith(f + ".") for f in fields_to_remove
                    ):
                        result[k] = remove_fields(v, full_key)
                return result
            if isinstance(obj, list):
                return [remove_fields(item, prefix) for item in obj]
            return obj

        return remove_fields(resource)
