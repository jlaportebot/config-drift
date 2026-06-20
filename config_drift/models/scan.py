"""Scan configuration and result models."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config_drift.models.config import ConfigSource
from config_drift.models.drift import DriftSummary


@dataclass
class ScanConfig:
    """Configuration for a drift scan."""

    sources: list[ConfigSource] = field(default_factory=list)
    paths: list[Path] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    label_selectors: dict[str, str] = field(default_factory=dict)
    exclude_patterns: list[str] = field(default_factory=list)
    severity_threshold: str = "low"
    output_format: str = "table"
    output_file: Optional[Path] = None
    baseline_file: Optional[Path] = None
    store_baseline: bool = False


@dataclass
class ScanResult:
    """Result of a drift scan."""

    scan_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    config: Optional[ScanConfig] = None
    summary: Optional[DriftSummary] = None
    error: Optional[str] = None
    scanned_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": self.config.__dict__ if self.config else None,
            "summary": self.summary.to_dict() if self.summary else None,
            "error": self.error,
            "scanned_sources": self.scanned_sources,
        }
