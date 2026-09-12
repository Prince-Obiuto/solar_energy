"""Token-authorized BEVE setup using the production read-only integration."""

from __future__ import annotations

import threading
from collections.abc import Callable

from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

from apps.core.config import Settings, settings
from apps.integrations.inverter import (
    BeveAuthenticationError,
    BeveClient,
    BeveCloudError,
    BeveConfig,
    BeveConfigurationError,
    BeveConnectionError,
    BeveDeviceNotFoundError,
    BeveIncompleteResponseError,
    BeveIntegrationError,
    BeveMalformedResponseError,
    BeveMappingError,
    BeveTimeoutError,
    InverterAdapter,
)
from apps.models.persistence import SystemEventRecord
from apps.schemas.setup import (
    BeveConfigurationResponse,
    BeveSetupErrorCategory,
    BeveSetupRequest,
    BeveVerificationResult,
    BeveVerificationSummary,
)
from apps.security.runtime_secrets import RuntimeSecretError
from apps.services.runtime_configuration_service import (
    BeveRuntimeConfiguration,
    RuntimeConfigurationError,
    RuntimeConfigurationService,
)
from apps.services.setup_service import SetupService


BeveClientFactory = Callable[[BeveConfig], object]
_BEVE_CONFIGURATION_LOCK = threading.Lock()

_ERROR_MESSAGES: dict[BeveSetupErrorCategory, str] = {
    "authentication_failed": "BEVE authentication failed.",
    "device_not_found": "The configured inverter device could not be found.",
    "network_error": "The BEVE cloud service is unreachable.",
    "timeout": "The BEVE cloud request timed out.",
    "malformed_response": "BEVE responded, but the inverter telemetry could not be validated.",
    "configuration_invalid": "The BEVE configuration could not be validated.",
    "vendor_error": "The BEVE cloud service returned an error.",
}


class _PersistedVerificationFailed(RuntimeError):
    def __init__(self, result: BeveVerificationResult) -> None:
        self.result = result


