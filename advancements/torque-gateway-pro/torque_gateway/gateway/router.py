"""
Gateway Request Routing and Backend Dispatcher.

Directs incoming OpenAI completion requests dynamically:
- To Ray Cluster's InferenceDirector if Ray is connected and active.
- To local Stitch Worker supervisor if operating in standalone/direct mode.
- Fallback to local Ollama API (11434) if native llama-server is not running.

Rust Migration Blueprint:
    In the native `loom-core` Rust crate:
    ```rust
    pub struct GatewayRouter {
        pub director: Option<Arc<InferenceDirector>>,
        pub local_backend: Option<Arc<StitchSupervisor>>,
        pub fallback_ollama_url: String,
    }
    ```
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional, Tuple
import httpx

from loom.config import get_settings
from loom.fabric.cluster import RayClusterManager
from loom.models.registry import ModelRegistry

logger = logging.getLogger("loom.gateway.router")


class GatewayRouter:
    """Intelligent request router with multi-tier failover and streaming proxy support."""

    def __init__(self, ray_manager: Optional[RayClusterManager] = None):
        self.settings = get_settings()
        self.ray_manager = ray_manager or RayClusterManager()
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0))

    async def determine_target_endpoint(
        self,
        model_name: str,
        tier: Optional[Any] = None,
        cloud_url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Determines the best available backend URL and provider name for the request.

        Returns:
            Tuple of (endpoint_url, provider_name)
        """
        import os

        # 0. Check if routed to Tier 3 Sovereign Cloud (only if a real cloud API key is configured)
        if tier and ("cloud" in str(tier).lower() or "tier_3" in str(tier).lower()):
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
            if api_key and api_key != "enclave-dummy-token":
                target = cloud_url or self.settings.torque.cloud_api_url
                return target, "Sovereign-Cloud-Arbitrage"

        # 1. Check if Ray cluster is active with registered director
        if self.ray_manager.is_connected:
            try:
                import ray
                from loom.fabric.actors import InferenceDirector
                director = ray.get_actor("InferenceDirector")
                status = ray.get(director.get_cluster_status.remote())
                if status.get("worker_endpoint"):
                    return status["worker_endpoint"], "Ray-Fabric-Cluster"
            except Exception as e:
                logger.debug(f"Ray director lookup skipped: {e}")

        # 2. Check primary Stitch native backend on desktop worker (port 8080)
        worker_endpoint = self.settings.endpoints.worker_native_url
        try:
            res = await self.client.get(f"{worker_endpoint}/health", timeout=1.0)
            if res.status_code == 200:
                return worker_endpoint, "Stitch-Native-Worker"
        except Exception:
            pass

        # 3. Check local Stitch native backend on localhost (port 8080)
        try:
            res = await self.client.get("http://127.0.0.1:8080/health", timeout=1.0)
            if res.status_code == 200:
                return "http://127.0.0.1:8080", "Stitch-Local-Direct"
        except Exception:
            pass

        # 4. Fallback to local Ollama on 127.0.0.1:11434 or 192.168.99.1:11434
        for ollama_host in ["http://127.0.0.1:11434", "http://192.168.99.1:11434"]:
            try:
                res = await self.client.get(f"{ollama_host}/api/version", timeout=1.0)
                if res.status_code == 200:
                    return ollama_host, "Ollama-Local-Fallback"
            except Exception:
                pass

        # Default fallback to local Ollama
        return "http://127.0.0.1:11434", "Ollama-Local-Fallback"

    def _resolve_ollama_model(self, model_name: str, payload: Dict[str, Any], provider_name: str) -> str:
        """Resolves model identifier to an installed local Ollama tag and prevents single-GPU 32B OOM/timeouts."""
        if "/" in model_name:
            model_name = model_name.split("/", 1)[1]
        preset = ModelRegistry.get_model(model_name)
        resolved = preset.ollama_tag if (preset and preset.ollama_tag) else model_name

        if resolved in ("auto", "default", "loom-fabric-qct", "gemini-2.5-flash", "gpt-4o"):
            resolved = "qwen2.5:7b"

        # When running on single-GPU Ollama fallback without distributed Ray/Stitch sharding,
        # large tool-enabled OpenClaw sessions (>8k chars or tool definitions) on 32B spill to CPU RAM
        # and exceed Discord/OpenClaw timeouts. Auto-triage to pure-CUDA qwen2.5:7b.
        if "Ollama" in provider_name and resolved == "qwen2.5:32b":
            total_chars = sum(len(str(m.get("content", ""))) for m in payload.get("messages", []) if isinstance(m, dict))
            has_tools = bool(payload.get("tools"))
            if has_tools or total_chars > 8000:
                logger.info(
                    f"Single-node Ollama guard: routing heavy/tool session ({total_chars} chars, tools={has_tools}) "
                    "from qwen2.5:32b to pure-CUDA qwen2.5:7b to prevent CPU-spill timeout."
                )
                resolved = "qwen2.5:7b"

        return resolved

    def _prepare_openai_payload(self, payload: Dict[str, Any], resolved_model: str) -> Dict[str, Any]:
        """Normalizes OpenAI chat completion payload for compatibility with Ollama /v1/chat/completions,
        ensuring strict JSON Schema tool validation and persistent tool IDs."""
        import uuid
        clean = dict(payload)
        clean["model"] = resolved_model
        # Remove custom Loom-only fields before forwarding to upstream OpenAI/Ollama endpoints
        clean.pop("force_local", None)
        clean.pop("airgap", None)

        # 1. Sanitize tool definitions: Guarantee valid parameters, object type, and properties dict
        if "tools" in clean and isinstance(clean["tools"], list):
            sanitized_tools = []
            for t in clean["tools"]:
                if not isinstance(t, dict):
                    continue
                tc = dict(t)
                if "type" not in tc:
                    tc["type"] = "function"
                if "function" in tc and isinstance(tc["function"], dict):
                    fn = dict(tc["function"])
                    params = fn.get("parameters")
                    if not isinstance(params, dict):
                        params = {"type": "object", "properties": {}}
                    else:
                        params = dict(params)
                        if "type" not in params:
                            params["type"] = "object"
                        if "properties" not in params or not isinstance(params["properties"], dict):
                            params["properties"] = {}
                        # Validate all properties have at least a schema type definition
                        for prop_name, prop_val in list(params["properties"].items()):
                            if not isinstance(prop_val, dict):
                                params["properties"][prop_name] = {"type": "string", "description": str(prop_val)}
                            elif "type" not in prop_val and "enum" not in prop_val and "$ref" not in prop_val:
                                prop_val["type"] = "string"
                    fn["parameters"] = params
                    tc["function"] = fn
                sanitized_tools.append(tc)
            clean["tools"] = sanitized_tools

        # 2. Normalize messages: roles, ensure valid tool_calls IDs and tool_call_id on tool results
        msgs = []
        for idx, m in enumerate(clean.get("messages", [])):
            if isinstance(m, dict):
                mc = dict(m)
                if mc.get("role") == "developer":
                    mc["role"] = "system"

                # Ensure every tool_call in assistant messages has a valid, non-empty ID
                if "tool_calls" in mc and isinstance(mc["tool_calls"], list):
                    clean_tool_calls = []
                    for t_idx, tc in enumerate(mc["tool_calls"]):
                        if isinstance(tc, dict):
                            tcc = dict(tc)
                            if not tcc.get("id"):
                                tcc["id"] = f"call_{uuid.uuid4().hex[:8]}_{idx}_{t_idx}"
                            if "type" not in tcc:
                                tcc["type"] = "function"
                            clean_tool_calls.append(tcc)
                    mc["tool_calls"] = clean_tool_calls

                # Ensure tool-response messages possess a valid tool_call_id
                if mc.get("role") == "tool" and not mc.get("tool_call_id"):
                    mc["tool_call_id"] = f"call_tool_{uuid.uuid4().hex[:8]}"

                msgs.append(mc)
            else:
                msgs.append(m)
        clean["messages"] = msgs
        return clean

    def _sanitize_sse_chunk(self, chunk: str) -> str:
        """Ensures streamed tool calls in SSE chunks contain valid IDs."""
        import json, uuid
        if not chunk.startswith("data: ") or chunk.strip() == "data: [DONE]":
            return chunk
        try:
            payload_str = chunk[6:]
            data = json.loads(payload_str)
            modified = False
            for choice in data.get("choices", []):
                delta = choice.get("delta", {})
                if "tool_calls" in delta and isinstance(delta["tool_calls"], list):
                    for idx, tc in enumerate(delta["tool_calls"]):
                        if isinstance(tc, dict) and not tc.get("id") and tc.get("index", 0) == 0:
                            tc["id"] = f"call_{uuid.uuid4().hex[:8]}"
                            modified = True
            if modified:
                return f"data: {json.dumps(data)}"
        except Exception:
            pass
        return chunk

    async def stream_chat_completion(
        self,
        payload: Dict[str, Any],
        target_url: str,
        provider_name: str,
    ) -> AsyncIterator[str]:
        """Streams Server-Sent Events (SSE) from the underlying backend to the gateway client."""
        raw_model = payload.get("model", "qwen2.5:7b")
        resolved_model = self._resolve_ollama_model(raw_model, payload, provider_name)
        forward_payload = self._prepare_openai_payload(payload, resolved_model)
        forward_payload["stream"] = True

        endpoint = (
            target_url
            if target_url.endswith("/chat/completions")
            else f"{target_url.rstrip('/')}/v1/chat/completions"
        )

        try:
            async with self.client.stream(
                "POST",
                endpoint,
                json=forward_payload,
                timeout=300.0,
            ) as response:
                if response.status_code >= 400 and resolved_model != "qwen2.5:7b":
                    raise httpx.HTTPStatusError(
                        f"Upstream status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield f"{self._sanitize_sse_chunk(chunk)}\n\n"
                return
        except Exception as exc:
            logger.warning(f"Primary stream ({endpoint}, model={resolved_model}) failed ({exc}); failing over to qwen2.5:7b.")

        # Automatic failover to local Ollama qwen2.5:7b
        fallback_payload = self._prepare_openai_payload(payload, "qwen2.5:7b")
        fallback_payload["stream"] = True
        async with self.client.stream(
            "POST",
            "http://127.0.0.1:11434/v1/chat/completions",
            json=fallback_payload,
            timeout=300.0,
        ) as response:
            async for chunk in response.aiter_lines():
                if chunk:
                    yield f"{self._sanitize_sse_chunk(chunk)}\n\n"

    def _sanitize_response_tool_calls(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures all tool calls in completion choices have valid IDs and type fields."""
        import uuid
        for choice in data.get("choices", []):
            msg = choice.get("message", {})
            if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                for idx, tc in enumerate(msg["tool_calls"]):
                    if isinstance(tc, dict):
                        if not tc.get("id"):
                            tc["id"] = f"call_{uuid.uuid4().hex[:8]}_{idx}"
                        if "type" not in tc:
                            tc["type"] = "function"
        return data

    async def execute_non_streaming_completion(
        self,
        payload: Dict[str, Any],
        target_url: str,
        provider_name: str,
    ) -> Dict[str, Any]:
        """Dispatches a synchronous/non-streaming completion request with automatic local failover."""
        raw_model = payload.get("model", "qwen2.5:7b")
        resolved_model = self._resolve_ollama_model(raw_model, payload, provider_name)
        forward_payload = self._prepare_openai_payload(payload, resolved_model)
        forward_payload["stream"] = False

        endpoint = (
            target_url
            if target_url.endswith("/chat/completions")
            else f"{target_url.rstrip('/')}/v1/chat/completions"
        )

        try:
            res = await self.client.post(endpoint, json=forward_payload, timeout=300.0)
            res.raise_for_status()
            return self._sanitize_response_tool_calls(res.json())
        except Exception as exc:
            logger.warning(f"Primary completion ({endpoint}, model={resolved_model}) failed ({exc}); failing over to qwen2.5:7b.")
            fallback_payload = self._prepare_openai_payload(payload, "qwen2.5:7b")
            fallback_payload["stream"] = False
            res = await self.client.post(
                "http://127.0.0.1:11434/v1/chat/completions",
                json=fallback_payload,
                timeout=300.0,
            )
            res.raise_for_status()
            return self._sanitize_response_tool_calls(res.json())
