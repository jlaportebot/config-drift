"""DuckDB storage for baselines and scan history."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

from config_drift.models.config import ParsedConfig
from config_drift.models.scan import ScanConfig, ScanResult


class DuckDBStore:
    """DuckDB-backed storage for config-drift."""

    def __init__(self, db_path: str | Path = "config_drift.db"):
        self.db_path = Path(db_path)
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                id VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,
                resource_id VARCHAR NOT NULL,
                namespace VARCHAR,
                content JSON NOT NULL,
                labels JSON,
                annotations JSON,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_baselines_source_resource
            ON baselines(source, resource_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                scan_id VARCHAR PRIMARY KEY,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                config JSON,
                summary JSON,
                error VARCHAR,
                scanned_sources JSON
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scan_history_started
            ON scan_history(started_at)
        """)

    def save_baseline(self, config: ParsedConfig) -> str:
        """Save or update a baseline configuration."""
        conn = self._get_conn()
        baseline_id = f"{config.source.value}/{config.resource_id}"
        if config.namespace:
            baseline_id = f"{baseline_id}/{config.namespace}"

        now = datetime.utcnow()
        conn.execute(
            """
            INSERT INTO baselines (id, source, resource_id, namespace, content, labels, annotations, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                content = excluded.content,
                labels = excluded.labels,
                annotations = excluded.annotations,
                updated_at = excluded.updated_at
        """,
            [
                baseline_id,
                config.source.value,
                config.resource_id,
                config.namespace,
                json.dumps(config.content),
                json.dumps(config.labels),
                json.dumps(config.annotations),
                now,
                now,
            ],
        )
        return baseline_id

    def get_baseline(
        self, source: str, resource_id: str, namespace: str | None = None
    ) -> Optional[ParsedConfig]:
        """Retrieve a baseline configuration."""
        conn = self._get_conn()
        baseline_id = f"{source}/{resource_id}"
        if namespace:
            baseline_id = f"{baseline_id}/{namespace}"

        result = conn.execute(
            """
            SELECT id, source, resource_id, namespace, content, labels, annotations, created_at, updated_at
            FROM baselines WHERE id = ?
        """,
            [baseline_id],
        ).fetchone()

        if not result:
            return None

        return ParsedConfig(
            source=result[1],
            format="yaml",  # Default, not stored
            content=json.loads(result[4]),
            resource_id=result[2],
            namespace=result[3],
            labels=json.loads(result[5]) if result[5] else {},
            annotations=json.loads(result[6]) if result[6] else {},
        )

    def list_baselines(self, source: str | None = None) -> list[dict]:
        """List all baselines, optionally filtered by source."""
        conn = self._get_conn()
        if source:
            results = conn.execute(
                """
                SELECT id, source, resource_id, namespace, created_at, updated_at
                FROM baselines WHERE source = ? ORDER BY updated_at DESC
            """,
                [source],
            ).fetchall()
        else:
            results = conn.execute("""
                SELECT id, source, resource_id, namespace, created_at, updated_at
                FROM baselines ORDER BY updated_at DESC
            """).fetchall()

        return [
            {
                "id": r[0],
                "source": r[1],
                "resource_id": r[2],
                "namespace": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in results
        ]

    def delete_baseline(self, source: str, resource_id: str, namespace: str | None = None) -> bool:
        """Delete a baseline."""
        conn = self._get_conn()
        baseline_id = f"{source}/{resource_id}"
        if namespace:
            baseline_id = f"{baseline_id}/{namespace}"

        result = conn.execute("DELETE FROM baselines WHERE id = ?", [baseline_id])
        # DuckDB returns -1 for ROWCOUNT on DELETE; check by re-querying
        if result.rowcount == -1:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM baselines WHERE id = ?", [baseline_id]
            ).fetchone()[0]
            return remaining == 0
        return result.rowcount > 0

    def save_scan(self, scan: ScanResult) -> str:
        """Save a scan result."""
        conn = self._get_conn()
        if not scan.scan_id:
            scan.scan_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO scan_history (scan_id, started_at, completed_at, config, summary, error, scanned_sources)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [
                scan.scan_id,
                scan.started_at,
                scan.completed_at,
                json.dumps(scan.config.__dict__) if scan.config else None,
                json.dumps(scan.summary.to_dict()) if scan.summary else None,
                scan.error,
                json.dumps(scan.scanned_sources),
            ],
        )
        return scan.scan_id

    def get_scan(self, scan_id: str) -> Optional[ScanResult]:
        """Retrieve a scan result."""
        conn = self._get_conn()
        result = conn.execute(
            """
            SELECT scan_id, started_at, completed_at, config, summary, error, scanned_sources
            FROM scan_history WHERE scan_id = ?
        """,
            [scan_id],
        ).fetchone()

        if not result:
            return None

        scan = ScanResult(
            scan_id=result[0],
            started_at=result[1],
            completed_at=result[2],
            error=result[5],
            scanned_sources=json.loads(result[6]) if result[6] else [],
        )
        if result[3]:
            scan.config = ScanConfig(**json.loads(result[3]))
        if result[4]:
            summary_data = json.loads(result[4])
            # Reconstruct DriftSummary (simplified)
            from config_drift.models.drift import DriftSummary

            scan.summary = DriftSummary(**summary_data)
        return scan

    def list_scans(self, limit: int = 50) -> list[dict]:
        """List recent scans."""
        conn = self._get_conn()
        results = conn.execute(
            """
            SELECT scan_id, started_at, completed_at, error, scanned_sources
            FROM scan_history ORDER BY started_at DESC LIMIT ?
        """,
            [limit],
        ).fetchall()

        return [
            {
                "scan_id": r[0],
                "started_at": r[1],
                "completed_at": r[2],
                "error": r[3],
                "scanned_sources": json.loads(r[4]) if r[4] else [],
            }
            for r in results
        ]

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
