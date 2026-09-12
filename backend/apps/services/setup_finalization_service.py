"""Local-only setup finalization preflight and safe failure normalization."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.orm import Session

from apps.integrations.inverter import BeveConfig
from apps.integrations.tuya.client import TuyaConfigurationError
from apps.integrations.tuya.device_loader import parse_breaker_configs
from apps.models.persistence import SystemEventRecord
from apps.schemas.setup import SetupCompletionErrorCategory
from apps.security.runtime_secrets import (
    InvalidRuntimeCiphertextError,
    RuntimeMasterKeyMalformedError,
    RuntimeMasterKeyMissingError,
    RuntimeSecretCipher,
    RuntimeSecretError,
)
from apps.services.runtime_configuration_service import (
    ConfigurationSource,
    RuntimeConfigurationError,
    RuntimeConfigurationService,
)
from apps.services.setup_service import SetupService


_MESSAGES: dict[SetupCompletionErrorCategory, str] = {
    "configuration_incomplete": "All setup stages must be completed before finalization.",
    "master_key_unavailable": "The runtime configuration master key is unavailable or invalid.",
    "beve_configuration_invalid": "The saved inverter configuration could not be validated. Review the inverter setup before finalizing.",
    "tuya_configuration_invalid": "The saved smart-breaker configuration could not be validated. Review the breaker setup before finalizing.",
    "runtime_configuration_invalid": "The saved runtime configuration could not be validated.",
}


class SetupPreflightError(RuntimeError):
    """Secret-safe finalization failure with an API-stable category."""

    def __init__(self, category: SetupCompletionErrorCategory) -> None:
        self.category = category
        super().__init__(_MESSAGES[category])


class SetupFinalizationService:
    """Validate persisted configuration locally, then permanently close setup."""

    def __init__(
        self,
        session: Session,
        runtime_configuration: RuntimeConfigurationService,
    ) -> None:
        self.session = session
        self.runtime_configuration = runtime_configuration

    def complete(self, setup_code: str):
        try:
            return SetupService(self.session).complete(
                setup_code,
                preflight=self.preflight,
            )
        except SetupPreflightError as exc:
            self.session.rollback()
            self.session.add(SystemEventRecord(
                category="installation.setup",
                severity="warning",
                message="Setup finalization preflight failed",
                details={"category": exc.category},
            ))
            self.session.commit()
            raise

    def preflight(self) -> None:
        """Resolve/decrypt typed persisted values without any hardware I/O."""

        master_key = self.runtime_configuration.master_key_file
        if master_key is None:
            raise SetupPreflightError("master_key_unavailable")
        try:
            RuntimeSecretCipher(master_key)
        except (RuntimeMasterKeyMissingError, RuntimeMasterKeyMalformedError):
            raise SetupPreflightError("master_key_unavailable") from None

        try:
            beve = self.runtime_configuration.get_beve_configuration()
            required = ("username", "password", "station_id", "device_id")
            if not beve.configured or any(
                beve.sources.get(field) != ConfigurationSource.PERSISTED
                for field in required
            ):
                raise SetupPreflightError("beve_configuration_invalid")
            BeveConfig(
                base_url=beve.base_url,
                username=beve.username,
                password=beve.password,
                station_id=beve.station_id,
                device_id=beve.device_id,
                time_zone=beve.time_zone,
                timeout_seconds=beve.timeout_seconds,
            )
        except SetupPreflightError:
            raise
        except (InvalidRuntimeCiphertextError, RuntimeConfigurationError, RuntimeSecretError, ValidationError, ValueError, TypeError):
            raise SetupPreflightError("beve_configuration_invalid") from None

        try:
            document = self.runtime_configuration.get_tuya_device_configuration()
            if not document:
                raise SetupPreflightError("tuya_configuration_invalid")
            breakers = parse_breaker_configs(
                document,
                require_supported_metadata=False,
                strict=True,
            )
            if not breakers or not any(item.enabled for item in breakers):
                raise SetupPreflightError("tuya_configuration_invalid")
        except SetupPreflightError:
            raise
        except (InvalidRuntimeCiphertextError, RuntimeConfigurationError, RuntimeSecretError, TuyaConfigurationError, ValidationError, ValueError, TypeError):
            raise SetupPreflightError("tuya_configuration_invalid") from None
