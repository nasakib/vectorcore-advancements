"""Latency, Throughput, and Token Telemetry Metrics Engine.

Calculates generation performance benchmarks including Time-To-First-Token (TTFT),
Tokens-Per-Second (TPS), and layer sharding telemetry for OpenAI-compatible headers.

Architecture Note (Rust Migration Target):
    Maps to `loom_gateway::metrics` in Rust:
    - High-resolution monotonic timers via `std::time::Instant`.
    - Zero-allocation header formatting.
"""

from __future__ import annotations

import time
from typing import Dict, Optional
from pydantic import BaseModel, Field


class CompletionTelemetry(BaseModel):
    """Runtime telemetry recorded across a single generation turn."""

    start_time: float = Field(default_factory=time.perf_counter)
    first_token_time: Optional[float] = Field(default=None)
    end_time: Optional[float] = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    sharding_descriptor: str = Field(default="Unsharded")

    def mark_first_token(self) -> None:
        """Records the timestamp of the first emitted token chunk."""
        if self.first_token_time is None:
            self.first_token_time = time.perf_counter()

    def mark_completed(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Finalizes the turn metrics with exact token counts."""
        self.end_time = time.perf_counter()
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def get_ttft_ms(self) -> float:
        """Returns Time-To-First-Token in milliseconds."""
        if self.first_token_time is None:
            return 0.0
        return round((self.first_token_time - self.start_time) * 1000.0, 2)

    def get_tokens_per_second(self) -> float:
        """Returns decoding throughput in tokens per second."""
        if self.end_time is None or self.first_token_time is None or self.completion_tokens <= 1:
            return 0.0
        decode_duration = self.end_time - self.first_token_time
        if decode_duration <= 0.0001:
            return 0.0
        return round(float(self.completion_tokens - 1) / decode_duration, 2)

    def export_http_headers(self) -> Dict[str, str]:
        """Constructs response headers for the OpenAI gateway endpoint."""
        return {
            "X-Loom-Provider": "Ray-Stitch-Fabric",
            "X-Loom-Tokens-Per-Sec": str(self.get_tokens_per_second()),
            "X-Loom-TTFT-Ms": str(self.get_ttft_ms()),
            "X-Loom-Sharding": self.sharding_descriptor,
        }
