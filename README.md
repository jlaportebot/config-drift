# Config Drift

> Configuration drift detector for Kubernetes, Docker Compose, Terraform, and Helm — compare environments and detect unauthorized changes.

## Features

- **Multi-format support**: Kubernetes YAML, Helm values, Docker Compose, Terraform, JSON, and generic YAML
- **Smart severity classification**: Automatic severity assignment based on field type (image changes = critical, annotations = info)
- **Multiple output formats**: Console (rich), JSON, SARIF, Summary
- **CI/CD integration**: Exit codes for breaking changes, fail-on thresholds
- **Extensible**: Custom severity rules for organization-specific policies

## Installation

```bash
pip install config-drift
# or
uv pip install config-drift
```

## Quick Start

```bash
# Compare two environment directories
config-drift compare ./environments/prod ./environments/staging

# Output as JSON for automation
config-drift compare ./prod ./staging --format json

# Fail CI if critical or error drifts found
config-drift compare ./prod ./staging --fail-on error

# Scan a directory to see discovered resources
config-drift scan ./environments/prod
```

## Commands

### `compare`

Compare two environment directories for configuration drift.

```bash
config-drift compare SOURCE_DIR TARGET_DIR [OPTIONS]
```

Options:
- `--source-name`, `--target-name`: Names for environments (default: "source", "target")
- `--format`: Output format - `console`, `json`, `summary`, `sarif` (default: `console`)
- `--severity`: Minimum severity to report - `info`, `warning`, `error`, `critical` (default: `info`)
- `--exclude`: Glob patterns to exclude (can be used multiple times)
- `--include`: Glob patterns to include (can be used multiple times)
- `--fail-on`: Exit with error code if drifts of this severity or higher found - `warning`, `error`, `critical`

### `scan`

Scan a directory and list all discovered configuration resources.

```bash
config-drift scan DIRECTORY [OPTIONS]
```

Options:
- `--name`: Environment name (default: "environment")
- `--format`: Output format - `console`, `json` (default: `console`)
- `--exclude`: Glob patterns to exclude
- `--include`: Glob patterns to include

## Severity Levels

| Severity | Description | Examples |
|----------|-------------|----------|
| **CRITICAL** | Breaking changes that affect runtime behavior | Container image, command changes |
| **ERROR** | Significant configuration changes | Replica count, env vars, resource limits |
| **WARNING** | Notable changes that may affect behavior | Ports, volumes, affinity, tolerations |
| **INFO** | Cosmetic or metadata changes | Annotations, labels |

## Custom Severity Rules

Create a custom rules file for organization-specific policies:

```python
from config_drift.detector import DriftDetector, DriftRule
from config_drift.models import DriftSeverity

rules = [
    DriftRule("spec.customField", DriftSeverity.CRITICAL, description="Custom critical field"),
    DriftRule("metadata.labels.owner", DriftSeverity.ERROR, description="Owner label changed"),
]

detector = DriftDetector(severity_rules=rules)
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Check for config drift
  run: |
    config-drift compare ./prod ./staging --fail-on error --format summary
```

### Exit Codes

- `0`: No drifts or only info/warning (below fail-on threshold)
- `1`: Fail-on threshold exceeded
- `2`: Breaking changes detected (critical/error drifts)

## Supported Formats

| Format | Extensions | Detection |
|--------|------------|-----------|
| Kubernetes | `.yaml`, `.yml` | `apiVersion` + `kind` |
| Helm Values | `values*.yaml` | Filename pattern |
| Docker Compose | `docker-compose*.yaml` | Filename pattern |
| Terraform | `.tf`, `.tfvars`, `.hcl` | Extension |
| JSON | `.json` | Extension |
| Generic YAML | `.yaml`, `.yml` | Fallback |

## Development

```bash
# Install dependencies
uv sync --all-groups

# Run tests
uv run pytest -v

# Lint
uv run ruff check .
uv run ruff format --check .

# Type check
uv run ty check config_drift/
```

## License

MIT License - see [LICENSE](LICENSE) for details.