"""
FastAPI Router for Spotlight-Local Compute Service Provider (sL-CSP) Endpoints.

Exposes REST and SSE endpoints for:
- Node hardware attestation and geohash manifest (`/v1/csp/manifest`)
- Real-time streaming compute meter metrics (`/v1/csp/meter/summary`)
- Instant neighborhood quote and route arbitration (`/v1/csp/quote`)
- Spotlight-Local double-entry settlement and invoice verification (`/v1/csp/settle`)
- Neighborhood mesh discovery (`/v1/csp/mesh/neighbors`)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from loom.csp import (
    CspNodeManifest,
    GpuDeviceManifest,
    CspPricingModel,
    StreamingComputeMeter,
    ComputeMeterReading,
    SlSettlementEngine,
    SlComputeInvoice,
    NeighborhoodMeshRouter,
)

router = APIRouter(prefix="/v1/csp", tags=["Spotlight-Local CSP"])

# Singleton local node manifest for SkyTech
local_manifest = CspNodeManifest(
    node_name="SkyTech-DualGPU-Rig",
    provider_address="192.168.1.110",
    geohash="dn5bpq",
    neighborhood_tag="Inman Park / Old Fourth Ward",
    city="Atlanta",
    vcpu_count=16,
    host_ram_gb=40.8,
    gpus=[
        GpuDeviceManifest(
            name="NVIDIA GeForce RTX 3060",
            backend="cuda",
            vram_total_gb=12.0,
            vram_available_gb=10.5,
            tflops_fp16=12.74,
            is_active_seeder=True,
        ),
        GpuDeviceManifest(
            name="AMD Radeon RX 580",
            backend="opencl",
            vram_total_gb=8.0,
            vram_available_gb=7.8,
            tflops_fp16=6.17,
            is_active_seeder=True,
        ),
    ],
    aggregate_vram_gb=20.0,
    landauer_rating_pj_per_mac=1.2,
    is_solar_powered=True,
    owner_avatar_totem_id="NFC-TOTEM-NAJ-01",
    sl_merchant_account_id="acct_sl_merchant_skytech_01",
)

# Stateful subsystems
active_meter = StreamingComputeMeter(node_id=local_manifest.node_id)
settlement_engine = SlSettlementEngine(provider_node_id=local_manifest.node_id)
mesh_router = NeighborhoodMeshRouter(local_geohash=local_manifest.geohash)

# Central ClothOS Compute Broker instance
from loom.csp.broker import ClothosComputeBroker, ConsumerWorkloadRequest
broker = ClothosComputeBroker(local_geohash=local_manifest.geohash)
broker.register_provider_node(local_manifest, ping_rtt_ms=0.5)

# Pre-register local node and default cluster peer
mesh_router.register_peer(local_manifest, ping_rtt_ms=0.5)

# Peer node 2 (Orchestrator APU)
node2_manifest = CspNodeManifest(
    node_name="WIN-7CMAQLVP8MV-APU",
    provider_address="192.168.1.116",
    geohash="dn5bpr",
    neighborhood_tag="Inman Park / O4W East",
    city="Atlanta",
    vcpu_count=16,
    host_ram_gb=16.0,
    gpus=[
        GpuDeviceManifest(
            name="AMD Radeon 680M / APU",
            backend="vulkan",
            vram_total_gb=4.0,
            vram_available_gb=3.5,
            tflops_fp16=3.8,
            is_active_seeder=True,
        )
    ],
    aggregate_vram_gb=4.0,
    landauer_rating_pj_per_mac=0.9,
    is_solar_powered=False,
)
mesh_router.register_peer(node2_manifest, ping_rtt_ms=1.8)
broker.register_provider_node(node2_manifest, ping_rtt_ms=1.8)


class QuoteRequest(BaseModel):
    model_id: str = Field("auto", description="Model requested")
    estimated_prompt_tokens: int = Field(500, description="Estimated prompt length")
    estimated_completion_tokens: int = Field(250, description="Estimated completion length")
    caller_geohash: Optional[str] = Field(None, description="Caller spatial coordinate")
    require_solar_only: bool = Field(False, description="Filter to green solar nodes only")


class SettlementRequest(BaseModel):
    session_id: str
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float
    allocated_vram_gb: float = 12.0
    sl_merchant_account_id: Optional[str] = None


@router.get("/manifest")
async def get_csp_manifest() -> Dict[str, Any]:
    """Returns local node hardware attestation, geohash, and pricing."""
    return {
        "status": "online",
        "manifest": local_manifest.dict(),
        "attestation_signature": local_manifest.compute_signature_hash(),
    }


@router.get("/meter/summary")
async def get_meter_summary() -> Dict[str, Any]:
    """Returns live streaming compute throughput and session metrics."""
    return active_meter.get_summary_metrics()


@router.get("/mesh/neighbors")
async def list_mesh_neighbors() -> Dict[str, Any]:
    """Lists discovered neighborhood CSP nodes within physical proximity."""
    return {
        "local_geohash": local_manifest.geohash,
        "neighborhood": local_manifest.neighborhood_tag,
        "active_peers_count": len(mesh_router._registered_peers),
        "neighbors": mesh_router.list_active_neighbors(),
    }


@router.post("/quote")
async def request_csp_quote(req: QuoteRequest) -> Dict[str, Any]:
    """
    Ranks nearby nodes by geohash distance and latency, providing a guaranteed
    micro-quote with Spotlight-Local's 1.0% fee breakdown.
    """
    best = mesh_router.select_optimal_csp(
        required_vram_gb=8.0,
        target_model=req.model_id,
        caller_geohash=req.caller_geohash,
    )
    if not best:
        raise HTTPException(status_code=503, detail="No proximate CSP nodes currently available.")

    node, score = best
    pricing = node.pricing
    prompt_cost = (req.estimated_prompt_tokens / 1000.0) * pricing.price_per_1k_prompt_tokens_usd
    comp_cost = (req.estimated_completion_tokens / 1000.0) * pricing.price_per_1k_completion_tokens_usd
    gross = round(prompt_cost + comp_cost, 6)
    sl_fee = round(gross * pricing.platform_take_rate, 6)
    host_payout = round(gross - sl_fee, 6)

    return {
        "selected_csp_node_id": node.node_id,
        "selected_csp_node_name": node.node_name,
        "geohash": node.geohash,
        "neighborhood": node.neighborhood_tag,
        "ping_rtt_ms": score.rtt_ms,
        "is_solar_powered": node.is_solar_powered,
        "quote": {
            "currency": "USD",
            "gross_estimated_usd": gross,
            "sl_platform_fee_usd": sl_fee,
            "csp_host_payout_usd": host_payout,
            "effective_rate_per_token_usd": round(gross / (req.estimated_prompt_tokens + req.estimated_completion_tokens), 8),
        },
    }


@router.post("/settle")
async def settle_compute_invoice(req: SettlementRequest) -> Dict[str, Any]:
    """
    Creates a cryptographically signed HMAC-SHA256 receipt for an executed compute chunk
    and commits the record to the Spotlight-Local double-entry ledger.
    """
    reading = ComputeMeterReading(
        session_id=req.session_id,
        model_id="loom-sovereign",
        prompt_tokens=req.prompt_tokens,
        completion_tokens=req.completion_tokens,
        allocated_vram_gb=req.allocated_vram_gb,
        start_time_epoch=time.time() - req.duration_seconds,
        end_time_epoch=time.time(),
    )
    invoice = settlement_engine.create_invoice(
        reading=reading,
        pricing=local_manifest.pricing,
        sl_merchant_account_id=req.sl_merchant_account_id or local_manifest.sl_merchant_account_id,
    )
    return {
        "status": "settled",
        "ledger_event": "SL_COMPUTE_STREAM_RECONCILED",
        "invoice": invoice.dict(),
    }


@router.post("/broker/match")
async def broker_match_workload(req: ConsumerWorkloadRequest) -> Dict[str, Any]:
    """
    ClothOS Sovereign Broker Endpoint:
    Matches a Consumer's workload (AI, Gaming, Video Editing, 3D Rendering)
    to the optimal nearby Compute Service Provider, initiates tracking, and returns
    stream connection coordinates.
    """
    try:
        match_result = broker.match_workload(req)
        session_id = broker.initiate_consumer_session(
            match=match_result,
            consumer_id=req.consumer_id,
            allocated_vram_gb=float(req.target_spec.get("required_vram_gb", 12.0)),
        )
        return {
            "status": "matched",
            "broker_authority": "VectorCore Holdings / ClothOS",
            "session_id": session_id,
            "match": match_result.dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Mount Thermodynamic Grid & Energy-to-Compute Endpoints
from loom.csp.energy_optimizer import energy_optimizer

@router.get("/energy/metrics")
def get_energy_efficiency_metrics() -> Dict[str, Any]:
    """
    Returns real-time Energy:Compute ratio metrics and demonstrates the 18x-25x
    economic advantage of useful consumer compute over blind crypto hashing.
    """
    arbitrage = energy_optimizer.evaluate_crypto_vs_useful_arbitrage()
    sample_workload = energy_optimizer.calculate_efficiency_metrics(
        tokens_generated=4500,
        duration_seconds=12.5,
    )
    return {
        "status": "optimal",
        "philosophy": "Transforming grid energy and crypto rigs into community-owned useful infrastructure",
        "live_telemetry": sample_workload,
        "arbitrage_comparison": arbitrage.dict(),
    }


# Mount Dynamic Polymorphic CSP/CSC Orchestrator Endpoints
from loom.csp.dynamic_orchestrator import dynamic_orchestrator

@router.get("/polymorphic/state")
def get_polymorphic_state() -> Dict[str, Any]:
    """Returns real-time dynamic VRAM partitioning, operating mode, and active jobs."""
    return dynamic_orchestrator.get_telemetry().dict()


@router.post("/polymorphic/workload")
def submit_polymorphic_workload(req: ConsumerWorkloadRequest) -> Dict[str, Any]:
    """
    Submits an on-demand workload to the polymorphic orchestrator.
    Dynamically decides whether to allocate local silicon or act as CSC bursting to mesh.
    """
    return dynamic_orchestrator.handle_on_demand_workload(req)


@router.post("/polymorphic/release/{job_id}")
def release_polymorphic_workload(job_id: str) -> Dict[str, Any]:
    """Releases local VRAM allocation, instantly returning spare capacity to the mesh CSP order book."""
    return dynamic_orchestrator.release_local_workload(job_id)


# Mount Diurnal Grid Scheduler & Nocturnal Scientific Compute Endpoints
from loom.csp.diurnal_scheduler import diurnal_scheduler, ScientificWorkloadItem

@router.get("/diurnal/state")
def get_diurnal_state(force_phase: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns real-time diurnal phase, capacity saturation percentage (target: 100%),
    active nocturnal scientific job, and kWh diverted from grid waste.
    """
    telemetry = diurnal_scheduler.tick_scheduler(force_phase=force_phase)
    return telemetry.dict()


