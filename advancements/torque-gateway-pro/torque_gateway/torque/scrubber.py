"""
Pure Functional Zero-Trust IP/PII Scrubber and In-Memory Rehydration Vault.

Part of Pillar 1: TORQUE.
Prevents sensitive proprietary intellectual property and confidential credentials
from ever leaking to remote or untrusted cloud providers.

Specifically guards:
- `fouriersLibrary` / `Fourier's Library`
- `VectorForge`
- `Mycos`
- `Gnorbit`
- `BabelForge`
- IPv4 addresses, API keys, emails, Ethereum wallet addresses

Rust Migration Blueprint:
    In the native `loom-core` Rust crate:
    ```rust
    use std::collections::HashMap;
    use regex::Regex;

    pub struct RehydrationVault {
        mapping: HashMap<String, String>,
    }

    impl RehydrationVault {
        pub fn new() -> Self { ... }
        pub fn tokenize_and_store(&mut self, text: &str) -> ScrubbedPayload { ... }
        pub fn rehydrate(&self, scrubbed: &str) -> String { ... }
    }
    ```
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Pattern, Tuple
from loom.config import get_settings
from loom.types import ScrubbedPayload, ScrubberProtocol


class RehydrationVault:
    """Stateful, thread-safe vault mapping synthetic tokens to sensitive source entities."""

    def __init__(self) -> None:
        """Initializes empty vault store."""
        self._store: Dict[str, str] = {}

    def insert(self, token: str, original_entity: str) -> None:
        """Stores a token-to-entity mapping."""
        self._store[token] = original_entity

    def get(self, token: str) -> str:
        """Retrieves the original entity corresponding to the given token."""
        return self._store.get(token, token)

    def snapshot(self) -> Dict[str, str]:
        """Returns an immutable copy of the active vault mapping."""
        return dict(self._store)

    def clear(self) -> None:
        """Wipes the vault memory."""
        self._store.clear()


class TorqueScrubber:
    """Pure functional string replacement engine and entity anonymizer.

    Implements:
        `ScrubberProtocol`
    """

    def __init__(self, vault: RehydrationVault | None = None) -> None:
        """Constructs scrubber with configured proprietary terms and regex patterns."""
        self.settings = get_settings().torque
        self.vault = vault or RehydrationVault()

        # Compile proprietary term patterns with word boundaries and case insensitivity
        self._term_patterns: List[Tuple[str, Pattern]] = []
        for term in self.settings.proprietary_terms:
            escaped = re.escape(term)
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            self._term_patterns.append((term, pattern))

        # Compile PII patterns
        self._pii_patterns: List[Tuple[str, Pattern]] = []
        for tag, pattern_str in self.settings.pii_patterns.items():
            self._pii_patterns.append((tag, re.compile(pattern_str)))

    def tokenize_and_store(self, text: str) -> ScrubbedPayload:
        """Strips proprietary IP terms and PII, replacing them with synthetic tokens.

        Args:
            text: Raw input text from user prompt.

        Returns:
            ScrubbedPayload containing anonymized text and the token lookup dictionary.
        """
        scrubbed = text
        token_map: Dict[str, str] = {}
        counter = 0

        # 1. Anonymize Proprietary IP Terms first
        for term, pattern in self._term_patterns:
            matches = list(pattern.finditer(scrubbed))
            if not matches:
                continue

            # Deterministic synthetic token prefix for term
            safe_term_id = re.sub(r"[^A-Za-z0-9]", "_", term).upper()
            synthetic_token = f"<<IP_{safe_term_id}_{uuid.uuid4().hex[:6]}>>"

            # Replace occurrences
            scrubbed = pattern.sub(synthetic_token, scrubbed)
            token_map[synthetic_token] = term
            self.vault.insert(synthetic_token, term)
            counter += len(matches)

        # 2. Anonymize PII and Secrets
        for tag, pattern in self._pii_patterns:
            matches = list(pattern.finditer(scrubbed))
            for match in matches:
                matched_val = match.group(0)
                # Avoid re-tokenizing an existing synthetic token
                if matched_val.startswith("<<") and matched_val.endswith(">>"):
                    continue
                synthetic_token = f"<<SEC_{tag}_{uuid.uuid4().hex[:6]}>>"
                # Safe precise replacement
                scrubbed = scrubbed.replace(matched_val, synthetic_token)
                token_map[synthetic_token] = matched_val
                self.vault.insert(synthetic_token, matched_val)
                counter += 1

        return ScrubbedPayload(
            original_text=text,
            scrubbed_text=scrubbed,
            replacements_count=counter,
            vault_token_map=token_map,
        )

    def rehydrate(self, scrubbed_text: str, vault_map: Dict[str, str] | None = None) -> str:
        """Restores synthetic tokens with their original real entities.

        Args:
            scrubbed_text: Text emitted from LLM (can be a full response or streaming chunk).
            vault_map: Specific token mapping to use, or falls back to internal vault.

        Returns:
            Rehydrated text with real proprietary names restored.
        """
        mapping = vault_map if vault_map is not None else self.vault.snapshot()
        rehydrated = scrubbed_text
        for token, original in mapping.items():
            if token in rehydrated:
                rehydrated = rehydrated.replace(token, original)
        return rehydrated
