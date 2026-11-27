# Copyright (c) 2026 Najmos Sakib / VectorCore Holdings, LLC.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Anthropic Messages API & Unified Sovereign Nexus Bridge (`loom/gateway/anthropic_bridge.py`).
============================================================================================
Provides full drop-in Anthropic API compatibility on Loom Fabric Gateway (:8002):
  - POST /v1/messages              (streaming SSE & JSON, tools, tool_use, thinking blocks)
  - POST /v1/messages/count_tokens (token estimation compatible with Anthropic SDKs / Claude Code)
  - GET  /v1/sovereign/mesh        (live multi-project ecosystem health & topology)
  - POST /v1/sovereign/audit       (Constitutional + Epistemic + Adversarial Deceit tribunal)
  - POST /v1/sovereign/verify      (Formal Z3 / Active Inference / Topological Betti verification)
  - POST /v1/sovereign/jit/eval    (Sub-millisecond bare-metal universal-jit x86-64 execution)
  - POST /v1/sovereign/typemetric/sync (Dozenal Base-12 Kuramoto sync + Gonzalez pruning + WHT)
  - POST /v1/sovereign/deliberate  (Multi-trajectory verified test-time reasoning)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from loom.gateway.router import GatewayRouter
from loom.torque.router import TorqueRouter
from loom.torque.scrubber import TorqueScrubber
from loom.types import ChatMessageDTO, ExecutionTier, PromptPayload
from loom.unified_nexus import (
    get_sovereign_nexus,
    prune_messages_gonzalez,
    tm_dozenal_kuramoto_step_batch,
    tm_gonzalez_select,
    tm_wht_eval,
)

anthropic_router = APIRouter(tags=["Anthropic-Compatible API"])
sovereign_router = APIRouter(prefix="/v1/sovereign", tags=["Sovereign Unified Nexus"])

_torque_router = TorqueRouter()
_torque_scrubber = TorqueScrubber()
_gateway_router = GatewayRouter()


# ============================================================================
# 1. ANTHROPIC <-> OPENAI TRANSLATION HELPERS
# ============================================================================

def resolve_anthropic_model(requested_model: str) -> str:
    """Maps Anthropic / Claude / ClothOS model identifiers to Sovereign local/cluster models."""
    m = (requested_model or "auto").strip()
    lower = m.lower()
    if "/" in lower:
        lower = lower.split("/", 1)[1]
    if "opus" in lower:
        return "qwen2.5:32b"
    if "sonnet" in lower:
        return "qwen2.5:32b"
    if "haiku" in lower:
        return "qwen2.5:7b"
    if "coder" in lower:
        return "qwen2.5-coder:7b"
    if "r1" in lower or "reason" in lower:
        return "deepseek-r1:14b"
    if lower in ("clothos", "clothos-sovereign", "sovereign", "auto", "default"):
        return "auto"
    return m


def _flatten_system_prompt(system_field: Any) -> str:
    if not system_field:
        return ""
    if isinstance(system_field, str):
        return system_field
    if isinstance(system_field, list):
        parts = []
        for blk in system_field:
            if isinstance(blk, dict):
                parts.append(str(blk.get("text", "")))
            else:
                parts.append(str(blk))
        return "\n\n".join(p for p in parts if p)
    return str(system_field)


