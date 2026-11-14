"""Device tokens are stored as SHA-256 hashes."""

from __future__ import annotations

import hashlib
import hmac


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def keys_match(presented: str, expected: str) -> bool:
    return hmac.compare_digest(presented, expected)
