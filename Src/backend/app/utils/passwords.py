"""Password hashing helpers centralised for the North Star backend."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    default="bcrypt_sha256",
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash *password* using bcrypt with per-call salt."""

    if password is None:
        raise ValueError("password must not be None")
    password = str(password)
    if password == "":
        raise ValueError("password must not be empty")
    return _pwd_context.hash(password)


def verify_password(password: str | None, hashed: str | None) -> bool:
    """Verify *password* against *hashed*; returns ``False`` on any error."""

    if not password or not hashed:
        return False
    try:
        return _pwd_context.verify(password, hashed)
    except ValueError:
        return False


def needs_rehash(hashed: str | None) -> bool:
    """Check whether *hashed* should be re-hashed under the current policy."""

    if not hashed:
        return True
    try:
        return _pwd_context.needs_update(hashed)
    except ValueError:
        return True