def _anthropic_tools_to_openai(tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Converts Anthropic tool definitions (`input_schema`) to strict OpenAI function schemas."""
    if not tools:
        return []
    out: List[Dict[str, Any]] = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "").strip()
        if not name:
            continue
        schema = t.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        else:
            schema = dict(schema)
            schema.setdefault("type", "object")
            if not isinstance(schema.get("properties"), dict):
                schema["properties"] = {}
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": str(t.get("description", "")),
                "parameters": schema,
            },
        })
    return out


def _anthropic_messages_to_openai(
    messages: List[Dict[str, Any]],
    system_text: str = "",
) -> List[Dict[str, Any]]:
    """
    Translates Anthropic Messages API messages (including `tool_use` and `tool_result` blocks)
    into normalized OpenAI chat completion messages with guaranteed tool_call IDs.
    """
    openai_msgs: List[Dict[str, Any]] = []
    if system_text:
        openai_msgs.append({"role": "system", "content": system_text})

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "user"))
        content = msg.get("content", "")

        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            openai_msgs.append({"role": role, "content": str(content)})
            continue

        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        tool_results: List[Dict[str, Any]] = []

        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "text")
            if btype == "text":
                text_parts.append(str(block.get("text", "")))
            elif btype == "tool_use":
                call_id = str(block.get("id") or f"call_{uuid.uuid4().hex[:10]}")
                fn_name = str(block.get("name", "unknown_tool"))
                fn_args = block.get("input", {})
                tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": json.dumps(fn_args) if not isinstance(fn_args, str) else fn_args,
                    },
                })
            elif btype == "tool_result":
                tool_use_id = str(block.get("tool_use_id") or f"call_{uuid.uuid4().hex[:10]}")
                raw_res = block.get("content", "")
                if isinstance(raw_res, list):
                    res_text = "\n".join(
                        str(item.get("text", item)) if isinstance(item, dict) else str(item)
                        for item in raw_res
                    )
                else:
                    res_text = str(raw_res)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": res_text,
                })
            elif btype == "thinking":
                # Do not echo historical reasoning blocks back to backend models
                continue

        if role == "assistant":
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": "\n".join(p for p in text_parts if p),
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            openai_msgs.append(assistant_msg)
        else:
            if text_parts:
                openai_msgs.append({
                    "role": role,
                    "content": "\n".join(p for p in text_parts if p),
                })
            openai_msgs.extend(tool_results)

    return openai_msgs


def _openai_choice_to_anthropic_blocks(
    choice: Dict[str, Any],
    thinking_payload: Optional[Dict[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], str]:
    """Converts an OpenAI completion choice (+ optional verified thinking) into Anthropic content blocks."""
    blocks: List[Dict[str, Any]] = []
    if thinking_payload and thinking_payload.get("thinking_text"):
        blocks.append({
            "type": "thinking",
            "thinking": thinking_payload["thinking_text"],
            "signature": thinking_payload.get("signature", ""),
        })

    msg = choice.get("message", {})
    text = msg.get("content") or ""
    if text:
        blocks.append({"type": "text", "text": text})

    raw_tool_calls = msg.get("tool_calls") or []
    for tc in raw_tool_calls:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function", {})
        raw_args = fn.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args) if raw_args.strip() else {}
            except Exception:
                parsed_args = {"raw": raw_args}
        elif isinstance(raw_args, dict):
            parsed_args = raw_args
        else:
            parsed_args = {}
        blocks.append({
            "type": "tool_use",
            "id": str(tc.get("id") or f"toolu_{uuid.uuid4().hex[:12]}"),
            "name": str(fn.get("name", "unknown")),
            "input": parsed_args,
        })

    if not blocks:
        blocks.append({"type": "text", "text": ""})

    finish_reason = choice.get("finish_reason", "stop")
    if raw_tool_calls or finish_reason == "tool_calls":
        stop_reason = "tool_use"
    elif finish_reason == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"
    return blocks, stop_reason


def _format_sse_event(event_name: str, data: Dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


def _estimate_tokens(obj: Any) -> int:
    text = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return max(1, len(text) // 4)


# ============================================================================
# 2. ANTHROPIC MESSAGES API ENDPOINTS (/v1/messages & /v1/messages/count_tokens)
# ============================================================================

@anthropic_router.post("/v1/messages/count_tokens")
async def anthropic_count_tokens(req: Request) -> Dict[str, Any]:
    """Anthropic-compatible token counting endpoint."""
    body = await req.json()
    total = 0
    if body.get("system"):
        total += _estimate_tokens(body["system"])
    if body.get("messages"):
        total += _estimate_tokens(body["messages"])
    if body.get("tools"):
        total += _estimate_tokens(body["tools"])
    return {"input_tokens": total}


@anthropic_router.post("/v1/messages")
async def anthropic_messages(req: Request):
    """
    Drop-in Anthropic Messages API (`/v1/messages`).
    Integrates:
      - Constitutional, Epistemic & Adversarial Deceit Immune Gate
      - Typemetric Gonzalez k-Center Context Diversity Pruning
      - Verified Multi-Trajectory Extended Thinking (`thinking` blocks)
      - Torque Complexity Routing & Zero-Trust RehydrationVault
      - Full Streaming SSE (`message_start`, `content_block_delta`, `tool_use`, `message_stop`)
    """
    body = await req.json()
    requested_model = str(body.get("model", "claude-sonnet-4-5"))
    system_text = _flatten_system_prompt(body.get("system"))
    raw_messages = body.get("messages", [])
    max_tokens = int(body.get("max_tokens") or 4096)
    temperature = float(body.get("temperature")) if body.get("temperature") is not None else 0.7
    stream = bool(body.get("stream", False))
    thinking_cfg = body.get("thinking") or {}
    thinking_enabled = isinstance(thinking_cfg, dict) and thinking_cfg.get("type") == "enabled"
    thinking_budget = int(thinking_cfg.get("budget_tokens", 2048)) if thinking_enabled else 0
    force_local = bool(body.get("force_local", False))

    openai_messages = _anthropic_messages_to_openai(raw_messages, system_text=system_text)
    openai_tools = _anthropic_tools_to_openai(body.get("tools"))

    # Prune oversized message windows via Typemetric Gonzalez k-center diversity sampling
    max_context_turns = int(body.get("max_context_turns", 32))
    pruned_messages, prune_info = prune_messages_gonzalez(openai_messages, max_turns=max_context_turns)

    # Extract latest user text for Constitutional & Adversarial Deceit Gate
    user_texts = [m["content"] for m in pruned_messages if m.get("role") == "user" and m.get("content")]
    latest_user_prompt = str(user_texts[-1]) if user_texts else ""

    nexus = get_sovereign_nexus()
    pre_audit = nexus.audit_constitutional_and_deceit(
        action_intent="Anthropic API Message Evaluation",
        payload_or_claim=latest_user_prompt,
        estimated_energy_joules=15.0,
    )

    msg_id = f"msg_{uuid.uuid4().hex[:18]}"
    input_tokens = _estimate_tokens({"system": system_text, "messages": pruned_messages, "tools": openai_tools})

    # Constitutional & Adversarial Deceit Veto Response (returns valid Anthropic Message structure)
    severe_deceit = pre_audit["deceit"]["deceit_detected"] and pre_audit["deceit"]["threat_score"] >= 85
    if (not pre_audit["approved"]) and (pre_audit["fiduciary"]["malignancy_score"] >= 0.7 or severe_deceit):
        veto_text = (
            f"[ClothOS Sovereign Constitutional Gate: {pre_audit['ruling']}] "
            f"Request blocked (verdict={pre_audit['verdict_id']}, merkle={pre_audit['merkle_proof'][:16]}...). "
            f"Reason: {pre_audit['narrative']}"
        )
        headers = {
            "X-ClothOS-Verdict": pre_audit["ruling"],
            "X-ClothOS-Merkle-Proof": pre_audit["merkle_proof"],
            "X-ClothOS-Deceit-Detected": str(pre_audit["deceit"]["deceit_detected"]).lower(),
        }
        if not stream:
            return JSONResponse(
                content={
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "model": requested_model,
                    "content": [{"type": "text", "text": veto_text}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": input_tokens, "output_tokens": _estimate_tokens(veto_text)},
                    "clothos_verification": pre_audit,
                },
                headers=headers,
            )

        async def veto_stream() -> AsyncIterator[str]:
            yield _format_sse_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "model": requested_model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                },
            })
            yield _format_sse_event("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            })
            yield _format_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": veto_text},
            })
            yield _format_sse_event("content_block_stop", {"type": "content_block_stop", "index": 0})
            yield _format_sse_event("message_delta", {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": _estimate_tokens(veto_text)},
            })
            yield _format_sse_event("message_stop", {"type": "message_stop"})

        return StreamingResponse(veto_stream(), media_type="text/event-stream", headers=headers)

    # Optional Extended Verified Thinking Block
    thinking_payload: Optional[Dict[str, Any]] = None
    if thinking_enabled and latest_user_prompt:
        thinking_payload = nexus.deliberate_with_verification(
            latest_user_prompt,
            budget_tokens=thinking_budget,
        )

    # Torque Routing & Zero-Trust Scrubbing
    resolved_alias = resolve_anthropic_model(requested_model)
    msgs_dto = [
        ChatMessageDTO(
            role=m.get("role", "user"),
            content=m.get("content", ""),
            tool_call_id=m.get("tool_call_id"),
            tool_calls=m.get("tool_calls"),
        )
        for m in pruned_messages
    ]
    prompt_dto = PromptPayload(
        model=resolved_alias,
        messages=msgs_dto,
        temperature=max(0.0, min(2.0, temperature)),
        top_p=float(body.get("top_p")) if body.get("top_p") is not None else 0.95,
        max_tokens=max(1, min(131072, max_tokens)),
        stream=stream,
        force_local=force_local,
    )
    decision = _torque_router.route(prompt_dto)
    dispatched_model = decision.model_name

    # Override to explicit fast/coder/reasoning alias if user explicitly requested one
    if resolved_alias in ("qwen2.5:7b", "qwen2.5-coder:7b", "deepseek-r1:14b") and decision.tier != ExecutionTier.TIER_3_SOVEREIGN_CLOUD:
        dispatched_model = resolved_alias

    forward_payload: Dict[str, Any] = {
        "model": dispatched_model,
        "messages": pruned_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if openai_tools:
        forward_payload["tools"] = openai_tools
    if body.get("stop_sequences"):
        forward_payload["stop"] = body["stop_sequences"]

    active_vault_map: Dict[str, str] = {}
    is_scrubbed = False
    if decision.tier == ExecutionTier.TIER_3_SOVEREIGN_CLOUD:
        scrubbed_msgs = []
        for m in pruned_messages:
            scrub_res = _torque_scrubber.tokenize_and_store(str(m.get("content", "")))
            m_copy = dict(m)
            m_copy["content"] = scrub_res.scrubbed_text
            scrubbed_msgs.append(m_copy)
            active_vault_map.update(scrub_res.vault_token_map)
        forward_payload["messages"] = scrubbed_msgs
        is_scrubbed = len(active_vault_map) > 0

    target_url, provider_name = await _gateway_router.determine_target_endpoint(
        dispatched_model,
        tier=decision.tier,
        cloud_url=decision.target_endpoint,
    )

    response_headers = {
        "X-Torque-Route": decision.tier.value,
        "X-Torque-Model-Selected": dispatched_model,
        "X-Torque-Scrubbed": str(is_scrubbed).lower(),
        "X-Loom-Provider": provider_name,
        "X-ClothOS-Verdict": pre_audit["ruling"],
        "X-ClothOS-Merkle-Proof": pre_audit["merkle_proof"],
        "X-ClothOS-Epistemic-Grade": pre_audit["epistemic"]["grade"],
        "X-Typemetric-Pruned": str(prune_info["pruned"]).lower(),
    }

    if not stream:
        completion_data = await _gateway_router.execute_non_streaming_completion(
            forward_payload, target_url, provider_name
        )
        choices = completion_data.get("choices", [])
        first_choice = choices[0] if choices else {"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}
        if is_scrubbed and active_vault_map:
            msg_content = first_choice.get("message", {}).get("content", "")
            if msg_content:
                first_choice["message"]["content"] = _torque_scrubber.rehydrate(msg_content, active_vault_map)

        blocks, stop_reason = _openai_choice_to_anthropic_blocks(first_choice, thinking_payload=thinking_payload)
        usage = completion_data.get("usage", {})
        out_tokens = int(usage.get("completion_tokens") or _estimate_tokens(blocks))
        in_tokens = int(usage.get("prompt_tokens") or input_tokens)

        return JSONResponse(
            content={
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": requested_model,
                "content": blocks,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": in_tokens, "output_tokens": out_tokens},
                "clothos_verification": {
                    "verdict": pre_audit["ruling"],
                    "merkle_proof": pre_audit["merkle_proof"],
                    "epistemic_grade": pre_audit["epistemic"]["grade"],
                    "dispatched_model": dispatched_model,
                    "provider": provider_name,
                    "context_pruning": prune_info,
                },
            },
            headers=response_headers,
        )

    # Streaming Anthropic SSE Generator
    async def anthropic_sse_generator() -> AsyncIterator[str]:
        yield _format_sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": requested_model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
            },
        })

        block_index = 0
        output_tokens = 0

        # Emit Verified Extended Thinking block first if requested
        if thinking_payload and thinking_payload.get("thinking_text"):
            yield _format_sse_event("content_block_start", {
                "type": "content_block_start",
                "index": block_index,
                "content_block": {"type": "thinking", "thinking": ""},
            })
            yield _format_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": block_index,
                "delta": {"type": "thinking_delta", "thinking": thinking_payload["thinking_text"]},
            })
            if thinking_payload.get("signature"):
                yield _format_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": block_index,
                    "delta": {"type": "signature_delta", "signature": thinking_payload["signature"]},
                })
            yield _format_sse_event("content_block_stop", {"type": "content_block_stop", "index": block_index})
            output_tokens += _estimate_tokens(thinking_payload["thinking_text"])
            block_index += 1

        text_block_started = False
        text_block_idx = block_index
        tool_buffers: Dict[int, Dict[str, Any]] = {}
        stop_reason = "end_turn"

        async for chunk_line in _gateway_router.stream_chat_completion(
            forward_payload, target_url, provider_name
        ):
            clean_line = chunk_line.strip()
            if not clean_line.startswith("data: "):
                continue
            data_str = clean_line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk_obj = json.loads(data_str)
            except Exception:
                continue

            for ch in chunk_obj.get("choices", []):
                delta = ch.get("delta", {})
                f_reason = ch.get("finish_reason")
                if f_reason == "tool_calls":
                    stop_reason = "tool_use"
                elif f_reason == "length":
                    stop_reason = "max_tokens"

                content_delta = delta.get("content")
                if content_delta:
                    if is_scrubbed and active_vault_map:
                        content_delta = _torque_scrubber.rehydrate(content_delta, active_vault_map)
                    if not text_block_started:
                        text_block_idx = block_index
                        block_index += 1
                        text_block_started = True
                        yield _format_sse_event("content_block_start", {
                            "type": "content_block_start",
                            "index": text_block_idx,
                            "content_block": {"type": "text", "text": ""},
                        })
                    output_tokens += max(1, len(content_delta.split()))
                    yield _format_sse_event("content_block_delta", {
                        "type": "content_block_delta",
                        "index": text_block_idx,
                        "delta": {"type": "text_delta", "text": content_delta},
                    })

                tc_deltas = delta.get("tool_calls") or []
                for tc in tc_deltas:
                    if not isinstance(tc, dict):
                        continue
                    tc_idx = int(tc.get("index", 0))
                    if tc_idx not in tool_buffers:
                        if text_block_started:
                            yield _format_sse_event("content_block_stop", {
                                "type": "content_block_stop",
                                "index": text_block_idx,
                            })
                            text_block_started = False
                        blk_idx = block_index
                        block_index += 1
                        fn_info = tc.get("function", {})
                        tool_id = str(tc.get("id") or f"toolu_{uuid.uuid4().hex[:10]}")
                        tool_name = str(fn_info.get("name") or "tool")
                        tool_buffers[tc_idx] = {"block_index": blk_idx, "id": tool_id, "name": tool_name}
                        yield _format_sse_event("content_block_start", {
                            "type": "content_block_start",
                            "index": blk_idx,
                            "content_block": {"type": "tool_use", "id": tool_id, "name": tool_name, "input": {}},
                        })
                    fn_args_delta = tc.get("function", {}).get("arguments")
                    if fn_args_delta:
                        output_tokens += 1
                        yield _format_sse_event("content_block_delta", {
                            "type": "content_block_delta",
                            "index": tool_buffers[tc_idx]["block_index"],
                            "delta": {"type": "input_json_delta", "partial_json": str(fn_args_delta)},
                        })

        if text_block_started:
            yield _format_sse_event("content_block_stop", {
                "type": "content_block_stop",
                "index": text_block_idx,
            })

        for tb in tool_buffers.values():
            stop_reason = "tool_use"
            yield _format_sse_event("content_block_stop", {
                "type": "content_block_stop",
                "index": tb["block_index"],
            })

        if block_index == 0:
            yield _format_sse_event("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            })
            yield _format_sse_event("content_block_stop", {"type": "content_block_stop", "index": 0})

        yield _format_sse_event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        })
        yield _format_sse_event("message_stop", {"type": "message_stop"})

    return StreamingResponse(
        anthropic_sse_generator(),
        media_type="text/event-stream",
        headers=response_headers,
    )


# ============================================================================
# 3. UNIFIED SOVEREIGN NEXUS HTTP APIs (/v1/sovereign/*)
# ============================================================================

class SovereignAuditRequest(BaseModel):
    action_intent: str = Field(..., description="Intent or claim to audit.")
    payload_or_claim: str = Field("", description="Code, prediction, or prompt payload.")
    estimated_energy_joules: float = Field(12.0, description="Estimated Landauer energy dissipation.")
    telemetry: Optional[Dict[str, Any]] = None
    seal_to_ratchet: bool = False


class SovereignVerifyRequest(BaseModel):
    graph_json: Optional[Dict[str, Any]] = None
    theoretical_expectations: Optional[Dict[str, float]] = None
    empirical_measurements: Optional[Dict[str, float]] = None
    proposed_edge: Optional[List[str]] = None
    constraint_type: str = "boolean_logic_and_kirchhoff"
    run_kuramoto: bool = True


class SovereignJitRequest(BaseModel):
    kernel_name: str = Field(..., description="Registered or newly compiled kernel name.")
    pseudocode: Optional[str] = Field(None, description="Optional ujit pseudocode to compile natively.")
    args: List[int] = Field(default_factory=list, description="64-bit integer arguments.")


class TypemetricSyncRequest(BaseModel):
    phases: List[int] = Field(default_factory=lambda: [0, 768, 1536, 2304])
    omegas: List[int] = Field(default_factory=lambda: [24, 42, 12, 36])
    trits: List[int] = Field(default_factory=lambda: [1, 1, 1, 1])
    precisions: List[int] = Field(default_factory=lambda: [1728, 1152, 864, 864])
    coupling_k: int = 24
    candidate_vectors: Optional[List[List[int]]] = None
    k_centers: Optional[int] = None
    wht_truth_table: Optional[List[int]] = None
    wht_input_bits: int = 0


class DeliberateRequest(BaseModel):
    prompt: str = Field(..., description="Problem statement or engineering prompt.")
    budget_tokens: int = Field(2048, ge=128, le=32768)


@sovereign_router.get("/mesh")
async def get_sovereign_mesh() -> Dict[str, Any]:
    """Returns live unified status across all local/cluster VectorCore & ClothOS services."""
    return get_sovereign_nexus().get_ecosystem_mesh_status(include_http_details=True)


@sovereign_router.post("/audit")
async def run_sovereign_audit(req: SovereignAuditRequest) -> Dict[str, Any]:
    """Runs Constitutional, Epistemic, Fiduciary & Adversarial Deceit Tribunal with Merkle Seal."""
    return get_sovereign_nexus().audit_constitutional_and_deceit(
        action_intent=req.action_intent,
        payload_or_claim=req.payload_or_claim,
        estimated_energy_joules=req.estimated_energy_joules,
        telemetry=req.telemetry,
        seal_to_ratchet=req.seal_to_ratchet,
    )


@sovereign_router.post("/verify")
async def run_sovereign_verify(req: SovereignVerifyRequest) -> Dict[str, Any]:
    """Runs Formal Z3 SMT, Active Inference KL Surprise & Topological Betti/Kuramoto verification."""
    return get_sovereign_nexus().verify_formal_and_topological(
        graph_json=req.graph_json,
        theoretical_expectations=req.theoretical_expectations,
        empirical_measurements=req.empirical_measurements,
        proposed_edge=req.proposed_edge,
        constraint_type=req.constraint_type,
        run_kuramoto=req.run_kuramoto,
    )


@sovereign_router.post("/jit/eval")
async def run_sovereign_jit(req: SovereignJitRequest) -> Dict[str, Any]:
    """Compiles and executes a native x86-64 machine-code kernel via universal-jit."""
    try:
        return get_sovereign_nexus().jit_compile_and_execute(
            kernel_name=req.kernel_name,
            pseudocode=req.pseudocode,
            args=req.args,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@sovereign_router.post("/typemetric/sync")
async def run_typemetric_sync(req: TypemetricSyncRequest) -> Dict[str, Any]:
    """Executes C99-isomorphic Dozenal Kuramoto sync, optional Gonzalez pruning, and WHT eval."""
    sync_res = tm_dozenal_kuramoto_step_batch(
        phases_in=req.phases,
        omegas=req.omegas,
        trit_polarities=req.trits,
        precision_weights_q12=req.precisions,
        coupling_k=req.coupling_k,
    )
    out: Dict[str, Any] = {"dozenal_kuramoto": sync_res}
    if req.candidate_vectors and req.k_centers:
        out["gonzalez_selected_indices"] = tm_gonzalez_select(req.candidate_vectors, k=req.k_centers)
    if req.wht_truth_table:
        out["wht_eval"] = tm_wht_eval(req.wht_truth_table, input_bits=req.wht_input_bits)
    return out


@sovereign_router.post("/deliberate")
async def run_sovereign_deliberate(req: DeliberateRequest) -> Dict[str, Any]:
    """Runs verified multi-trajectory test-time thinking across ClothOS cognitive subsystems."""
    return get_sovereign_nexus().deliberate_with_verification(
        prompt=req.prompt,
        budget_tokens=req.budget_tokens,
    )
