from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from app.application.ingestion_service import extract_text


def _make_zip(contents: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, text in contents.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def test_extract_text_supports_zip_archive() -> None:
    payload = _make_zip({"docs/one.md": "Alpha", "two.txt": "Beta"})

    text = extract_text(payload, "bundle.zip")

    assert "Alpha" in text and "Beta" in text
    assert "# File: docs/one.md" in text


def test_extract_text_supports_xip_archive_alias() -> None:
    payload = _make_zip({"readme.md": "Gamma"})

    text = extract_text(payload, "bundle.xip")

    assert "Gamma" in text


def test_extract_text_archive_without_readable_documents() -> None:
    payload = _make_zip({"image.bin": "\x00\x01"})

    with pytest.raises(HTTPException) as exc:
        extract_text(payload, "bundle.zip")

    assert exc.value.status_code == 422
    assert "readable" in str(exc.value.detail).lower()