class BeveSetupService:
    """Verify candidates, persist encrypted credentials, and advance setup state."""

    def __init__(
        self,
        session: Session,
        runtime_configuration: RuntimeConfigurationService,
        *,
        client_factory: BeveClientFactory = BeveClient,
        environment: Settings = settings,
        adapter: InverterAdapter | None = None,
    ) -> None:
        self.session = session
        self.runtime_configuration = runtime_configuration
        self.client_factory = client_factory
        self.environment = environment
        self.adapter = adapter or InverterAdapter()

    def test_configuration(self, payload: BeveSetupRequest) -> BeveVerificationResult:
        SetupService(self.session).authorize_beve_stage(payload.setup_code)
        result = self._verify(self._candidate_config(payload))
        self._audit_verification(result, operation="test")
        self.session.flush()
        return result

    def configure(self, payload: BeveSetupRequest) -> BeveConfigurationResponse:
        # The database row lock protects PostgreSQL; this process lock makes
        # SQLite/development behavior deterministic without duplicating setup.
        with _BEVE_CONFIGURATION_LOCK:
            setup = SetupService(self.session)
            state = setup.authorize_beve_stage(payload.setup_code)
            candidate_result = self._verify(self._candidate_config(payload))
            if not candidate_result.success:
                self._audit_verification(candidate_result, operation="configure")
                self.session.flush()
                return BeveConfigurationResponse(
                    verification=candidate_result,
                    setup=setup.progress(),
                )

            try:
                with self.session.begin_nested():
                    self._persist(payload)
                    persisted = self.runtime_configuration.get_beve_configuration()
                    final_result = self._verify(self._resolved_config(persisted))
                    if not final_result.success:
                        raise _PersistedVerificationFailed(final_result)
            except _PersistedVerificationFailed as exc:
                self._audit_verification(exc.result, operation="persisted_verification")
                self.session.flush()
                return BeveConfigurationResponse(
                    verification=exc.result,
                    setup=setup.progress(),
                )
            except (RuntimeConfigurationError, RuntimeSecretError, ValidationError):
                result = self._failure("configuration_invalid")
                self._audit_verification(result, operation="persistence")
                self.session.flush()
                return BeveConfigurationResponse(
                    verification=result,
                    setup=setup.progress(),
                )

            state.beve_configured = True
            self.session.add(SystemEventRecord(
                category="installation.beve",
                severity="info",
                message="BEVE configuration verified and persisted",
                details={"result": "success"},
            ))
            self.session.flush()
            return BeveConfigurationResponse(
                verification=final_result,
                setup=setup.progress(),
            )

    def _candidate_config(self, payload: BeveSetupRequest) -> BeveConfig:
        return BeveConfig(
            base_url=self.environment.beve_base_url,
            username=payload.username,
            password=payload.password,
            station_id=payload.station_id,
            device_id=payload.device_id,
            time_zone=self.environment.beve_time_zone,
            timeout_seconds=self.environment.beve_timeout_seconds,
        )

    @staticmethod
    def _resolved_config(configuration: BeveRuntimeConfiguration) -> BeveConfig:
        if not configuration.configured:
            raise RuntimeConfigurationError("BEVE runtime configuration is incomplete")
        return BeveConfig(
            base_url=configuration.base_url,
            username=configuration.username,
            password=configuration.password,
            station_id=configuration.station_id,
            device_id=configuration.device_id,
            time_zone=configuration.time_zone,
            timeout_seconds=configuration.timeout_seconds,
        )

    def _persist(self, payload: BeveSetupRequest) -> None:
        self.runtime_configuration.set_secret("beve", "username", payload.username)
        self.runtime_configuration.set_secret("beve", "password", payload.password)
        self.runtime_configuration.set_non_secret("beve", "station_id", payload.station_id)
        self.runtime_configuration.set_non_secret("beve", "device_id", payload.device_id)

    def _verify(self, configuration: BeveConfig) -> BeveVerificationResult:
        client: object | None = None
        try:
            client = self.client_factory(configuration)
            telemetry = self.adapter.read(client)
            signals = (
                telemetry.inverter.status,
                telemetry.inverter.rated_power_w,
                telemetry.inverter.output_voltage,
                telemetry.inverter.output_power_w,
                telemetry.battery.soc,
                telemetry.solar.connected,
                telemetry.grid.voltage,
            )
            if all(value is None for value in signals):
                return self._failure("malformed_response")
            return BeveVerificationResult(
                success=True,
                device_verified=True,
                message="BEVE inverter telemetry verified.",
                summary=BeveVerificationSummary(
                    station_device_matched=True,
                    inverter_status=telemetry.inverter.status,
                    battery_soc=telemetry.battery.soc,
                    output_power_w=telemetry.inverter.output_power_w,
                    pv_status=telemetry.solar.connected,
                    source_timestamp=telemetry.timestamp,
                ),
            )
        except BeveAuthenticationError:
            return self._failure("authentication_failed")
        except BeveDeviceNotFoundError:
            return self._failure("device_not_found")
        except BeveTimeoutError:
            return self._failure("timeout")
        except BeveConnectionError:
            return self._failure("network_error")
        except (BeveMalformedResponseError, BeveIncompleteResponseError, BeveMappingError):
            return self._failure("malformed_response")
        except (BeveConfigurationError, ValidationError, ValueError):
            return self._failure("configuration_invalid")
        except (BeveCloudError, BeveIntegrationError):
            return self._failure("vendor_error")
        except Exception:
            return self._failure("vendor_error")
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    @staticmethod
    def _failure(category: BeveSetupErrorCategory) -> BeveVerificationResult:
        return BeveVerificationResult(
            success=False,
            device_verified=False,
            category=category,
            message=_ERROR_MESSAGES[category],
        )

    def _audit_verification(
        self,
        result: BeveVerificationResult,
        *,
        operation: str,
    ) -> None:
        self.session.add(SystemEventRecord(
            category="installation.beve",
            severity="info" if result.success else "warning",
            message=(
                "BEVE configuration verification succeeded"
                if result.success
                else "BEVE configuration verification failed"
            ),
            details={
                "operation": operation,
                "result": "success" if result.success else result.category,
            },
        ))


__all__ = ["BeveClientFactory", "BeveSetupService"]
