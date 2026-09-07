"""Authenticated encryption for persisted runtime secrets."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class RuntimeSecretError(RuntimeError):
    """Base class for sanitized runtime-secret failures."""


class RuntimeMasterKeyMissingError(RuntimeSecretError):
    """The configured key file does not exist."""


class RuntimeMasterKeyMalformedError(RuntimeSecretError):
    """The configured key file does not contain a valid Fernet key."""


class InvalidRuntimeCiphertextError(RuntimeSecretError):
    """A persisted secret cannot be authenticated or decrypted."""


class RuntimeSecretCipher:
    """Load an external Fernet key and encrypt/decrypt individual values."""

    def __init__(self, key_file: Path | str) -> None:
        self._fernet = Fernet(self._load_key(Path(key_file)))

    @staticmethod
    def _load_key(path: Path) -> bytes:
        try:
            key = path.read_bytes().strip()
        except FileNotFoundError:
            raise RuntimeMasterKeyMissingError(
                "Runtime configuration master key is missing"
            ) from None
        except OSError:
            raise RuntimeMasterKeyMissingError(
                "Runtime configuration master key cannot be read"
            ) from None
        try:
            Fernet(key)
        except (TypeError, ValueError):
            raise RuntimeMasterKeyMalformedError(
                "Runtime configuration master key is malformed"
            ) from None
        return key

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            raise TypeError("Runtime secrets must be strings")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError, ValueError):
            raise InvalidRuntimeCiphertextError(
                "Persisted runtime secret is invalid or cannot be decrypted"
            ) from None


def initialize_runtime_master_key(path: Path | str) -> bool:
    """Create a Fernet key atomically with mode 0600; never replace a key."""

    destination = Path(path)
    if destination.exists():
        RuntimeSecretCipher(destination)
        return False

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError:
        RuntimeSecretCipher(destination)
        return False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(Fernet.generate_key())
            stream.write(b"\n")
        os.chmod(destination, 0o600)
    except Exception:
        # The exclusive file may be incomplete. Remove only this exact file so
        # a later explicit retry is possible; no pre-existing key is touched.
        try:
            destination.unlink()
        except OSError:
            pass
        raise
    return True
