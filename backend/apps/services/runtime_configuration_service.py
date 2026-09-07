"""Persistent, encrypted runtime configuration with environment fallback."""

from __future__ import annotations

import json
import re
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, computed_field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.config import Settings, settings
from apps.models.persistence import RuntimeConfigurationRecord, SystemEventRecord
from apps.security.runtime_secrets import RuntimeMasterKeyMissingError, RuntimeSecretCipher


class RuntimeConfigurationError(RuntimeError):
    """Base class for safe runtime-configuration errors."""


class RuntimeConfigurationValidationError(RuntimeConfigurationError):
    """A namespace, key, or value is outside the bounded configuration format."""


class RuntimeSecretClassificationError(RuntimeConfigurationError):
    """A known sensitive setting was presented as plaintext storage."""


class RuntimeConfigurationValueError(RuntimeConfigurationError):
    """A persisted non-secret value is malformed."""


class RuntimeConfigurationNamespace(StrEnum):
    BEVE = "beve"
    TUYA_CLOUD = "tuya_cloud"
    TUYA_DEVICES = "tuya_devices"
    SYSTEM = "system"


class ConfigurationSource(StrEnum):
    PERSISTED = "persisted"
    ENVIRONMENT = "environment"
    MISSING = "missing"


class ConfigurationFieldMetadata(BaseModel):
    configured: bool
    source: ConfigurationSource
    secret: bool


class NamespaceConfigurationStatus(BaseModel):
    namespace: RuntimeConfigurationNamespace
    configured: bool
    fields: dict[str, ConfigurationFieldMetadata]


class BeveRuntimeConfiguration(BaseModel):
    """Secret-safe resolved BEVE values for internal runtime consumers."""

    model_config = ConfigDict(frozen=True)

    base_url: str
    username: SecretStr | None = None
    password: SecretStr | None = None
    station_id: str | None = None
    device_id: str | None = None
    time_zone: str = "Africa/Lagos"
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    sources: dict[str, ConfigurationSource] = Field(default_factory=dict)

    @computed_field
    @property
    def configured(self) -> bool:
        return all(
            self.sources.get(name) != ConfigurationSource.MISSING
            for name in ("username", "password", "station_id", "device_id")
        )

    @computed_field
    @property
    def missing_fields(self) -> list[str]:
        required = {
            "username": self.username,
            "password": self.password,
            "station_id": self.station_id,
            "device_id": self.device_id,
        }
        return [
            name
            for name in required
            if self.sources.get(name) == ConfigurationSource.MISSING
        ]


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")
_SECRET_TERMS = {
    "access_id",
    "access_secret",
    "api_key",
    "local_key",
    "password",
    "secret",
    "token",
    "username",
}


def is_secret_configuration_key(
    namespace: RuntimeConfigurationNamespace | str,
    key: str,
) -> bool:
    """Classify known credentials centrally, including future device-scoped keys."""

    normalized_namespace = _normalize_namespace(namespace)
    normalized_key = _normalize_key(key)
    segments = set(normalized_key.replace("-", "_").split("."))
    if segments & _SECRET_TERMS:
        return True
    return normalized_namespace == RuntimeConfigurationNamespace.TUYA_DEVICES and (
        normalized_key.endswith("_local_key") or normalized_key.endswith("_secret")
    )


