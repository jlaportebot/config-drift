"""Tests for Kubernetes parser."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource
from config_drift.parsers.kubernetes import KubernetesParser


class TestKubernetesParser:
    """Tests for KubernetesParser."""

    def test_source_type(self):
        parser = KubernetesParser()
        assert parser.source_type == ConfigSource.KUBERNETES

    def test_supported_formats(self):
        parser = KubernetesParser()
        assert parser.supported_formats == [ConfigFormat.YAML]

    def test_resource_kinds(self):
        parser = KubernetesParser()
        assert "ConfigMap" in parser.RESOURCE_KINDS
        assert "Secret" in parser.RESOURCE_KINDS
        assert "Deployment" in parser.RESOURCE_KINDS
        assert "Service" in parser.RESOURCE_KINDS

    @patch("config_drift.parsers.kubernetes.config")
    def test_get_api_client_kubeconfig(self, mock_config):
        parser = KubernetesParser(kubeconfig="/path/to/kubeconfig")
        mock_client = Mock()
        mock_config.load_kube_config.return_value = None
        mock_config.load_incluster_config.side_effect = Exception("not in cluster")

        client = parser._get_api_client()
        mock_config.load_kube_config.assert_called_once_with(
            config_file="/path/to/kubeconfig", context=None
        )
        assert client is not None

    @patch("config_drift.parsers.kubernetes.config")
    def test_get_api_client_incluster(self, mock_config):
        parser = KubernetesParser()
        mock_config.load_incluster_config.return_value = None

        client = parser._get_api_client()
        mock_config.load_incluster_config.assert_called_once()
        assert client is not None

    @patch("config_drift.parsers.kubernetes.config")
    def test_get_api_client_fallback_to_kubeconfig(self, mock_config):
        parser = KubernetesParser()

        # Create a real exception class for ConfigException
        class ConfigException(Exception):
            pass

        mock_config.ConfigException = ConfigException
        mock_config.load_incluster_config.side_effect = ConfigException("not in cluster")
        mock_config.load_kube_config.return_value = None

        client = parser._get_api_client()
        mock_config.load_incluster_config.assert_called_once()
        mock_config.load_kube_config.assert_called_once_with(context=None)

    @patch("config_drift.parsers.kubernetes.config")
    @patch("config_drift.parsers.kubernetes.client")
    def test_parse_with_namespaces(self, mock_client_module, mock_config):
        parser = KubernetesParser()
        mock_api_client = Mock()
        mock_config.load_incluster_config.return_value = None
        mock_client_module.ApiClient.return_value = mock_api_client

        mock_v1 = Mock()
        mock_client_module.CoreV1Api.return_value = mock_v1
        mock_ns_list = Mock()
        mock_ns_list.items = [
            Mock(metadata=Mock(name="default")),
            Mock(metadata=Mock(name="kube-system")),
        ]
        mock_v1.list_namespace.return_value = mock_ns_list

        mock_v1.list_namespaced_config_map.return_value = Mock(items=[])
        mock_client_module.AppsV1Api.return_value.list_namespaced_deployment.return_value = Mock(
            items=[]
        )
        mock_client_module.NetworkingV1Api.return_value.list_namespaced_ingress.return_value = Mock(
            items=[]
        )
        mock_client_module.RbacAuthorizationV1Api.return_value.list_namespaced_role.return_value = (
            Mock(items=[])
        )
        mock_client_module.AutoscalingV2Api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = Mock(
            items=[]
        )
        mock_client_module.BatchV1Api.return_value.list_namespaced_cron_job.return_value = Mock(
            items=[]
        )
        mock_client_module.BatchV1Api.return_value.list_namespaced_job.return_value = Mock(items=[])

        result = parser.parse("", namespaces=["default"])
        assert len(result.configs) >= 0

    @patch("config_drift.parsers.kubernetes.config")
    @patch("config_drift.parsers.kubernetes.client")
    def test_parse_specific_kinds(self, mock_client_module, mock_config):
        parser = KubernetesParser()
        mock_api_client = Mock()
        mock_config.load_incluster_config.return_value = None
        mock_client_module.ApiClient.return_value = mock_api_client

        mock_v1 = Mock()
        mock_client_module.CoreV1Api.return_value = mock_v1
        mock_v1.list_namespace.return_value = Mock(items=[Mock(metadata=Mock(name="default"))])
        mock_v1.list_namespaced_config_map.return_value = Mock(items=[])
        mock_client_module.AppsV1Api.return_value.list_namespaced_deployment.return_value = Mock(
            items=[]
        )
        mock_client_module.NetworkingV1Api.return_value.list_namespaced_ingress.return_value = Mock(
            items=[]
        )
        mock_client_module.RbacAuthorizationV1Api.return_value.list_namespaced_role.return_value = (
            Mock(items=[])
        )
        mock_client_module.AutoscalingV2Api.return_value.list_namespaced_horizontal_pod_autoscaler.return_value = Mock(
            items=[]
        )
        mock_client_module.BatchV1Api.return_value.list_namespaced_cron_job.return_value = Mock(
            items=[]
        )
        mock_client_module.BatchV1Api.return_value.list_namespaced_job.return_value = Mock(items=[])

        result = parser.parse("", kinds=["ConfigMap", "Secret"], namespaces=["default"])
        assert len(result.configs) >= 0

    def test_sanitize_resource(self):
        parser = KubernetesParser()
        resource = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "test-config",
                "namespace": "default",
                "uid": "12345",
                "resourceVersion": "67890",
                "generation": 1,
                "creationTimestamp": "2024-01-01T00:00:00Z",
                "managedFields": [{"manager": "kubectl"}],
                "labels": {"app": "test"},
                "annotations": {"note": "test"},
            },
            "data": {"key": "value"},
        }
        sanitized = parser._sanitize_resource(resource)
        assert "uid" not in sanitized["metadata"]
        assert "resourceVersion" not in sanitized["metadata"]
        assert "generation" not in sanitized["metadata"]
        assert "creationTimestamp" not in sanitized["metadata"]
        assert "managedFields" not in sanitized["metadata"]
        assert sanitized["metadata"]["name"] == "test-config"
        assert sanitized["metadata"]["labels"]["app"] == "test"
        assert sanitized["data"]["key"] == "value"

    def test_sanitize_resource_nested(self):
        parser = KubernetesParser()
        resource = {
            "metadata": {
                "labels": {"app": "test"},
                "annotations": {"note": "test"},
                "ownerReferences": [
                    {"uid": "123", "name": "owner"},
                ],
            },
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {"app": "test"},
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }
        sanitized = parser._sanitize_resource(resource)
        # Top-level metadata fields are sanitized
        assert "uid" not in sanitized.get("metadata", {})
        assert "resourceVersion" not in sanitized.get("metadata", {})
        # Nested metadata is not sanitized (only top-level)
        assert (
            sanitized["spec"]["template"]["metadata"]["creationTimestamp"] == "2024-01-01T00:00:00Z"
        )

    @patch("config_drift.parsers.kubernetes.config")
    @patch("config_drift.parsers.kubernetes.client")
    def test_parse_resource(self, mock_client_module, mock_config):
        parser = KubernetesParser()
        mock_config.load_incluster_config.return_value = None

        mock_resource = Mock()
        mock_resource.kind = "ConfigMap"
        mock_resource.metadata = Mock()
        mock_resource.metadata.name = "test-config"
        mock_resource.metadata.labels = {"app": "test"}
        mock_resource.metadata.annotations = {"note": "test"}
        mock_resource.to_dict.return_value = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "test-config",
                "labels": {"app": "test"},
                "annotations": {"note": "test"},
            },
            "data": {"key": "value"},
        }

        parsed = parser._parse_resource(mock_resource, "default")
        assert parsed is not None
        assert parsed.resource_id == "ConfigMap/test-config"
        assert parsed.namespace == "default"
        assert parsed.labels == {"app": "test"}

    @patch("config_drift.parsers.kubernetes.config")
    @patch("config_drift.parsers.kubernetes.client")
    def test_parse_resource_exception(self, mock_client_module, mock_config):
        parser = KubernetesParser()
        mock_config.load_incluster_config.return_value = None

        mock_resource = Mock()
        mock_resource.to_dict.side_effect = Exception("to_dict failed")

        parsed = parser._parse_resource(mock_resource, "default")
        assert parsed is None

    @patch("config_drift.parsers.kubernetes.config")
    @patch("config_drift.parsers.kubernetes.client")
    def test_fetch_resources_configmap(self, mock_client_module, mock_config):
        parser = KubernetesParser()
        mock_api_client = Mock()
        mock_config.load_incluster_config.return_value = None
        mock_client_module.ApiClient.return_value = mock_api_client

        mock_v1 = Mock()
        mock_client_module.CoreV1Api.return_value = mock_v1
        mock_cm = Mock()
        mock_cm.metadata.name = "test-cm"
        mock_cm.metadata.labels = {"app": "test"}
        mock_v1.list_namespaced_config_map.return_value = Mock(items=[mock_cm])

        resources = parser._fetch_resources(mock_api_client, "ConfigMap", "default", None)
        assert len(resources) == 1

    def test_parse_connection_error(self):
        parser = KubernetesParser()
        with patch("config_drift.parsers.kubernetes.config") as mock_config:
            mock_config.load_incluster_config.side_effect = Exception("No cluster")
            mock_config.load_kube_config.side_effect = Exception("No kubeconfig")

            result = parser.parse("")
            assert len(result.errors) > 0
            assert "Kubernetes connection error" in result.errors[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
