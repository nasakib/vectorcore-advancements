"""
Torque Sovereign Enclave: Zero-Trust Scrubber, Rehydration Vault & Egress Firewall.

Part of Pillar 1: TORQUE.
Enforces zero-trust data protection across local and cloud boundaries:
- Replaces Protected IP Entities and PII with session-scoped synthetic tokens (`<<ENCLAVE_VAR_N>>`).
- Stores bidirectional translation mappings in an in-memory `RehydrationVault`.
- Rehydrates streaming token chunks on the fly before delivery to the client.
- Strict `EgressFirewall` drops any outbound frame matching protected IP assets.
"""

from __future__ import annotations

import re
import threading
from typing import Dict, List, Mapping, Optional, Pattern, Tuple
from loom.config import get_settings
from loom.types import (
    EgressFirewallProtocol,
    SanitizedPayload,
    ScrubbedPayload,
    ScrubberProtocol,
    VaultProtocol,
)


class SecurityEgressViolation(PermissionError):
    """Raised when the Egress Firewall detects prohibited sovereign IP in an outbound payload."""
    pass


# Compatibility alias for existing callers
EgressViolationError = SecurityEgressViolation


class RehydrationVault:
    """Thread-safe, ephemeral in-memory vault mapping synthetic tokens to sovereign entities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._forward: Dict[str, str] = {}  # {synthetic_tag: original_text}
        self._reverse: Dict[str, str] = {}  # {original_text: synthetic_tag}
        self._counter: int = 0

    def get_or_create_token(self, original_value: str) -> str:
        """Returns existing synthetic tag for original_value or registers a new one."""
        with self._lock:
            if original_value in self._reverse:
                return self._reverse[original_value]

            self._counter += 1
            token = f"<<ENCLAVE_VAR_{self._counter}>>"
            self._forward[token] = original_value
            self._reverse[original_value] = token
            return token

    def resolve(self, token: str) -> Optional[str]:
        """Resolves synthetic token back to original sovereign entity."""
        with self._lock:
            return self._forward.get(token)

    def snapshot(self) -> Dict[str, str]:
        """Returns an immutable copy of the active token map."""
        with self._lock:
            return dict(self._forward)

    def clear(self) -> None:
        """Flushes the active vault."""
        with self._lock:
            self._forward.clear()
            self._reverse.clear()
            self._counter = 0


class TorqueEnclaveScrubber(ScrubberProtocol):
    """Cryptographic pattern scrubber implementing `ScrubberProtocol`."""

    def __init__(self, vault: Optional[RehydrationVault] = None) -> None:
        self.settings = get_settings()
        self.vault = vault or RehydrationVault()

        # Compile Protected IP Entities regexes
        self.protected_entities = list(self.settings.torque.proprietary_terms)
        escaped_terms = [re.escape(term) for term in self.protected_entities]
        self._ip_pattern: Pattern[str] = re.compile(
            rf"\b({'|'.join(escaped_terms)})\b",
            re.IGNORECASE,
        )

        # Compile PII patterns
        self._pii_patterns: List[Tuple[str, Pattern[str]]] = [
            (label, re.compile(pattern, re.IGNORECASE))
            for label, pattern in self.settings.torque.pii_patterns.items()
        ]

    def tokenize_and_store(self, text: str) -> ScrubbedPayload:
        """Scrubs all protected IP and sensitive PII from text into synthetic vault tokens."""
        if not text:
            return ScrubbedPayload(
                original_text="",
                scrubbed_text="",
                replacements_count=0,
                vault_token_map={},
                contains_protected_ip=False,
            )

        token_map: Dict[str, str] = {}
        scrubbed = text
        replacements = 0
        detected_ip = False

        # 1. Scrub Protected IP Entities
        matches = list(self._ip_pattern.finditer(scrubbed))
        if matches:
            detected_ip = True
            for match in sorted(matches, key=lambda m: len(m.group()), reverse=True):
                original_entity = match.group()
                token = self.vault.get_or_create_token(original_entity)
                token_map[token] = original_entity
                # Replace occurrences safely
                scrubbed = re.sub(re.escape(original_entity), token, scrubbed)
                replacements += 1

        # 2. Scrub PII and Secrets
        for label, pattern in self._pii_patterns:
            pii_matches = list(pattern.finditer(scrubbed))
            for match in pii_matches:
                secret_value = match.group()
                # Skip if already a synthetic token
                if secret_value.startswith("<<ENCLAVE_VAR_") and secret_value.endswith(">>"):
                    continue
                token = self.vault.get_or_create_token(secret_value)
                token_map[token] = secret_value
                scrubbed = scrubbed.replace(secret_value, token)
                replacements += 1

        return ScrubbedPayload(
            original_text=text,
            scrubbed_text=scrubbed,
            replacements_count=replacements,
            vault_token_map=token_map,
            contains_protected_ip=detected_ip,
        )

    def sanitize(self, text: str) -> SanitizedPayload:
        """Scrubs protected IP and sensitive PII returning immutable SanitizedPayload."""
        res = self.tokenize_and_store(text)
        return SanitizedPayload(
            original_text=res.original_text,
            sanitized_text=res.scrubbed_text,
            replacements_count=res.replacements_count,
            vault_token_map=res.vault_token_map,
            contains_protected_ip=res.contains_protected_ip,
            is_scrubbed=res.replacements_count > 0,
        )

    def scrub(self, text: str) -> SanitizedPayload:
        """Alias for sanitize() returning immutable SanitizedPayload."""
        return self.sanitize(text)

    def scrub_outbound(self, text: str) -> SanitizedPayload:
        """Scrubs outbound text or telemetry before leaving the Torque Enclave."""
        return self.sanitize(text)

    def rehydrate(self, scrubbed_text: str, vault_map: Optional[Mapping[str, str]] = None) -> str:
        """Restores synthetic tokens back to original sovereign entities."""
        if not scrubbed_text:
            return ""

        mapping = vault_map if vault_map is not None else self.vault.snapshot()
        if not mapping:
            return scrubbed_text

        result = scrubbed_text
        for token, original in mapping.items():
            if token in result:
                result = result.replace(token, original)
        return result


class Rehydrator:
    """Reverse mapping to replace synthetic tokens with original entities for local delivery."""

    def __init__(self, vault: Optional[RehydrationVault] = None) -> None:
        self.vault = vault

    def rehydrate(self, scrubbed_text: str, vault_map: Optional[Mapping[str, str]] = None) -> str:
        """Restores synthetic tokens back to original entities."""
        if not scrubbed_text:
            return ""

        mapping = vault_map if vault_map is not None else (self.vault.snapshot() if self.vault else {})
        if not mapping:
            return scrubbed_text

        result = scrubbed_text
        for token, original in mapping.items():
            if token in result:
                result = result.replace(token, original)
        return result


# Core class aliases matching architectural directives
Scrubber = TorqueEnclaveScrubber
TorqueEnclave = TorqueEnclaveScrubber


class EgressFirewall(EgressFirewallProtocol):
    """Enforces zero-egress policy for sovereign IP entities directed to external networks."""

    def __init__(self, protected_terms: Optional[List[str]] = None) -> None:
        self.settings = get_settings()
        self.protected_terms = protected_terms or list(self.settings.torque.proprietary_terms)

    def inspect_outbound_payload(self, destination_url: str, payload_text: str) -> bool:
        """Inspects outbound payload. Returns True if permitted, or drops/raises on violation."""
        lower_url = destination_url.lower()

        # Local cluster traffic is always permitted
        is_local = (
            "127.0.0.1" in lower_url
            or "localhost" in lower_url
            or "192.168.99." in lower_url
            or "100.100.99." in lower_url
        )
        if is_local:
            return True

        # External destination: verify zero unscrubbed protected IP assets
        for term in self.protected_terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            if pattern.search(payload_text):
                raise EgressViolationError(
                    f"Egress Firewall Dropped Packet: Outbound transmission to '{destination_url}' "
                    f"contains unscrubbed Protected IP Entity '{term}'."
                )

        return True


class Enclave:
    """Zero-Trust Enclave namespace facade exposing core components."""
    Vault = RehydrationVault
    RehydrationVault = RehydrationVault
    Scrubber = TorqueEnclaveScrubber
    TorqueEnclaveScrubber = TorqueEnclaveScrubber
    EgressFirewall = EgressFirewall
    Rehydrator = Rehydrator
    SecurityEgressViolation = SecurityEgressViolation
    EgressViolationError = SecurityEgressViolation
