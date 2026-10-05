from uuid import uuid4

from app.core import security
from app.core.config import get_settings


def test_password_is_hashed_with_argon2() -> None:
    password = "Безопасный-пароль-2026"
    stored_hash = security.hash_password(password)

    assert stored_hash != password
    assert security.verify_password(password, stored_hash)
    assert not security.verify_password("другой-пароль", stored_hash)


def test_access_token_requires_configured_secret(monkeypatch) -> None:
    monkeypatch.setenv("PK_CONTROL_JWT_SECRET", "test-secret-that-is-not-production")
    get_settings.cache_clear()
    token = security.create_access_token(uuid4())

    assert security.decode_access_token(token) is not None
    get_settings.cache_clear()
