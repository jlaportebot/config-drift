"""Tests for Docker Compose parser."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from config_drift.models.config import ConfigFormat, ConfigSource
from config_drift.parsers.docker_compose import DockerComposeParser


class TestDockerComposeParser:
    """Tests for DockerComposeParser."""

    def test_source_type(self):
        parser = DockerComposeParser()
        assert parser.source_type == ConfigSource.DOCKER_COMPOSE

    def test_supported_formats(self):
        parser = DockerComposeParser()
        assert parser.supported_formats == [ConfigFormat.YAML]

    def test_can_parse_docker_compose_yml(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\nservices:\n  web:\n    image: nginx\n")
        assert parser.can_parse(compose_file) is True

    def test_can_parse_docker_compose_yaml(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yaml"
        compose_file.write_text("version: '3.8'\nservices:\n  web:\n    image: nginx\n")
        assert parser.can_parse(compose_file) is True

    def test_cannot_parse_other_files(self, tmp_path):
        parser = DockerComposeParser()
        other_file = tmp_path / "config.txt"
        other_file.write_text("key: value\n")
        assert parser.can_parse(other_file) is False

    def test_parse_compose_file(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_content = """version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    environment:
      - ENV=production
  db:
    image: postgres:13
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
"""
        compose_file.write_text(compose_content)

        result = parser.parse(str(compose_file))
        assert len(result.configs) == 1
        assert result.configs[0].source == ConfigSource.DOCKER_COMPOSE
        assert "services" in result.configs[0].content
        assert "web" in result.configs[0].content["services"]
        assert "db" in result.configs[0].content["services"]
        assert "volumes" in result.configs[0].content

    def test_parse_compose_file_without_version(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_content = """services:
  web:
    image: nginx:latest
"""
        compose_file.write_text(compose_content)

        result = parser.parse(str(compose_file))
        assert len(result.configs) == 1
        assert result.configs[0].content.get("version") == "3.8"  # default version

    def test_parse_compose_directory(self, tmp_path):
        parser = DockerComposeParser()
        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()
        (compose_dir / "docker-compose.yml").write_text(
            "version: '3.8'\nservices:\n  web:\n    image: nginx\n"
        )
        (compose_dir / "docker-compose.prod.yml").write_text(
            "version: '3.8'\nservices:\n  web:\n    image: nginx:prod\n"
        )

        result = parser.parse(str(compose_dir))
        assert len(result.configs) == 2

    def test_parse_nonexistent_path(self):
        parser = DockerComposeParser()
        result = parser.parse("/nonexistent/path")
        assert len(result.errors) > 0

    def test_parse_empty_file(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("")
        result = parser.parse(str(compose_file))
        assert len(result.configs) == 0

    def test_parse_invalid_yaml(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("invalid: yaml: [")
        result = parser.parse(str(compose_file))
        assert len(result.configs) == 0
        assert len(result.errors) > 0

    def test_normalize_service_removes_runtime_fields(self):
        parser = DockerComposeParser()
        service = {
            "image": "nginx",
            "container_name": "my-container",
            "build": ".",
            "deploy": {"replicas": 3},
            "extends": {"service": "base"},
            "ports": ["80:80"],
        }
        normalized = parser._normalize_service(service)  # noqa: SLF001
        assert "container_name" not in normalized
        assert "build" not in normalized
        assert "deploy" not in normalized
        assert "extends" not in normalized
        assert "ports" in normalized

    def test_normalize_compose(self):
        parser = DockerComposeParser()
        content = {
            "version": "3.9",
            "services": {
                "web": {
                    "image": "nginx",
                    "container_name": "web-container",
                },
            },
            "volumes": {"data": {}},
            "networks": {"frontend": {}},
        }
        normalized = parser._normalize_compose(content)  # noqa: SLF001
        assert normalized["version"] == "3.9"
        assert "services" in normalized
        assert "volumes" in normalized
        assert "networks" in normalized
        assert "container_name" not in normalized["services"]["web"]

    @patch("config_drift.parsers.docker_compose.docker")
    def test_parse_running_containers(self, mock_docker, tmp_path):
        parser = DockerComposeParser()
        mock_client = Mock()
        mock_docker.from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.attrs = {
            "Config": {
                "Image": "nginx:latest",
                "Cmd": ["nginx", "-g", "daemon off;"],
                "Env": ["ENV=prod"],
                "Labels": {"app": "web"},
            },
            "HostConfig": {
                "PortBindings": {
                    "80/tcp": [{"HostPort": "8080"}],
                },
                "RestartPolicy": {"Name": "unless-stopped"},
            },
            "NetworkSettings": {
                "Networks": {"bridge": {}, "custom": {}},
            },
            "Mounts": [
                {"Type": "bind", "Source": "/host/data", "Destination": "/container/data"},
                {"Type": "volume", "Name": "my-volume", "Destination": "/container/vol"},
            ],
        }
        mock_client.containers.list.return_value = [mock_container]

        result = parser.parse("running")
        assert len(result.configs) == 1
        assert result.configs[0].resource_id == "container/test-container"
        assert "services" in result.configs[0].content
        assert "test-container" in result.configs[0].content["services"]

    @patch("config_drift.parsers.docker_compose.docker")
    def test_parse_running_containers_docker_error(self, mock_docker):
        parser = DockerComposeParser()
        mock_docker.from_env.side_effect = Exception("Docker not running")

        result = parser.parse("running")
        assert len(result.configs) == 0
        assert len(result.errors) > 0
        assert "Docker client error" in result.errors[0]

    def test_extract_ports(self):
        parser = DockerComposeParser()
        attrs = {
            "HostConfig": {
                "PortBindings": {
                    "80/tcp": [{"HostPort": "8080"}],
                    "443/tcp": [{"HostPort": "8443"}],
                    "3000/udp": [{"HostPort": "3000"}],
                }
            }
        }
        ports = parser._extract_ports(attrs)  # noqa: SLF001
        assert len(ports) == 3
        assert ports[0]["container"] == "80/tcp"
        assert ports[0]["host"] == "8080"
        assert ports[0]["protocol"] == "tcp"

    def test_extract_volumes(self):
        parser = DockerComposeParser()
        attrs = {
            "Mounts": [
                {"Type": "bind", "Source": "/host/data", "Destination": "/container/data"},
                {"Type": "volume", "Name": "my-volume", "Destination": "/container/vol"},
                {"Type": "tmpfs", "Destination": "/tmp"},
            ]
        }
        volumes = parser._extract_volumes(attrs)  # noqa: SLF001
        assert len(volumes) == 2
        assert "/host/data:/container/data" in volumes
        assert "my-volume:/container/vol" in volumes

    def test_parse_with_project_name(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\nservices:\n  web:\n    image: nginx\n")
        result = parser.parse(str(compose_file), project_name="my-project")
        assert len(result.configs) == 1

    def test_parse_with_include_volumes_networks(self, tmp_path):
        parser = DockerComposeParser()
        compose_file = tmp_path / "docker-compose.yml"
        compose_content = """version: '3.8'
services:
  web:
    image: nginx
volumes:
  data:
networks:
  frontend:
"""
        compose_file.write_text(compose_content)
        result = parser.parse(str(compose_file), include_volumes=True, include_networks=True)
        assert len(result.configs) == 1
        assert "volumes" in result.configs[0].content
        assert "networks" in result.configs[0].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