class RuntimeConfigurationService:
    """Read and mutate bounded settings without caching decrypted credentials."""

    def __init__(
        self,
        session: Session,
        *,
        environment: Settings = settings,
        master_key_file: str | None = None,
        clock=None,
    ) -> None:
        self.session = session
        self.environment = environment
        configured_path = environment.runtime_master_key_path
        self.master_key_file = master_key_file or (
            str(configured_path) if configured_path is not None else None
        )
        self.clock = clock

    def get_setting(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
    ) -> Any | None:
        record = self._record(namespace, key)
        if record is None:
            return None
        if record.is_secret:
            return self._cipher().decrypt(record.value)
        try:
            return json.loads(record.value)
        except (json.JSONDecodeError, TypeError):
            raise RuntimeConfigurationValueError(
                "Persisted runtime configuration value is invalid"
            ) from None

    def set_non_secret(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
        value: Any,
        *,
        actor_id: uuid.UUID | str | None = None,
    ) -> RuntimeConfigurationRecord:
        return self._write(namespace, key, value, is_secret=False, actor_id=actor_id)

    def set_secret(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
        value: str | SecretStr,
        *,
        actor_id: uuid.UUID | str | None = None,
    ) -> RuntimeConfigurationRecord:
        return self._write(namespace, key, value, is_secret=True, actor_id=actor_id)

    def delete_setting(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
        *,
        actor_id: uuid.UUID | str | None = None,
    ) -> bool:
        normalized_namespace = _normalize_namespace(namespace)
        normalized_key = _normalize_key(key)
        record = self._record(normalized_namespace, normalized_key)
        if record is None:
            return False
        was_secret = record.is_secret
        self.session.delete(record)
        self._audit(
            normalized_namespace,
            normalized_key,
            "deleted",
            secret=was_secret,
            actor_id=actor_id,
        )
        self.session.flush()
        return True

    def get_namespace_status(
        self,
        namespace: RuntimeConfigurationNamespace | str,
    ) -> NamespaceConfigurationStatus:
        normalized = _normalize_namespace(namespace)
        if normalized == RuntimeConfigurationNamespace.BEVE:
            fields: dict[str, ConfigurationFieldMetadata] = {}
            for key, environment_value in self._beve_environment_values().items():
                record = self._record(normalized, key)
                if record is not None:
                    if is_secret_configuration_key(normalized, key) and not record.is_secret:
                        raise RuntimeSecretClassificationError(
                            "Persisted sensitive runtime configuration is not encrypted"
                        )
                    source = ConfigurationSource.PERSISTED
                else:
                    source = (
                        ConfigurationSource.MISSING
                        if _is_missing(environment_value)
                        else ConfigurationSource.ENVIRONMENT
                    )
                fields[key] = ConfigurationFieldMetadata(
                    configured=source != ConfigurationSource.MISSING,
                    source=source,
                    secret=is_secret_configuration_key(normalized, key),
                )
            return NamespaceConfigurationStatus(
                namespace=normalized,
                configured=all(
                    fields[key].configured
                    for key in ("username", "password", "station_id", "device_id")
                ),
                fields=fields,
            )

        records = self.session.scalars(
            select(RuntimeConfigurationRecord).where(
                RuntimeConfigurationRecord.namespace == normalized.value
            )
        ).all()
        fields = {
            record.key: ConfigurationFieldMetadata(
                configured=True,
                source=ConfigurationSource.PERSISTED,
                secret=record.is_secret,
            )
            for record in records
        }
        return NamespaceConfigurationStatus(
            namespace=normalized,
            configured=bool(fields),
            fields=fields,
        )

    def get_beve_configuration(self) -> BeveRuntimeConfiguration:
        """Resolve each BEVE field persisted-first, then from environment."""

        resolved: dict[str, Any] = {}
        sources: dict[str, ConfigurationSource] = {}
        for key, environment_value in self._beve_environment_values().items():
            record = self._record(RuntimeConfigurationNamespace.BEVE, key)
            if record is not None:
                if is_secret_configuration_key(RuntimeConfigurationNamespace.BEVE, key) and not record.is_secret:
                    raise RuntimeSecretClassificationError(
                        "Persisted sensitive runtime configuration is not encrypted"
                    )
                value = self.get_setting(RuntimeConfigurationNamespace.BEVE, key)
                sources[key] = ConfigurationSource.PERSISTED
            else:
                value = environment_value
                sources[key] = (
                    ConfigurationSource.MISSING
                    if _is_missing(value)
                    else ConfigurationSource.ENVIRONMENT
                )
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if key in {"username", "password"} and value is not None:
                value = SecretStr(str(value))
            resolved[key] = value
        return BeveRuntimeConfiguration(**resolved, sources=sources)

    def _beve_environment_values(self) -> dict[str, Any]:
        return {
            "base_url": self.environment.beve_base_url,
            "username": self.environment.beve_username,
            "password": self.environment.beve_password,
            "station_id": self.environment.beve_station_id,
            "device_id": self.environment.beve_device_id,
            "time_zone": self.environment.beve_time_zone,
            "timeout_seconds": self.environment.beve_timeout_seconds,
        }

    def _write(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
        value: Any,
        *,
        is_secret: bool,
        actor_id: uuid.UUID | str | None,
    ) -> RuntimeConfigurationRecord:
        normalized_namespace = _normalize_namespace(namespace)
        normalized_key = _normalize_key(key)
        classified_secret = is_secret_configuration_key(normalized_namespace, normalized_key)
        if classified_secret and not is_secret:
            raise RuntimeSecretClassificationError(
                "Sensitive runtime configuration must be encrypted"
            )

        if is_secret:
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if not isinstance(value, str):
                raise RuntimeConfigurationValidationError(
                    "Secret runtime configuration must be a string"
                )
            if value == "":
                raise RuntimeConfigurationValidationError(
                    "Secret runtime configuration cannot be empty"
                )
            serialized = self._cipher().encrypt(value)
        else:
            try:
                serialized = json.dumps(value, allow_nan=False, separators=(",", ":"))
            except (TypeError, ValueError):
                raise RuntimeConfigurationValidationError(
                    "Runtime configuration value must be JSON serializable"
                ) from None

        record = self._record(normalized_namespace, normalized_key)
        action = "updated" if record is not None else "created"
        if record is None:
            record = RuntimeConfigurationRecord(
                namespace=normalized_namespace.value,
                key=normalized_key,
                value=serialized,
                is_secret=is_secret,
            )
            self.session.add(record)
        else:
            record.value = serialized
            record.is_secret = is_secret
        self._audit(
            normalized_namespace,
            normalized_key,
            action,
            secret=is_secret,
            actor_id=actor_id,
        )
        self.session.flush()
        return record

    def _record(
        self,
        namespace: RuntimeConfigurationNamespace | str,
        key: str,
    ) -> RuntimeConfigurationRecord | None:
        normalized_namespace = _normalize_namespace(namespace)
        normalized_key = _normalize_key(key)
        return self.session.scalar(
            select(RuntimeConfigurationRecord).where(
                RuntimeConfigurationRecord.namespace == normalized_namespace.value,
                RuntimeConfigurationRecord.key == normalized_key,
            )
        )

    def _cipher(self) -> RuntimeSecretCipher:
        if self.master_key_file is None:
            raise RuntimeMasterKeyMissingError(
                "Runtime configuration master key is not configured"
            )
        return RuntimeSecretCipher(self.master_key_file)

    def _audit(
        self,
        namespace: RuntimeConfigurationNamespace,
        key: str,
        action: str,
        *,
        secret: bool,
        actor_id: uuid.UUID | str | None,
    ) -> None:
        details: dict[str, Any] = {
            "namespace": namespace.value,
            "changed_keys": [key],
            "action": action,
            "secret": secret,
        }
        if actor_id is not None:
            details["actor_id"] = str(actor_id)
        event = SystemEventRecord(
            category="installation.configuration",
            severity="info",
            message=f"{namespace.value} runtime configuration {action}",
            details=details,
        )
        if self.clock is not None:
            event.timestamp = self.clock()
        self.session.add(event)


def _normalize_namespace(
    namespace: RuntimeConfigurationNamespace | str,
) -> RuntimeConfigurationNamespace:
    try:
        return RuntimeConfigurationNamespace(str(namespace).strip().lower())
    except ValueError:
        raise RuntimeConfigurationValidationError(
            "Runtime configuration namespace is not supported"
        ) from None


def _normalize_key(key: str) -> str:
    if not isinstance(key, str):
        raise RuntimeConfigurationValidationError("Runtime configuration key is invalid")
    normalized = key.strip().lower()
    if not _KEY_PATTERN.fullmatch(normalized):
        raise RuntimeConfigurationValidationError("Runtime configuration key is invalid")
    return normalized


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, SecretStr):
        return value.get_secret_value() == ""
    return isinstance(value, str) and value == ""


__all__ = [
    "BeveRuntimeConfiguration",
    "ConfigurationFieldMetadata",
    "ConfigurationSource",
    "NamespaceConfigurationStatus",
    "RuntimeConfigurationError",
    "RuntimeConfigurationNamespace",
    "RuntimeConfigurationService",
    "RuntimeConfigurationValidationError",
    "RuntimeConfigurationValueError",
    "RuntimeSecretClassificationError",
    "is_secret_configuration_key",
]
