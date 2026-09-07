"""External runtime master-key and authenticated-encryption tests."""

from __future__ import annotations

import stat
from types import SimpleNamespace

import pytest

from apps.security.runtime_secrets import (
    InvalidRuntimeCiphertextError,
    RuntimeMasterKeyMalformedError,
    RuntimeMasterKeyMissingError,
    RuntimeSecretCipher,
    initialize_runtime_master_key,
)


def test_key_initialization_is_restrictive_and_never_overwrites(tmp_path) -> None:
    key_file = tmp_path / "private" / "master.key"

    assert initialize_runtime_master_key(key_file) is True
    first_bytes = key_file.read_bytes()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600

    assert initialize_runtime_master_key(key_file) is False
    assert key_file.read_bytes() == first_bytes


def test_encrypt_decrypt_roundtrip_and_ciphertext_differs(tmp_path) -> None:
    key_file = tmp_path / "master.key"
    initialize_runtime_master_key(key_file)
    cipher = RuntimeSecretCipher(key_file)

    ciphertext = cipher.encrypt("dummy-secret")

    assert ciphertext != "dummy-secret"
    assert cipher.decrypt(ciphertext) == "dummy-secret"


def test_wrong_key_and_corrupted_ciphertext_fail_safely(tmp_path) -> None:
    first = tmp_path / "first.key"
    second = tmp_path / "second.key"
    initialize_runtime_master_key(first)
    initialize_runtime_master_key(second)
    ciphertext = RuntimeSecretCipher(first).encrypt("dummy-secret")

    with pytest.raises(InvalidRuntimeCiphertextError, match="invalid") as wrong:
        RuntimeSecretCipher(second).decrypt(ciphertext)
    with pytest.raises(InvalidRuntimeCiphertextError, match="invalid") as corrupt:
        RuntimeSecretCipher(first).decrypt(ciphertext[:-4] + "xxxx")

    assert "dummy-secret" not in str(wrong.value)
    assert ciphertext not in str(wrong.value)
    assert ciphertext not in str(corrupt.value)


def test_missing_and_malformed_key_are_distinct_safe_errors(tmp_path) -> None:
    missing = tmp_path / "missing.key"
    with pytest.raises(RuntimeMasterKeyMissingError, match="missing"):
        RuntimeSecretCipher(missing)

    malformed = tmp_path / "malformed.key"
    malformed.write_text("not-a-valid-key", encoding="utf-8")
    with pytest.raises(RuntimeMasterKeyMalformedError, match="malformed") as error:
        RuntimeSecretCipher(malformed)
    assert "not-a-valid-key" not in str(error.value)


def test_key_cli_prints_only_path_and_safe_status(tmp_path, monkeypatch, capsys) -> None:
    from apps.scripts import initialize_runtime_key

    key_file = tmp_path / "runtime-key"
    monkeypatch.setattr(
        initialize_runtime_key,
        "settings",
        SimpleNamespace(runtime_master_key_path=key_file),
    )

    assert initialize_runtime_key.main() == 0
    created_output = capsys.readouterr().out
    stored_key = key_file.read_text(encoding="ascii").strip()
    assert "created" in created_output
    assert str(key_file) in created_output
    assert stored_key not in created_output

    assert initialize_runtime_key.main() == 0
    existing_output = capsys.readouterr().out
    assert "already exists" in existing_output
    assert stored_key not in existing_output


def test_key_cli_rejects_unconfigured_and_invalid_existing_key(
    tmp_path, monkeypatch, capsys
) -> None:
    from apps.scripts import initialize_runtime_key

    monkeypatch.setattr(
        initialize_runtime_key,
        "settings",
        SimpleNamespace(runtime_master_key_path=None),
    )
    assert initialize_runtime_key.main() == 1
    assert "not configured" in capsys.readouterr().out

    invalid = tmp_path / "master.key"
    invalid.write_text("invalid", encoding="utf-8")
    monkeypatch.setattr(
        initialize_runtime_key,
        "settings",
        SimpleNamespace(runtime_master_key_path=invalid),
    )
    assert initialize_runtime_key.main() == 1
    output = capsys.readouterr().out
    assert "malformed" in output
    assert "invalid" not in output
