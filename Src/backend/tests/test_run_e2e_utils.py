from __future__ import annotations

from app.scripts.run_e2e import Redactor, build_env_fingerprint, sanitize_url_for_snapshot


def test_redactor_masks_tokens_and_headers() -> None:
    redactor = Redactor(["super-secret-token"])
    redactor.register("Bearer abc.def.ghi")
    text = "Authorization: Bearer abc.def.ghi\napi-key: secret_value\nredis://user:pass@host"
    output = redactor.redact_text(text)
    assert "Bearer abc.def.ghi" not in output
    assert "api-key: ***" in output.lower()
    assert "rediss://***@host" in output
    assert "super-secret-token" not in output


def test_env_fingerprint_stable_order(monkeypatch) -> None:
    env = {"ONE": "1", "TWO": "2"}
    with monkeypatch.context() as m:
        m.delenv("ONE", raising=False)
        m.delenv("TWO", raising=False)
        m.setenv("ONE", env["ONE"])
        m.setenv("TWO", env["TWO"])
        hashes = build_env_fingerprint()
    assert hashes == sorted(hashes)
    import hashlib

    expected = {hashlib.sha256(name.encode("utf-8")).hexdigest() for name in env}
    assert expected.issubset(set(hashes))


def test_sanitize_url_for_snapshot_host_only() -> None:
    url = "https://user:password@example.com:12345/path"
    assert sanitize_url_for_snapshot(url, host_only=True) == "example.com:12345"
    assert sanitize_url_for_snapshot(url) == "https://example.com:12345"
