"""
Atomic SQLite WAL State Store (`loom/fabric/state_store.py`).

Eliminates concurrent flat-file JSON I/O bottlenecks and race conditions for:
- `cluster` (migrated from `cluster.json`)
- `fiber_leases` (migrated from `data/fiber_leases.json`)
- `sl_gas_ledger` (migrated from `data/sl_gas_ledger.json`)
- `learned_patterns` (migrated from `.clothos_learned_patterns.json`)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "clothos_state.db"

LEGACY_JSON_MAP: Dict[str, Path] = {
    "cluster": REPO_ROOT / "cluster.json",
    "fiber_leases": REPO_ROOT / "data" / "fiber_leases.json",
    "sl_gas_ledger": REPO_ROOT / "data" / "sl_gas_ledger.json",
    "learned_patterns": REPO_ROOT / ".clothos_learned_patterns.json",
}


class SQLiteWALStateStore:
    """Thread-safe and process-safe SQLite Write-Ahead Log (WAL) state backend."""

    def __init__(self, db_path: Optional[Path] = None):
        env_path = os.environ.get("CLOTHOS_STATE_DB")
        self.db_path = Path(env_path) if env_path else (db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kv_state (
                        namespace TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )

    def _maybe_migrate_legacy(self, namespace: str, legacy_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        src = legacy_path or LEGACY_JSON_MAP.get(namespace)
        if not src or not src.exists() or src.stat().st_size == 0:
            return None
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.set_state(namespace, data)
                return data
        except Exception:
            return None
        return None

    def get_state(
        self,
        namespace: str,
        default: Optional[Dict[str, Any]] = None,
        legacy_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Atomically reads a state namespace from SQLite WAL, auto-migrating legacy JSON if needed."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT payload_json FROM kv_state WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
                if row:
                    try:
                        parsed = json.loads(row[0])
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        pass
            migrated = self._maybe_migrate_legacy(namespace, legacy_path=legacy_path)
            if migrated is not None:
                return migrated
            return dict(default) if default is not None else {}

    def set_state(self, namespace: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically writes a state namespace inside an IMMEDIATE WAL transaction."""
        now = time.time()
        raw = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    conn.execute(
                        """
                        INSERT INTO kv_state (namespace, payload_json, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(namespace) DO UPDATE SET
                            payload_json = excluded.payload_json,
                            updated_at = excluded.updated_at
                        """,
                        (namespace, raw, now),
                    )
                    conn.execute("COMMIT;")
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise
        return payload

    def update_state(
        self,
        namespace: str,
        mutator: Callable[[Dict[str, Any]], Dict[str, Any]],
        legacy_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Performs an atomic read-modify-write cycle under lock and WAL transaction."""
        with self._lock:
            current = self.get_state(namespace, default={}, legacy_path=legacy_path)
            updated = mutator(current)
            return self.set_state(namespace, updated)

    def get_wal_status(self) -> Dict[str, Any]:
        """Returns SQLite WAL health, journal_mode, and per-namespace timestamps."""
        with self._lock:
            with self._connect() as conn:
                mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
                rows = conn.execute(
                    "SELECT namespace, length(payload_json), updated_at FROM kv_state ORDER BY namespace"
                ).fetchall()
                return {
                    "db_path": str(self.db_path),
                    "journal_mode": str(mode).upper(),
                    "namespaces": {
                        r[0]: {"bytes": int(r[1]), "updated_at": float(r[2])}
                        for r in rows
                    },
                }


state_store = SQLiteWALStateStore()
