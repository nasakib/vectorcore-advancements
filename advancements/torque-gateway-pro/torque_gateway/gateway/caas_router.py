"""
FastAPI Router for VectorCore CaaS and Sovereign Banking Endpoints.

Exposes REST APIs for:
- Consumer stored-value float management and deposits
- Continuous Double Auction order book inspection and order placement
- Silicon-Backed Hardware Loan origination and repayment monitoring
- Streaming compute session lifecycle and instant settlement
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from loom.caas.bank_vault import VectorCoreBankVault, BankAccount, SiliconHardwareLoan
from loom.caas.p2p_auction import P2PComputeAuction, BidOrder, AskOrder, AuctionMatchResult

router = APIRouter(prefix="/v1/caas", tags=["VectorCore CaaS & Sovereign Bank"])

# Global singleton bank and auction instances for the cluster
bank_vault = VectorCoreBankVault()
auction_engine = P2PComputeAuction()


class DepositRequest(BaseModel):
    account_id: str
    amount_usd: float = Field(..., gt=0.0)


class CreateAccountRequest(BaseModel):
    owner_id: str
    account_type: str = Field("consumer", description="'consumer', 'provider_host'")


class OriginateLoanRequest(BaseModel):
    borrower_account_id: str
    hardware_description: str
    principal_amount_usd: float = Field(..., gt=0.0)
    repayment_split_pct: float = Field(0.50, ge=0.10, le=0.90)


@router.get("/vault/summary")
def get_vault_summary() -> Dict[str, Any]:
    """Returns bank float, treasury accumulation, and lending portfolio."""
    return bank_vault.calculate_treasury_metrics()


@router.post("/vault/accounts")
def create_or_get_account(req: CreateAccountRequest) -> Dict[str, Any]:
    """Retrieves or opens a sovereign account in the VectorCore ledger."""
    acc = bank_vault.get_or_create_account(req.owner_id, req.account_type)
    return acc.dict()


@router.post("/vault/deposit")
def deposit_funds(req: DepositRequest) -> Dict[str, Any]:
    """Preloads fiat funds into an account balance (Stored-Value Float)."""
    try:
        acc = bank_vault.deposit_fiat(req.account_id, req.amount_usd)
        return {"status": "ok", "account": acc.dict()}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/auction/depth")
def get_auction_depth() -> Dict[str, Any]:
    """Inspects the continuous double auction order book depth and spread."""
    return auction_engine.get_order_book_depth()


@router.post("/auction/bid")
def place_bid(bid: BidOrder) -> Dict[str, Any]:
    """Submits a consumer bid for spot compute."""
    registered_bid, match = auction_engine.submit_bid(bid)
    return {
        "status": "matched" if match else "open",
        "bid": registered_bid.dict(),
        "match": match.dict() if match else None,
    }


@router.post("/auction/ask")
def place_ask(ask: AskOrder) -> Dict[str, Any]:
    """Submits a provider ask offering compute capacity."""
    registered_ask, match = auction_engine.submit_ask(ask)
    return {
        "status": "matched" if match else "open",
        "ask": registered_ask.dict(),
        "match": match.dict() if match else None,
    }


@router.post("/loans/originate")
def originate_loan(req: OriginateLoanRequest) -> Dict[str, Any]:
    """Originates a silicon-backed hardware loan repaid via compute splits."""
    try:
        loan = bank_vault.originate_silicon_hardware_loan(
            borrower_account_id=req.borrower_account_id,
            hardware_description=req.hardware_description,
            principal_amount_usd=req.principal_amount_usd,
        )
        return {"status": "originated", "loan": loan.dict()}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Mount Fault-Tolerant Compute Block Ledger Endpoints
from loom.caas.block_ledger import compute_ledger

class ClaimChunkRequest(BaseModel):
    worker_node_id: str

class MintBlockRequest(BaseModel):
    chunk_id: str
    worker_node_id: str
    worker_account_id: str
    units_computed: int = 128
    execution_time_sec: float = 0.45
    result_payload_hash: str = "sha256:verified_output"
    reward_usd: float = 0.005

class RegisterJobChunksRequest(BaseModel):
    parent_job_id: str
    workload_type: str = "token_stream"
    chunks_data: List[Dict[str, Any]]
    lease_duration_sec: float = 15.0


@router.get("/ledger/summary")
def get_ledger_summary() -> Dict[str, Any]:
    """Returns block height, minted blocks, rewards distributed, and offline recovery counts."""
    return compute_ledger.get_ledger_summary()


@router.post("/ledger/chunks/register")
def register_job_chunks(req: RegisterJobChunksRequest) -> Dict[str, Any]:
    """Registers micro-chunks for an incoming job with fault-tolerant lease timeouts."""
    chunks = compute_ledger.register_job_chunks(
        parent_job_id=req.parent_job_id,
        workload_type=req.workload_type,
        chunks_data=req.chunks_data,
        lease_duration_sec=req.lease_duration_sec,
    )
    return {"status": "registered", "chunks_count": len(chunks), "chunks": [c.dict() for c in chunks]}


@router.post("/ledger/chunks/claim")
def claim_chunk_lease(req: ClaimChunkRequest) -> Dict[str, Any]:
    """Worker node claims next available chunk lease (auto-sweeps offline nodes)."""
    chunk = compute_ledger.claim_next_chunk_lease(worker_node_id=req.worker_node_id)
    return {
        "status": "leased" if chunk else "no_chunks_available",
        "chunk": chunk.dict() if chunk else None,
    }


@router.post("/ledger/chunks/mint")
def mint_compute_block(req: MintBlockRequest) -> Dict[str, Any]:
    """Worker submits verifiable proof of useful work, mints a block, and receives instant USD reward."""
    try:
        block = compute_ledger.mint_verified_block(
            chunk_id=req.chunk_id,
            worker_node_id=req.worker_node_id,
            worker_account_id=req.worker_account_id,
            units_computed=req.units_computed,
            execution_time_sec=req.execution_time_sec,
            result_payload_hash=req.result_payload_hash,
            reward_usd=req.reward_usd,
        )
        return {"status": "minted", "block": block.dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Cloud Gaming Streaming Routes (Low-Latency P2P Sunshine/Moonlight & WebRTC)
# ============================================================================

from loom.caas.gaming.streaming_bridge import (
    gaming_streaming_bridge,
    GamingSessionConfig,
    ActiveGamingSession,
)


class GamingHeartbeatRequest(BaseModel):
    session_id: str
    frames_increment: int = 60
    dropped_increment: int = 0
    encode_latency_ms: float = 1.6
    network_rtt_ms: float = 1.1


@router.get("/gaming/hardware/probe")
def probe_gaming_hardware() -> Dict[str, Any]:
    """Inspects host machine for hardware encoders (NVENC, AMF, VideoToolbox)."""
    profile = gaming_streaming_bridge.hardware_profile
    return {
        "status": "ready",
        "hardware_profile": profile.dict(),
    }


@router.post("/gaming/sessions/initiate")
def initiate_gaming_session(cfg: GamingSessionConfig) -> Dict[str, Any]:
    """Initiates an ultra-low latency P2P cloud gaming stream and starts metering."""
    session = gaming_streaming_bridge.initiate_gaming_session(cfg)
    return {
        "status": "initiated",
        "session": session.dict(),
    }


@router.post("/gaming/sessions/heartbeat")
def record_gaming_heartbeat(req: GamingHeartbeatRequest) -> Dict[str, Any]:
    """Records streaming frame metrics and updates real-time accrued USD cost."""
    try:
        updated_metrics = gaming_streaming_bridge.process_heartbeat(
            session_id=req.session_id,
            frames_increment=req.frames_increment,
            dropped_increment=req.dropped_increment,
            encode_latency_ms=req.encode_latency_ms,
            network_rtt_ms=req.network_rtt_ms,
        )
        return {"status": "ok", "metrics": updated_metrics.to_dict()}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gaming/sessions/terminate")
def terminate_gaming_session(session_id: str) -> Dict[str, Any]:
    """Finalizes cloud gaming session, returns summary, and routes 99% payout to host."""
    try:
        result = gaming_streaming_bridge.terminate_gaming_session(session_id)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/gaming/sessions/{session_id}")
def get_gaming_session(session_id: str) -> Dict[str, Any]:
    """Fetches real-time status and telemetry for an active gaming stream."""
    session = gaming_streaming_bridge.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return {"status": "active", "session": session.dict()}


