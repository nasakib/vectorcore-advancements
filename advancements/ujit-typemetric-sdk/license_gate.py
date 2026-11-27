"""
Offline Ed25519 Commercial License Gate (Public Key Only).
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

EMBEDDED_PUBLIC_KEY_B64 = "hLhvPayNCqP4tL7o7pxUr/zxeXkdytAAAEAnxdYDrgI="


class LicenseError(PermissionError):
    """Raised when a commercial feature is invoked without a valid signed license."""


def _load_public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(EMBEDDED_PUBLIC_KEY_B64))


def verify_license_file(
    license_path: Optional[str | Path] = None,
    *,
    expected_product: str,
    required_feature: Optional[str] = None,
) -> Dict[str, Any]:
    """Verifies an offline Ed25519 `.lic` file and enforces product/expiry/feature bounds."""
    path = Path(
        license_path
        or os.environ.get("CLOTHOS_LICENSE_FILE")
        or (Path.home() / ".clothos" / "license.lic")
    )
    if not path.exists():
        raise LicenseError(
            f"Commercial license required for '{expected_product}' "
            f"(feature='{required_feature or 'commercial'}'). No license found at {path}."
        )

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        payload = doc["payload"]
        sig = base64.b64decode(doc["signature"])
    except Exception as exc:
        raise LicenseError(f"Malformed license file {path}: {exc}") from exc

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        _load_public_key().verify(sig, canonical)
    except InvalidSignature as exc:
        raise LicenseError("Invalid Ed25519 license signature (tampered or forged key).") from exc

    prod = payload.get("product", "")
    if prod not in (expected_product, "all"):
        raise LicenseError(f"License is for '{prod}', not '{expected_product}'.")

    exp_str = payload.get("expires_at", "")
    exp = dt.datetime.fromisoformat(exp_str)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if dt.datetime.now(dt.timezone.utc) > exp:
        raise LicenseError(f"Commercial license expired on {exp_str}.")

    features = set(payload.get("features", []))
    if required_feature and required_feature not in features:
        raise LicenseError(f"License missing required enterprise feature '{required_feature}'.")

    return payload
