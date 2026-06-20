# 🔍 config-drift

Configuration drift detector for **Kubernetes**, **Docker Compose**, **Terraform**, and **Helm** — compare environments and detect unauthorized changes.

## Features

- **Multi-source support**: Kubernetes, Docker Compose, Terraform, Helm, and local files
- **Structural drift detection**: Compare configuration structure (added/removed/modified keys)
- **Semantic drift detection**: Understand the *meaning* of changes (critical vs. cosmetic)
- **Baseline management**: Save, compare, and track configuration baselines
- **DuckDB storage**: Fast analytics-grade storage for scan history
- **Rich CLI**: Beautiful terminal output with tables, colors, and panels
- **Multiple output formats**: Table, JSON, YAML, Markdown, HTML

## Installation

```bash
pip install config-drift
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add config-drift
```

## Quick Start

```bash
# Save a baseline
config-drift baseline save --source file --path ./k8s/

# Scan for drift
config-drift scan --source file --path ./k8s/ --baseline ./baselines/

# Compare two directories
config-drift compare --baseline ./k8s-staging/ --current ./k8s-production/

# Generate a report
config-drift report --last --format markdown
```

## Usage

### Scan

```bash
# Scan Kubernetes cluster
config-drift scan --source kubernetes --namespace default

# Scan Docker Compose file
config-drift scan --source docker_compose --path docker-compose.yml

# Scan Terraform directory
config-drift scan --source terraform --path ./terraform/

# Scan Helm releases
config-drift scan --source helm --path releases

# Scan with severity filter
config-drift scan --source file --path ./k8s/ --severity high

# Output as JSON
config-drift scan --source file --path ./k8s/ --format json --output scan.json
```

### Compare

```bash
# Compare two configuration sets
config-drift compare --baseline ./baselines/ --current ./k8s/

# Use specific detector
config-drift compare -b old-compose.yml -c new-compose.yml --detector semantic
```

### Baselines

```bash
# Save baseline
config-drift baseline save --source file --path ./k8s/

# List baselines
config-drift baseline list

# Show a baseline
config-drift baseline show file/config/my-app

# Delete a baseline
config-drift baseline delete file/config/my-app
```

### Reports

```bash
# Report on latest scan
config-drift report --last

# Generate HTML report
config-drift report --db scans.db --last --format html --output report.html

# Generate Markdown report
config-drift report --last --format markdown --output report.md
```

## Drift Severity Levels

| Level | Description | Example |
|-------|-------------|---------|
| **Critical** | Security/reliability impact | Changed replicas, image tags, security contexts |
| **High** | Significant configuration change | Removed services, changed ports, modified environments |
| **Medium** | Moderate impact | Changed annotations, labels, strategies |
| **Low** | Minor/cosmetic change | Added documentation, changed timestamps |

## Python API

```python
from config_drift import BasicDriftDetector, ParsedConfig, ConfigSource, ConfigFormat

# Create configs
baseline = ParsedConfig(
    source=ConfigSource.KUBERNETES,
    format=ConfigFormat.YAML,
    content={"spec": {"replicas": 3, "image": "v1"}},
    resource_id="Deployment/my-app",
)

current = ParsedConfig(
    source=ConfigSource.KUBERNETES,
    format=ConfigFormat.YAML,
    content={"spec": {"replicas": 5, "image": "v2"}},
    resource_id="Deployment/my-app",
)

# Detect drift
detector = BasicDriftDetector()
drifts = detector.detect(baseline, current)

for drift in drifts:
    print(f"{drift.path}: {drift.drift_type.value} (severity: {drift.severity.value})")
    print(f"  Expected: {drift.expected}")
    print(f"  Actual: {drift.actual}")
```

## Development

```bash
# Install dev dependencies
uv sync --all-groups

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format --check .

# Type check
uv run ty check config_drift/
```

## License

MIT
