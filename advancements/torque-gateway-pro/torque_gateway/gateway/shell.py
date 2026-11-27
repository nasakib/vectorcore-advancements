"""
Loom Gateway Shell: FastAPI OpenAI-Compatible API with Zero-Trust Enclave & Dynamic Telemetry.

Part of Pillar 4: LOOM / GATEWAY.
Features:
- Standard `/v1/chat/completions` and `/v1/models` endpoints.
- Full Torque Zero-Trust Enclave scrubbing and on-the-fly streaming rehydration.
- Observability headers: `X-Fabric-Route`, `X-Fabric-TTFT-Ms`, `X-Fabric-Tokens-Per-Sec`, `X-Enclave-Scrubbed`.
- Cluster state endpoint `/api/state` for Streamlit Mission Control UI (:8501).
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from loom.config import get_settings
from loom.fabric.cluster import DualHomedNetworkManager, FabricClusterOrchestrator
from loom.gateway.sse_pipeline import SSEStreamTransformer
from loom.models.registry import ModelRegistry
from loom.torque.enclave import TorqueEnclaveScrubber
from loom.torque.scheduler import TorqueCascadeScheduler
from loom.types import ChatMessageDTO, ExecutionTier, PromptPayload

app = FastAPI(
    title="Loom Fabric Gateway Shell",
    version="0.1.0",
    description="Distributed AI Compute Shell with Zero-Trust Enclave & Heterogeneous Dynamic Routing",
)

# Enable CORS for standard web and desktop client integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core subsystems
settings = get_settings()
scrubber = TorqueEnclaveScrubber()
scheduler = TorqueCascadeScheduler()
network_manager = DualHomedNetworkManager()
orchestrator = FabricClusterOrchestrator()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Cluster gateway health check."""
    return {
        "status": "healthy",
        "service": "loom-fabric-gateway-shell",
        "version": "0.1.0",
        "timestamp": time.time(),
        "torque_enclave_active": True,
    }


