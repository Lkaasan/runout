import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import Settings, settings
from app.services import musickit_token
from app.services.musickit_token import (
    LIFETIME_S,
    MusicKitNotConfigured,
    get_developer_token,
)


@pytest.fixture(autouse=True)
def fresh_cache():
    musickit_token.clear_cache()
    yield
    musickit_token.clear_cache()


@pytest.fixture
def key_pair(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "AuthKey_TEST.p8"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key.public_key(), path


def configured(path) -> Settings:
    return Settings(
        apple_team_id="TEAM123456",
        apple_key_id="KEY1234567",
        apple_private_key_path=path,
        web_origin="http://localhost:3000",
        _env_file=None,
    )


def test_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "apple_team_id", "")
    r = client.get("/musickit/developer-token")
    assert r.status_code == 503
    assert "APPLE_TEAM_ID" in r.json()["detail"]


def test_token_has_apple_header_and_claims(key_pair):
    public, path = key_pair
    t = get_developer_token(configured(path), now=1_000_000)
    assert jwt.get_unverified_header(t.token) == {"alg": "ES256", "kid": "KEY1234567", "typ": "JWT"}
    claims = jwt.decode(t.token, public, algorithms=["ES256"], options={"verify_exp": False})
    assert claims["iss"] == "TEAM123456"
    assert claims["iat"] == 1_000_000
    assert claims["exp"] == t.expires_at == 1_000_000 + LIFETIME_S
    assert claims["origin"] == ["http://localhost:3000"]
    assert LIFETIME_S <= 15_777_000  # Apple's 6 month maximum


def test_token_is_cached_then_reminted_before_expiry(key_pair):
    _, path = key_pair
    s = configured(path)
    first = get_developer_token(s, now=1_000_000)
    assert get_developer_token(s, now=1_000_500) is first
    later = get_developer_token(s, now=first.expires_at - 60)
    assert later is not first
    assert later.expires_at > first.expires_at


def test_missing_key_file_is_not_configured(tmp_path):
    with pytest.raises(MusicKitNotConfigured):
        get_developer_token(configured(tmp_path / "missing.p8"), now=1)


def test_endpoint_returns_token(client, key_pair, monkeypatch):
    public, path = key_pair
    monkeypatch.setattr(settings, "apple_team_id", "TEAM123456")
    monkeypatch.setattr(settings, "apple_key_id", "KEY1234567")
    monkeypatch.setattr(settings, "apple_private_key_path", path)
    r = client.get("/musickit/developer-token")
    assert r.status_code == 200
    body = r.json()
    assert jwt.decode(body["token"], public, algorithms=["ES256"])["iss"] == "TEAM123456"
    assert body["expires_at"] > 0