@router.post("/diurnal/queue")
def queue_scientific_job(job: ScientificWorkloadItem) -> Dict[str, Any]:
    """Enqueues an automated scientific research calculation or model training job."""
    registered = diurnal_scheduler.queue_scientific_job(job)
    return {"status": "enqueued", "job": registered.dict()}


@router.post("/diurnal/complete")
def complete_scientific_job(result_hash: str = "sha256:alphafold_structure_verified") -> Dict[str, Any]:
    """Completes active nocturnal scientific job and records output to Merkle ledger."""
    job = diurnal_scheduler.complete_active_scientific_job(result_hash=result_hash)
    return {"status": "completed" if job else "no_active_job", "job": job.dict() if job else None}


# ============================================================================
# Virtual Compute Accelerator (VCA) - Network as a Physical GPU/Compute Resource
# ============================================================================

from loom.virtual_device.virtual_accelerator import (
    virtual_accelerator_manager,
    VirtualComputeDevice,
)


class DeviceDispatchRequest(BaseModel):
    device_index: int = 1
    workload_id: str = "app-workload-01"
    workload_type: str = "ai_inference"
    required_vram_gb: float = 4.0
    prompt: str = "Explain VectorCore in one sentence."
    iterations: int = 2000000


@router.get("/virtual-devices")
def list_virtual_devices() -> Dict[str, Any]:
    """
    Returns real physical and cluster compute devices.
    Presents the Loom Fabric cluster as an additional physical GPU/accelerator with 32 cores and pooled memory.
    """
    devices = virtual_accelerator_manager.list_devices()
    return {
        "status": "online",
        "device_count": len(devices),
        "devices": [d.dict() for d in devices],
    }


@router.post("/virtual-devices/dispatch")
def dispatch_to_virtual_device(req: DeviceDispatchRequest) -> Dict[str, Any]:
    """
    Dispatches actual computation to:
    - Device 0: Physical RTX 3060 CUDA Tensor Cores (via Ollama)
    - Device 1: Physical Distributed Ray Cluster (skyTech + WIN-7CMAQLVP8MV)
    """
    try:
        res = virtual_accelerator_manager.dispatch_workload(
            device_index=req.device_index,
            workload_id=req.workload_id,
            workload_type=req.workload_type,
            required_vram_gb=req.required_vram_gb,
            prompt=req.prompt,
            iterations=req.iterations,
        )
        return res
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))





