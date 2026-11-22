"""Mints and caches the MusicKit developer token (ES256 JWT).

Format per Apple's "Generating Developer Tokens": header {alg: ES256, kid}, claims
{iss: team id, iat, exp, origin?}, exp at most 15777000 s (6 months) after now.
"""

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import jwt

from app.config import Settings

# Apple's maximum is 15777000 s; stay well inside it and re-mint a day before expiry.
LIFETIME_S = 60 * 60 * 24 * 30
REFRESH_BEFORE_S = 60 * 60 * 24


class MusicKitNotConfigured(RuntimeError):
    """The Apple team id, key id or private key path is missing."""


@dataclass(frozen=True)
class DeveloperToken:
    token: str
    expires_at: int


_lock = threading.Lock()
_cached: tuple[tuple[str, str, str, str], DeveloperToken] | None = None


def _mint(settings: Settings, now: int) -> DeveloperToken:
    if not (
        settings.apple_team_id and settings.apple_key_id and settings.apple_private_key_path
    ):
        raise MusicKitNotConfigured(
            "Set APPLE_TEAM_ID, APPLE_KEY_ID and APPLE_PRIVATE_KEY_PATH to enable Apple Music."
        )
    key = Path(settings.apple_private_key_path)
    if not key.is_file():
        raise MusicKitNotConfigured(f"APPLE_PRIVATE_KEY_PATH does not point to a file: {key}")
    exp = now + LIFETIME_S
    token = jwt.encode(
        {"iss": settings.apple_team_id, "iat": now, "exp": exp, "origin": [settings.web_origin]},
        key.read_text(),
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )
    return DeveloperToken(token=token, expires_at=exp)


def get_developer_token(settings: Settings, now: int | None = None) -> DeveloperToken:
    """Return a cached token, minting a new one shortly before the old one expires."""
    global _cached
    now = int(time.time()) if now is None else now
    ident = (
        settings.apple_team_id,
        settings.apple_key_id,
        str(settings.apple_private_key_path),
        settings.web_origin,
    )
    with _lock:
        if _cached and _cached[0] == ident and _cached[1].expires_at - REFRESH_BEFORE_S > now:
            return _cached[1]
        fresh = _mint(settings, now)
        _cached = (ident, fresh)
        return fresh


def clear_cache() -> None:
    global _cached
    with _lock:
        _cached = None
