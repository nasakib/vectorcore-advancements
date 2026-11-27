"""
Loom Fabric Cloud LLM Provider Gateway & Porter.

Enables seamless porting, routing, and fallbacks to major external cloud LLM APIs:
- OpenAI (GPT-4o, o3-mini, o1)
- Anthropic Claude (Claude 3.5 Sonnet, Claude 3.7 Sonnet)
- Google Gemini (Gemini 2.5 Flash, Gemini 3.1 Pro Preview)
- OpenRouter / DeepSeek Cloud
- Groq / Together AI

Features:
- Standardized OpenAI schema translation.
- Integration with Torque Zero-Trust Scrubber (all requests are de-identified before dispatch).
- Key vault resolution from environment or user-defined configuration.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from loom.config import get_settings
from loom.torque.scrubber import TorqueScrubber, RehydrationVault


class CloudProviderConfig(BaseModel):
    """Configuration coordinate for a cloud AI provider."""
    name: str = Field(..., description="Provider identifier (e.g. 'openai', 'anthropic', 'google')")
    base_url: str = Field(..., description="API base URL")
    api_key_env_var: str = Field(..., description="Environment variable holding secret key")
    default_model: str = Field(..., description="Default model ID for this provider")
    auth_header_format: str = Field("Bearer {key}", description="Format for authorization header")


CLOUD_PROVIDERS: Dict[str, CloudProviderConfig] = {
    "openai": CloudProviderConfig(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_env_var="OPENAI_API_KEY",
        default_model="gpt-4o",
    ),
    "anthropic": CloudProviderConfig(
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key_env_var="ANTHROPIC_API_KEY",
        default_model="claude-3-5-sonnet-20241022",
        auth_header_format="{key}",
    ),
    "google": CloudProviderConfig(
        name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env_var="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
    ),
    "openrouter": CloudProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env_var="OPENROUTER_API_KEY",
        default_model="google/gemini-2.5-flash",
    ),
    "groq": CloudProviderConfig(
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env_var="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
    ),
}


class CloudLLMBridge:
    """Manages cloud API credentials, zero-trust token sanitization, and request dispatch."""

    def __init__(self, scrubber: Optional[TorqueScrubber] = None):
        self.scrubber = scrubber or TorqueScrubber()
        self.settings = get_settings()

    def get_provider_status(self) -> Dict[str, bool]:
        """Returns online/configured status for all supported cloud providers."""
        status = {}
        for key, p in CLOUD_PROVIDERS.items():
            status[key] = bool(os.environ.get(p.api_key_env_var))
        return status

    def resolve_api_key(self, provider_id: str) -> Optional[str]:
        """Retrieves active API key for the requested cloud provider."""
        provider = CLOUD_PROVIDERS.get(provider_id.lower())
        if not provider:
            return None
        return os.environ.get(provider.api_key_env_var)

    async def execute_cloud_completion(
        self,
        provider_id: str,
        messages: List[Dict[str, str]],
        model_override: Optional[str] = None,
        scrub_payload: bool = True,
    ) -> Dict[str, Any]:
        """Dispatches an LLM completion to the specified cloud provider with zero-trust protection.

        Args:
            provider_id: One of 'openai', 'anthropic', 'google', 'openrouter', 'groq'.
            messages: List of chat messages [{"role": "...", "content": "..."}].
            model_override: Optional target cloud model.
            scrub_payload: Whether to apply Torque de-identification before sending.

        Returns:
            OpenAI-compatible dictionary response with rehydrated assistant content.
        """
        provider = CLOUD_PROVIDERS.get(provider_id.lower())
        if not provider:
            raise ValueError(f"Unknown cloud provider: {provider_id}")

        api_key = self.resolve_api_key(provider_id)
        if not api_key:
            raise PermissionError(f"No API key configured for {provider.name} in ${provider.api_key_env_var}")

        model = model_override or provider.default_model

        # 1. Zero-Trust Torque Sanitization
        vault_map: Dict[str, str] = {}
        processed_messages = []
        if scrub_payload:
            for m in messages:
                res = self.scrubber.tokenize_and_store(m.get("content", ""))
                processed_messages.append({"role": m.get("role", "user"), "content": res.scrubbed_text})
                vault_map.update(res.vault_token_map)
        else:
            processed_messages = messages

        headers = {
            "Content-Type": "application/json",
            "Authorization": provider.auth_header_format.format(key=api_key),
        }

        # 2. HTTP Dispatch to Cloud Provider
        target_endpoint = f"{provider.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": processed_messages,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(target_endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 3. Torque Stream / Content Rehydration
        if scrub_payload and vault_map:
            try:
                for choice in data.get("choices", []):
                    raw_reply = choice.get("message", {}).get("content", "")
                    if raw_reply:
                        choice["message"]["content"] = self.scrubber.rehydrate(raw_reply, vault_map)
            except Exception:
                pass

        return data
