"""Parser for Docker Compose files."""

from pathlib import Path

import docker
import yaml

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.parsers.base import ConfigParser, ParseResult


class DockerComposeParser(ConfigParser):
    """Parser for Docker Compose configurations."""

    @property
    def source_type(self) -> ConfigSource:
        return ConfigSource.DOCKER_COMPOSE

    @property
    def supported_formats(self) -> list[ConfigFormat]:
        return [ConfigFormat.YAML]

    def __init__(self, docker_host: str | None = None):
        self.docker_host = docker_host
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self.docker_host:
                self._client = docker.DockerClient(base_url=self.docker_host)
            else:
                self._client = docker.from_env()
        return self._client

    def parse(self, source: str | Path, **kwargs) -> ParseResult:
        """Parse Docker Compose file or running containers.

        Args:
            source: Path to docker-compose.yml file, or "running" for live containers
            **kwargs:
                project_name: Docker Compose project name
                include_volumes: Include volume configs
                include_networks: Include network configs
        """
        configs = []
        errors = []

        try:
            if str(source) == "running":
                return self._parse_running_containers(**kwargs)

            path = Path(source)
            if path.is_file():
                config = self._parse_compose_file(path)
                if config:
                    configs.append(config)
                else:
                    errors.append(f"Failed to parse {path}")
            elif path.is_dir():
                for compose_file in path.rglob("docker-compose*.yml"):
                    config = self._parse_compose_file(compose_file)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse {compose_file}")
                for compose_file in path.rglob("docker-compose*.yaml"):
                    config = self._parse_compose_file(compose_file)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse {compose_file}")
            else:
                errors.append(f"Path does not exist: {path}")

        except Exception as e:
            errors.append(f"Docker Compose parse error: {e}")

        return ParseResult(configs=configs, errors=errors)

    def _parse_compose_file(self, file_path: Path) -> ParsedConfig | None:
        """Parse a docker-compose.yml file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            content = yaml.safe_load(raw_content)

            if not isinstance(content, dict):
                return None

            # Normalize the compose structure
            normalized = self._normalize_compose(content)

            return self._create_parsed_config(
                content=normalized,
                file_path=file_path,
                resource_id=f"compose/{file_path.stem}",
                raw_content=raw_content,
            )
        except Exception:
            return None

    def _parse_running_containers(self, **kwargs) -> ParseResult:
        """Parse running Docker containers as if they were compose configs."""
        configs = []
        errors = []

        try:
            client = self._get_client()
            containers = client.containers.list(all=True)

            for container in containers:
                try:
                    # Reconstruct compose-like config from container
                    config = self._container_to_compose(container)
                    if config:
                        configs.append(config)
                except Exception as e:
                    errors.append(f"Error parsing container {container.name}: {e}")

        except Exception as e:
            errors.append(f"Docker client error: {e}")

        return ParseResult(configs=configs, errors=errors)

    def _container_to_compose(self, container) -> ParsedConfig | None:
        """Convert a running container to a compose-like config."""
        try:
            attrs = container.attrs
            config_data = {
                "version": "3.8",
                "services": {
                    container.name: {
                        "image": attrs["Config"]["Image"],
                        "command": attrs["Config"]["Cmd"],
                        "environment": attrs["Config"]["Env"],
                        "ports": self._extract_ports(attrs),
                        "volumes": self._extract_volumes(attrs),
                        "networks": list(attrs["NetworkSettings"]["Networks"].keys()),
                        "restart": attrs["HostConfig"]["RestartPolicy"]["Name"],
                        "labels": attrs["Config"]["Labels"],
                    }
                },
            }

            raw_yaml = yaml.dump(config_data, sort_keys=False)

            return self._create_parsed_config(
                content=config_data,
                resource_id=f"container/{container.name}",
                labels=attrs["Config"]["Labels"] or {},
                raw_content=raw_yaml,
            )
        except Exception:
            return None

    def _normalize_compose(self, content: dict) -> dict:
        """Normalize compose content for comparison."""
        normalized = {"version": content.get("version", "3.8")}
        if "services" in content:
            normalized["services"] = {}
            for name, svc in content["services"].items():
                normalized["services"][name] = self._normalize_service(svc)
        for key in ["volumes", "networks", "configs", "secrets"]:
            if key in content:
                normalized[key] = content[key]
        return normalized

    def _normalize_service(self, service: dict) -> dict:
        """Normalize a service definition."""
        # Remove runtime-only fields
        runtime_fields = ["container_name", "build", "deploy", "extends"]
        return {k: v for k, v in service.items() if k not in runtime_fields}

    def _extract_ports(self, attrs: dict) -> list[dict]:
        """Extract port mappings from container attributes."""
        ports = []
        port_bindings = attrs["HostConfig"].get("PortBindings", {})
        for container_port, bindings in port_bindings.items():
            if bindings:
                for binding in bindings:
                    ports.append(
                        {
                            "container": container_port,
                            "host": binding.get("HostPort"),
                            "protocol": container_port.split("/")[-1]
                            if "/" in container_port
                            else "tcp",
                        }
                    )
        return ports

    def _extract_volumes(self, attrs: dict) -> list[str]:
        """Extract volume mounts from container attributes."""
        volumes = []
        for mount in attrs["Mounts"]:
            if mount["Type"] == "bind":
                volumes.append(f"{mount['Source']}:{mount['Destination']}")
            elif mount["Type"] == "volume":
                volumes.append(f"{mount['Name']}:{mount['Destination']}")
        return volumes
