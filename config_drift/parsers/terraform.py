"""Parser for Terraform configurations."""

import json
from pathlib import Path

import hcl2
from python_terraform import Terraform

from config_drift.models.config import ConfigFormat, ConfigSource, ParsedConfig
from config_drift.parsers.base import ConfigParser, ParseResult


class TerraformParser(ConfigParser):
    """Parser for Terraform configurations and state."""

    @property
    def source_type(self) -> ConfigSource:
        return ConfigSource.TERRAFORM

    @property
    def supported_formats(self) -> list[ConfigFormat]:
        return [ConfigFormat.HCL, ConfigFormat.JSON]

    def __init__(self, working_dir: str | None = None):
        self.working_dir = working_dir
        self._tf = None

    def _get_terraform(self, dir_path: Path) -> Terraform:
        if self._tf is None or self._tf.working_dir != str(dir_path):
            self._tf = Terraform(working_dir=str(dir_path))
        return self._tf

    def parse(self, source: str | Path, **kwargs) -> ParseResult:
        """Parse Terraform configuration or state.

        Args:
            source: Path to Terraform directory or state file
            **kwargs:
                include_state: Parse terraform.tfstate as well
                include_plan: Run terraform plan and parse output
                variables: Dict of variables to pass to terraform
        """
        configs = []
        errors = []

        path = Path(source)
        try:
            if path.is_file() and path.name.endswith(".tfstate"):
                config = self._parse_state_file(path)
                if config:
                    configs.append(config)
                else:
                    errors.append(f"Failed to parse state file {path}")
            elif path.is_file() and path.suffix in [".tf", ".tf.json"]:
                config = self._parse_tf_file(path)
                if config:
                    configs.append(config)
                else:
                    errors.append(f"Failed to parse {path}")
            elif path.is_dir():
                # Parse all .tf files in directory
                for tf_file in path.rglob("*.tf"):
                    config = self._parse_tf_file(tf_file)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse {tf_file}")
                for tf_file in path.rglob("*.tf.json"):
                    config = self._parse_tf_json_file(tf_file)
                    if config:
                        configs.append(config)
                    else:
                        errors.append(f"Failed to parse {tf_file}")

                # Parse state if requested
                if kwargs.get("include_state"):
                    state_file = path / "terraform.tfstate"
                    if state_file.exists():
                        config = self._parse_state_file(state_file)
                        if config:
                            configs.append(config)

                # Run plan if requested
                if kwargs.get("include_plan"):
                    plan_config = self._parse_plan(path, kwargs.get("variables", {}))
                    if plan_config:
                        configs.append(plan_config)
            else:
                errors.append(f"Path does not exist: {path}")

        except Exception as e:
            errors.append(f"Terraform parse error: {e}")

        return ParseResult(configs=configs, errors=errors)

    def _parse_tf_file(self, file_path: Path) -> ParsedConfig | None:
        """Parse a .tf (HCL) file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            parsed = hcl2.loads(raw_content)

            if not parsed:
                return None

            # Normalize HCL structure
            normalized = self._normalize_hcl(parsed)

            return self._create_parsed_config(
                content=normalized,
                file_path=file_path,
                resource_id=f"terraform/{file_path.stem}",
                raw_content=raw_content,
                format=ConfigFormat.HCL,
            )
        except Exception:
            return None

    def _parse_tf_json_file(self, file_path: Path) -> ParsedConfig | None:
        """Parse a .tf.json file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            content = json.loads(raw_content)

            if not isinstance(content, dict):
                return None

            return self._create_parsed_config(
                content=content,
                file_path=file_path,
                resource_id=f"terraform/{file_path.stem}",
                raw_content=raw_content,
                format=ConfigFormat.JSON,
            )
        except Exception:
            return None

    def _parse_state_file(self, file_path: Path) -> ParsedConfig | None:
        """Parse terraform.tfstate file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            content = json.loads(raw_content)

            if not isinstance(content, dict):
                return None

            # Normalize state structure
            normalized = self._normalize_state(content)

            return self._create_parsed_config(
                content=normalized,
                file_path=file_path,
                resource_id="terraform/state",
                raw_content=raw_content,
                format=ConfigFormat.JSON,
            )
        except Exception:
            return None

    def _parse_plan(self, dir_path: Path, variables: dict) -> ParsedConfig | None:
        """Run terraform plan and parse output."""
        try:
            tf = self._get_terraform(dir_path)
            # Initialize if needed
            tf.init(capture_output=True)

            # Run plan with variables
            var_args = []
            for k, v in variables.items():
                var_args.extend(["-var", f"{k}={v}"])

            return_code, stdout, stderr = tf.plan(
                no_color=True,
                detailed_exitcode=True,
                capture_output=True,
                *var_args,
            )

            # Parse plan output (simplified)
            plan_data = {
                "plan_output": stdout,
                "plan_stderr": stderr,
                "return_code": return_code,
                "variables": variables,
            }

            raw_content = f"Plan return code: {return_code}\n{stdout}\n{stderr}"

            return self._create_parsed_config(
                content=plan_data,
                file_path=dir_path,
                resource_id="terraform/plan",
                raw_content=raw_content,
                format=ConfigFormat.TEXT,
            )
        except Exception:
            return None

    def _normalize_hcl(self, parsed: list) -> dict:
        """Normalize HCL parsed structure."""
        result = {}
        for block in parsed:
            for block_type, block_content in block.items():
                if block_type not in result:
                    result[block_type] = {}
                if isinstance(block_content, list):
                    for item in block_content:
                        for name, config in item.items():
                            if name not in result[block_type]:
                                result[block_type][name] = {}
                            result[block_type][name].update(config)
                elif isinstance(block_content, dict):
                    result[block_type].update(block_content)
        return result

    def _normalize_state(self, state: dict) -> dict:
        """Normalize Terraform state for comparison."""
        # Remove sensitive/computed fields that change
        normalized = {
            "version": state.get("version"),
            "terraform_version": state.get("terraform_version"),
            "resources": [],
        }

        for resource in state.get("resources", []):
            normalized_resource = {
                "type": resource.get("type"),
                "name": resource.get("name"),
                "provider": resource.get("provider"),
                "instances": [],
            }
            for instance in resource.get("instances", []):
                normalized_instance = {
                    "index": instance.get("index"),
                    "attributes": self._filter_attributes(instance.get("attributes", {})),
                }
                normalized_resource["instances"].append(normalized_instance)
            normalized["resources"].append(normalized_resource)

        return normalized

    def _filter_attributes(self, attributes: dict) -> dict:
        """Filter out computed/sensitive attributes that change."""
        # Remove known computed fields
        computed_prefixes = [
            "id",
            "arn",
            "owner_id",
            "creation_timestamp",
            "default_version",
        ]
        return {
            k: v
            for k, v in attributes.items()
            if not any(k.startswith(prefix) for prefix in computed_prefixes)
        }