@app.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    """OpenAI-compatible models enumeration endpoint."""
    presets = ModelRegistry.list_models()
    model_entries = []
    for p in presets:
        model_entries.append({
            "id": p.id,
            "object": "model",
            "created": 1700000000,
            "owned_by": "loom-fabric",
            "permission": [],
            "root": p.id,
            "parent": None,
            "details": {
                "display_name": p.display_name,
                "total_layers": p.total_layers,
                "default_context": p.default_context_length,
                "quant": p.quant_label,
            },
        })
    return {"object": "list", "data": model_entries}


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """OpenAI-compatible chat completion endpoint supporting SSE streaming and Torque zero-trust routing."""
    body_dict = await req.json()

    # 1. Normalize model name (strip provider prefix like 'loom-fabric/' or 'ollama/')
    raw_model = body_dict.get("model", "auto")
    clean_model = raw_model.split("/", 1)[1] if "/" in raw_model else raw_model
    body_dict["model"] = clean_model

    # 2. Normalize messages into flat string payloads
    normalized_messages = []
    for m in body_dict.get("messages", []):
        if isinstance(m, dict):
            m_copy = dict(m)
            m_copy["content"] = ChatMessageDTO.normalize_content(m.get("content", ""))
            normalized_messages.append(m_copy)
        else:
            normalized_messages.append(m)
    body_dict["messages"] = normalized_messages

    # Parse into immutable DTOs
    messages_dto = [
        ChatMessageDTO(
            role=m.get("role", "user") if isinstance(m, dict) else "user",
            content=m.get("content", "") if isinstance(m, dict) else str(m),
        )
        for m in body_dict.get("messages", [])
    ]
    payload = PromptPayload(
        model=clean_model,
        messages=messages_dto,
        temperature=body_dict.get("temperature", 0.7),
        top_p=body_dict.get("top_p", 0.95),
        max_tokens=body_dict.get("max_tokens", 4096),
        stream=body_dict.get("stream", False),
        force_local=body_dict.get("force_local", False),
        airgap=body_dict.get("airgap", False),
    )

    # 3. Torque 3-Tier Cascade Routing Decision
    decision = scheduler.route(payload)
    dispatched_model = decision.model_name
    body_dict["model"] = dispatched_model

    # Check 300s Arbitrage Circuit Breaker
    if decision.circuit_breaker_triggered and decision.requires_manual_approval:
        # If client has not provided explicit bypass flag
        if not body_dict.get("bypass_approval", False):
            return JSONResponse(
                status_code=402,
                content={
                    "error": {
                        "message": (
                            f"Torque Circuit Breaker: Estimated compute duration {decision.estimated_duration_seconds:.1f}s "
                            f"exceeds 300s limit. Manual confirmation required in Mission Control UI."
                        ),
                        "type": "circuit_breaker_approval_required",
                        "decision": decision.model_dump(),
                    }
                },
                headers={
                    "X-Fabric-Route": decision.tier.value,
                    "X-Fabric-Circuit-Breaker": "tripped",
                },
            )

    # 4. Zero-Trust Enclave Scrubbing if routing to Cloud Tier 3
    active_vault_map: Dict[str, str] = {}
    is_scrubbed = False

    if decision.tier == ExecutionTier.TIER_3_SOVEREIGN_CLOUD:
        scrubbed_messages = []
        for msg in payload.messages:
            scrub_res = scrubber.tokenize_and_store(msg.content)
            scrubbed_messages.append({"role": msg.role, "content": scrub_res.scrubbed_text})
            active_vault_map.update(scrub_res.vault_token_map)
        body_dict["messages"] = scrubbed_messages
        is_scrubbed = len(active_vault_map) > 0

    # 5. Resolve Active Endpoint via Dual-Homed Network Manager
    if decision.tier == ExecutionTier.TIER_3_SOVEREIGN_CLOUD:
        target_url = settings.torque.cloud_api_url
        route_label = "Sovereign-Cloud-Arbitrage"
    else:
        target_url, route_label = network_manager.resolve_active_worker_endpoint(8080)

    # Build response headers
    base_headers = {
        "X-Fabric-Route": decision.tier.value,
        "X-Fabric-Target": route_label,
        "X-Fabric-Model-Selected": dispatched_model,
        "X-Enclave-Scrubbed": str(is_scrubbed).lower(),
        "X-Torque-Reasoning": decision.reasoning,
    }

    # 6. Stream Execution with On-The-Fly Rehydration
    if payload.stream:
        transformer = SSEStreamTransformer(vault_map=active_vault_map, scrubber=scrubber)

        async def generate_response() -> AsyncIterator[str]:
            # Connect to backend
            client = httpx.AsyncClient(timeout=300.0)
            try:
                # If local Ollama fallback
                if "11434" in target_url or "Head-Node" in route_label:
                    ollama_payload = {
                        "model": dispatched_model,
                        "messages": body_dict.get("messages", []),
                        "stream": True,
                    }
                    async with client.stream("POST", "http://127.0.0.1:11434/api/chat", json=ollama_payload) as resp:
                        async for sse_chunk in transformer.transform_stream(resp.aiter_lines(), dispatched_model):
                            yield sse_chunk
                else:
                    async with client.stream("POST", f"{target_url}/v1/chat/completions", json=body_dict) as resp:
                        async for sse_chunk in transformer.transform_stream(resp.aiter_lines(), dispatched_model):
                            yield sse_chunk
            finally:
                await client.aclose()

        headers = {
            **base_headers,
            "X-Fabric-TTFT-Ms": str(transformer.ttft_ms),
            "X-Fabric-Tokens-Per-Sec": str(transformer.tokens_per_sec),
        }
        return StreamingResponse(generate_response(), media_type="text/event-stream", headers=headers)

    else:
        # Non-streaming synchronous execution
        start_t = time.time()
        client = httpx.AsyncClient(timeout=300.0)
        try:
            if "11434" in target_url or "Head-Node" in route_label:
                ollama_payload = {
                    "model": dispatched_model,
                    "messages": body_dict.get("messages", []),
                    "stream": False,
                }
                res = await client.post("http://127.0.0.1:11434/api/chat", json=ollama_payload)
                res.raise_for_status()
                data = res.json()
                content = data.get("message", {}).get("content", "")

                # Rehydrate if scrubbed
                if is_scrubbed and active_vault_map:
                    content = scrubber.rehydrate(content, active_vault_map)

                resp_dict = {
                    "id": f"chatcmpl-{dispatched_model}",
                    "object": "chat.completion",
                    "created": int(start_t),
                    "model": dispatched_model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": data.get("eval_count", 50)},
                }
            else:
                res = await client.post(f"{target_url}/v1/chat/completions", json=body_dict)
                res.raise_for_status()
                resp_dict = res.json()

                if is_scrubbed and active_vault_map:
                    for choice in resp_dict.get("choices", []):
                        msg = choice.get("message", {})
                        if "content" in msg:
                            msg["content"] = scrubber.rehydrate(msg["content"], active_vault_map)
        finally:
            await client.aclose()

        elapsed = max(0.001, time.time() - start_t)
        tokens = resp_dict.get("usage", {}).get("total_tokens", 50)
        tps = round(tokens / elapsed, 2)

        headers = {
            **base_headers,
            "X-Fabric-TTFT-Ms": str(round(elapsed * 1000, 2)),
            "X-Fabric-Tokens-Per-Sec": str(tps),
        }
        return JSONResponse(content=resp_dict, headers=headers)


@app.get("/api/state")
async def cluster_state() -> Dict[str, Any]:
    """Exposes comprehensive telemetry for the Streamlit Mission Control UI (:8501)."""
    return {
        "cluster_status": orchestrator.get_cluster_status(),
        "vault_active_tokens": len(scrubber.vault.snapshot()),
        "network_matrix": network_manager.resolve_active_worker_endpoint(8080),
        "gateway_port": settings.gateway_port,
    }
