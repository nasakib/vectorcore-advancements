"""Phase 2 verification: Atomic SQLite WAL state store & concurrency hardening."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient


def test_sqlite_wal_concurrent_updates(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test_state.db"
    monkeypatch.setenv("CLOTHOS_STATE_DB", str(db_file))

    from loom.fabric.state_store import SQLiteWALStateStore

    store = SQLiteWALStateStore(db_path=db_file)
    status = store.get_wal_status()
    assert status["journal_mode"] == "WAL"

    store.set_state("counter", {"count": 0})

    def _inc(_i: int):
        store.update_state("counter", lambda d: {"count": d.get("count", 0) + 1})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_inc, range(40)))

    assert store.get_state("counter")["count"] == 40


def test_gas_ledger_and_fiber_lease_persist_to_sqlite_wal(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "csp_state.db"
    monkeypatch.setenv("CLOTHOS_STATE_DB", str(db_file))

    import loom.fabric.state_store as ss_mod
    ss_mod.state_store = ss_mod.SQLiteWALStateStore(db_path=db_file)

    from loom.csp.gas_meter import SpotlightLocalGasLedger
    from loom.csp.fiber_lease import FiberLeaseManager, FiberLeaseType

    ledger = SpotlightLocalGasLedger(persistence_file=str(tmp_path / "sl_gas_ledger.json"))
    ledger.deposit_fiat_usd("acct_test", 10.0)
    ledger_reloaded = SpotlightLocalGasLedger(persistence_file=str(tmp_path / "sl_gas_ledger.json"))
    assert ledger_reloaded.wallets["acct_test"].balance_gas == ledger.wallets["acct_test"].balance_gas

    mgr = FiberLeaseManager(persistence_file=str(tmp_path / "fiber_leases.json"))
    carrier = next(iter(mgr.known_carriers.values()))
    lease = mgr.provision_lease(carrier.carrier_id, carrier.supported_lease_types[0], "node1", "node2")
    mgr_reloaded = FiberLeaseManager(persistence_file=str(tmp_path / "fiber_leases.json"))
    assert lease.circuit_id in mgr_reloaded.active_circuits


def test_fastapi_state_endpoints():
    from loom.fabric.dashboard_server import app

    client = TestClient(app)
    r_wal = client.get("/api/state/wal_status")
    assert r_wal.status_code == 200
    assert r_wal.json()["journal_mode"] == "WAL"

    for ns in ("cluster", "fiber_leases", "sl_gas_ledger", "learned_patterns"):
        r = client.get(f"/api/state/{ns}")
        assert r.status_code == 200
        assert r.json()["namespace"] == ns
