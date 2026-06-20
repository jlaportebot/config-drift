"""Tests for the semantic drift detector."""

from config_drift.detectors.semantic import SemanticDriftDetector
from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.models.drift import DriftSeverity, DriftType


def _make_k8s_config(content, resource_id="Deployment/my-app"):
    """Helper to create Kubernetes ParsedConfig."""
    return ParsedConfig(
        source=ConfigSource.KUBERNETES,
        format=ConfigFormat.YAML,
        content=content,
        resource_id=resource_id,
    )


class TestSemanticDriftDetector:
    """Tests for SemanticDriftDetector."""

    def test_no_drift(self):
        baseline = _make_k8s_config({"spec": {"replicas": 3}})
        current = _make_k8s_config({"spec": {"replicas": 3}})
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) == 0

    def test_critical_field_change(self):
        baseline = _make_k8s_config(
            {
                "spec": {"replicas": 3},
            }
        )
        current = _make_k8s_config(
            {
                "spec": {"replicas": 5},
            }
        )
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1
        # Replicas change should be at least HIGH severity
        replica_drifts = [d for d in drifts if "replicas" in d.path]
        assert len(replica_drifts) >= 1
        assert replica_drifts[0].severity.value in ("high", "critical")

    def test_added_field(self):
        baseline = _make_k8s_config({"spec": {"replicas": 3}})
        current = _make_k8s_config({"spec": {"replicas": 3, "new_field": "value"}})
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1
        added_drifts = [d for d in drifts if d.drift_type == DriftType.ADDED]
        assert len(added_drifts) >= 1

    def test_removed_field(self):
        baseline = _make_k8s_config({"spec": {"replicas": 3, "strategy": "rolling"}})
        current = _make_k8s_config({"spec": {"replicas": 3}})
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1
        removed_drifts = [d for d in drifts if d.drift_type == DriftType.REMOVED]
        assert len(removed_drifts) >= 1

    def test_docker_compose_source(self):
        baseline = ParsedConfig(
            source=ConfigSource.DOCKER_COMPOSE,
            format=ConfigFormat.YAML,
            content={"services": {"web": {"image": "nginx:1.19"}}},
            resource_id="compose/docker-compose",
        )
        current = ParsedConfig(
            source=ConfigSource.DOCKER_COMPOSE,
            format=ConfigFormat.YAML,
            content={"services": {"web": {"image": "nginx:1.25"}}},
            resource_id="compose/docker-compose",
        )
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1
        # Image change should be critical
        image_drifts = [d for d in drifts if "image" in d.path]
        assert len(image_drifts) >= 1

    def test_terraform_source(self):
        baseline = ParsedConfig(
            source=ConfigSource.TERRAFORM,
            format=ConfigFormat.HCL,
            content={"resource": {"aws_instance": {"web": {"instance_type": "t3.micro"}}}},
            resource_id="terraform/main",
        )
        current = ParsedConfig(
            source=ConfigSource.TERRAFORM,
            format=ConfigFormat.HCL,
            content={"resource": {"aws_instance": {"web": {"instance_type": "t3.large"}}}},
            resource_id="terraform/main",
        )
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1

    def test_helm_source(self):
        baseline = ParsedConfig(
            source=ConfigSource.HELM,
            format=ConfigFormat.YAML,
            content={
                "metadata": {"name": "my-chart", "version": "1.0.0"},
                "values": {"replicaCount": 3},
            },
            resource_id="chart/my-chart",
        )
        current = ParsedConfig(
            source=ConfigSource.HELM,
            format=ConfigFormat.YAML,
            content={
                "metadata": {"name": "my-chart", "version": "1.0.0"},
                "values": {"replicaCount": 5},
            },
            resource_id="chart/my-chart",
        )
        detector = SemanticDriftDetector()
        drifts = detector.detect(baseline, current)
        assert len(drifts) >= 1
        # replicaCount change should be critical
        replica_drifts = [d for d in drifts if "replicaCount" in d.path]
        assert len(replica_drifts) >= 1
        assert replica_drifts[0].severity == DriftSeverity.CRITICAL
