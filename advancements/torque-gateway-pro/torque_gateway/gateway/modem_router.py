# Copyright (c) 2026 Najmos Sakib / VectorCore Holdings, LLC.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Fabric Modem & Seamless Mesh Gateway Endpoints (`loom/gateway/modem_router.py`).
==============================================================================
Provides REST and SSE endpoints for inspecting Fabric Modem signal strength,
scanning for local/regional compute nodes, dispatching compute seamlessly,
and serving isolated VFS / SPA routes based on Accept headers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from loom.hardware.seamless_gateway import SeamlessComputeGateway
from loom.governance.ring_p0 import RingP0GovernanceController

logger = logging.getLogger("loom.gateway.modem_router")
router = APIRouter(prefix="/v1/fabric/modem", tags=["Fabric Modem"])


class ConnectRequest(BaseModel):
    ssid: str = Field(..., description="Target Fabric Mesh SSID to associate with")


class DispatchRequest(BaseModel):
    prompt: Any = Field(..., description="Compute prompt, task, or payload")
    model: str = Field("auto", description="Target model tier: 'auto', '7b', '70b'")
    required_vram_gb: float = Field(4.0, description="Estimated VRAM requirement in GB")
    workload_type: str = Field("llm_inference", description="Workload type (llm_inference, base12_convert, base16_frame, atgc_analysis)")
    requires_nvidia: bool = False


@router.get("/status")
async def get_modem_status(request: Request, accept: Optional[str] = Header(None)) -> Response:
    """Returns real-time Fabric Modem telemetry, RSSI, SNR, and signal bars.
    Enforces VFS vs SPA proxy route isolation (HTML vs JSON).
    """
    gw = SeamlessComputeGateway.get_instance()
    telem = gw.modem.get_telemetry()
    
    # VFS vs SPA isolation check
    if accept and "text/html" in accept:
        card = gw.get_mesh_status_card()
        html_content = f"<html><head><title>ClothOS Modem Status</title></head><body style='background:#111;color:#0f0;font-family:monospace;'><pre>{card}</pre></body></html>"
        return HTMLResponse(content=html_content)
    
    return JSONResponse(content=telem)


@router.get("/scan")
async def scan_modem_networks() -> List[Dict[str, Any]]:
    """Scans local RF airwaves and direct-wire interfaces for in-range Fabric compute nodes."""
    gw = SeamlessComputeGateway.get_instance()
    return gw.modem.scan_airwaves()


@router.post("/connect")
async def connect_to_ssid(req: ConnectRequest) -> Dict[str, Any]:
    """Associates the Fabric Modem with a specific Mesh SSID."""
    gw = SeamlessComputeGateway.get_instance()
    success = gw.modem.associate(req.ssid)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to associate with SSID '{req.ssid}'. Out of range or signal attenuated."
        )
    return {
        "status": "connected",
        "ssid": req.ssid,
        "telemetry": gw.modem.get_telemetry(),
    }


@router.post("/dispatch")
async def seamless_dispatch(req: DispatchRequest) -> Dict[str, Any]:
    """Seamlessly dispatches a compute task across the Fabric Mesh.
    Automatically handles layer partitioning, DMA packetization, and peer execution.
    """
    gw = SeamlessComputeGateway.get_instance()
    res = gw.dispatch(
        prompt_or_payload=req.prompt,
        target_model=req.model,
        required_vram_gb=req.required_vram_gb,
        workload_type=req.workload_type,
        requires_nvidia=req.requires_nvidia,
    )
    return {
        "task_id": res.task_id,
        "status": res.status,
        "result": res.result_text,
        "route": res.execution_route,
        "total_latency_ms": res.total_latency_ms,
        "dma_transit_time_ms": res.dma_transit_time_ms,
        "tflops": res.tflops_dispatched,
        "signal_bars": res.carrier_link_bars,
        "payload_metadata": res.payload_metadata,
    }


@router.get("/card")
async def get_modem_card() -> Dict[str, str]:
    """Returns visual ASCII Wi-Fi card representing current Fabric Mesh link status."""
    gw = SeamlessComputeGateway.get_instance()
    return {"card": gw.get_mesh_status_card()}


@router.get("/governance")
async def get_governance_report() -> Dict[str, Any]:
    """Returns Ring P0 Root of Trust status and audit report."""
    gov = RingP0GovernanceController.get_instance()
    return gov.get_governance_report()
