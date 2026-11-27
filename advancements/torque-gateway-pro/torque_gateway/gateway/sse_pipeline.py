"""
Loom Gateway SSE Pipeline: Real-Time Stream Transformer & On-The-Fly Vault Rehydrator.

Part of Pillar 4: LOOM / GATEWAY.
Parses backend Server-Sent Events (SSE) token chunks:
- Normalizes disparate streaming protocols (Ollama, llama.cpp, OpenAI) into standard OpenAI SSE chunks.
- Rehydrates synthetic enclave tokens (`<<ENCLAVE_VAR_N>>`) on the fly before emitting to client.
- Tracks exact Time-To-First-Token (TTFT) and throughput (Tokens-Per-Second).
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, Mapping, Optional
from loom.torque.enclave import TorqueEnclaveScrubber


class SSEStreamTransformer:
    """Transforms raw backend SSE streams and applies zero-loss on-the-fly token rehydration."""

    def __init__(
        self,
        vault_map: Optional[Mapping[str, str]] = None,
        scrubber: Optional[TorqueEnclaveScrubber] = None,
    ) -> None:
        self.vault_map = vault_map or {}
        self.scrubber = scrubber or TorqueEnclaveScrubber()
        self.start_time: float = time.time()
        self.first_token_time: Optional[float] = None
        self.token_count: int = 0

    @property
    def ttft_ms(self) -> float:
        """Returns Time-To-First-Token in milliseconds."""
        if self.first_token_time is None:
            return 0.0
        return round((self.first_token_time - self.start_time) * 1000.0, 2)

    @property
    def tokens_per_sec(self) -> float:
        """Returns total generated tokens per second."""
        elapsed = max(0.001, time.time() - self.start_time)
        return round(self.token_count / elapsed, 2)

    def mark_token(self) -> None:
        """Records arrival of a new generation token."""
        if self.first_token_time is None:
            self.first_token_time = time.time()
        self.token_count += 1

    async def transform_stream(
        self,
        raw_stream: AsyncIterator[str],
        model_name: str,
    ) -> AsyncIterator[str]:
        """Transforms raw streaming chunks and applies on-the-fly rehydration."""
        async for chunk in raw_stream:
            if not chunk or not chunk.strip():
                continue

            cleaned = chunk.strip()
            if cleaned == "data: [DONE]" or cleaned == "[DONE]":
                yield "data: [DONE]\n\n"
                break

            if cleaned.startswith("data: "):
                payload_str = cleaned[6:].strip()
            else:
                payload_str = cleaned

            try:
                data = json.loads(payload_str)
                delta_content = ""

                # OpenAI format
                if "choices" in data and data["choices"]:
                    delta_content = data["choices"][0].get("delta", {}).get("content", "")
                # Ollama format
                elif "message" in data:
                    delta_content = data.get("message", {}).get("content", "")
                elif "response" in data:
                    delta_content = data.get("response", "")

                if delta_content:
                    self.mark_token()

                    # Apply on-the-fly Rehydration if vault has mappings
                    if self.vault_map:
                        delta_content = self.scrubber.rehydrate(delta_content, self.vault_map)

                    chunk_out = {
                        "id": f"chatcmpl-{model_name}",
                        "object": "chat.completion.chunk",
                        "created": int(self.start_time),
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": delta_content},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_out)}\n\n"

            except Exception:
                # If plain text chunk, rehydrate and forward
                if cleaned:
                    self.mark_token()
                    rehydrated = self.scrubber.rehydrate(cleaned, self.vault_map)
                    yield f"data: {rehydrated}\n\n"

        yield "data: [DONE]\n\n"
