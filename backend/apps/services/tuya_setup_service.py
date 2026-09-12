"""Token-authorized, read-only Tuya cloud-to-LAN onboarding workflow."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from apps.core.config import Settings, settings
from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.client import (
    TuyaClient,
    TuyaCommunicationError,
    TuyaConfigurationError,
    TuyaDeviceConfig,
    TuyaMalformedResponseError,
    TuyaOfflineError,
    TuyaTimeoutError,
)
from apps.integrations.tuya.device_loader import parse_breaker_configs
from apps.integrations.tuya.onboarding import (
    TinyTuyaCloudGateway,
    TinyTuyaLanDiscovery,
    TuyaCloudAuthenticationError,
    TuyaCloudConfig,
    TuyaCloudConfigurationError,
    TuyaCloudDeviceFetchError,
    TuyaCloudMalformedResponseError,
    TuyaCloudNetworkError,
    TuyaCloudTimeoutError,
    TuyaScanError,
    TuyaScanTimeoutError,
)
from apps.models.persistence import SystemEventRecord
from apps.schemas.setup import (
    TuyaCloudCandidateResponse,
    TuyaCloudDiscoveryResponse,
    TuyaCloudSetupRequest,
    TuyaConfigurationStatusResponse,
    TuyaConfiguredDeviceSummary,
    TuyaDeviceConfigurationRequest,
    TuyaDeviceConfigurationResponse,
    TuyaDeviceVerificationResponse,
    TuyaMatchedDeviceResponse,
    TuyaScanResponse,
    TuyaSetupErrorCategory,
)
from apps.security.runtime_secrets import RuntimeSecretError
from apps.services.runtime_configuration_service import (
    RuntimeConfigurationError,
    RuntimeConfigurationService,
)
from apps.services.setup_service import SetupService
from apps.services.tuya_onboarding_store import (
    TuyaOnboardingCandidate,
    TuyaOnboardingSessionError,
    TuyaOnboardingStore,
)


TuyaClientFactory = Callable[[TuyaDeviceConfig], Any]
_TUYA_SCAN_LOCK = threading.Lock()
_TUYA_CONFIGURATION_LOCK = threading.Lock()
_MAX_EXACT_FIND_FALLBACKS = 25

_MESSAGES: dict[TuyaSetupErrorCategory, str] = {
    "cloud_authentication_failed": "Tuya Cloud authentication failed.",
    "cloud_device_fetch_failed": "Tuya Cloud device retrieval failed.",
    "cloud_configuration_invalid": "Tuya Cloud configuration is invalid.",
    "network_error": "Tuya Cloud is unreachable.",
    "timeout": "The Tuya operation timed out.",
    "cloud_malformed_response": "Tuya Cloud returned an invalid device list.",
    "scan_timeout": "The Tuya LAN scan timed out.",
    "no_devices_found": "No matching Tuya devices were found on the LAN.",
    "onboarding_session_invalid": "The Tuya onboarding session is invalid or expired.",
    "device_not_on_lan": "A selected device is not available on the LAN.",
    "device_id_mismatch": "A selected device does not match the onboarding session.",
    "local_connection_failed": "Local communication with a selected breaker failed.",
    "protocol_error": "The selected breaker protocol could not be validated.",
    "malformed_response": "The selected breaker returned malformed telemetry.",
    "unsupported_device": "The selected device is not compatible with the breaker profile.",
    "configuration_invalid": "The selected Tuya device configuration is invalid.",
}


class TuyaScanInProgressError(RuntimeError):
    pass


class TuyaSetupService:
    """Coordinate cloud discovery, exact LAN matching, and encrypted activation."""

    def __init__(
        self,
        session: Session,
        runtime_configuration: RuntimeConfigurationService,
        onboarding_store: TuyaOnboardingStore,
        *,
        cloud_gateway: TinyTuyaCloudGateway | None = None,
        lan_discovery: TinyTuyaLanDiscovery | None = None,
        client_factory: TuyaClientFactory | None = None,
        adapter: TuyaBreakerAdapter | None = None,
        environment: Settings = settings,
    ) -> None:
        self.session = session
        self.runtime_configuration = runtime_configuration
        self.onboarding_store = onboarding_store
        self.cloud_gateway = cloud_gateway or TinyTuyaCloudGateway()
        self.lan_discovery = lan_discovery or TinyTuyaLanDiscovery()
        self.environment = environment
        self.client_factory = client_factory or self._production_client
        self.adapter = adapter or TuyaBreakerAdapter()

    def retrieve_cloud_devices(
        self,
        payload: TuyaCloudSetupRequest,
    ) -> TuyaCloudDiscoveryResponse:
        SetupService(self.session).authorize_tuya_stage(payload.setup_code)
        try:
            config = TuyaCloudConfig(
                region=payload.region,
                access_id=payload.access_id,
                access_secret=payload.access_secret,
                anchor_device_id=payload.anchor_device_id,
            )
            devices = self.cloud_gateway.get_devices(config)
        except TuyaCloudAuthenticationError:
            return self._cloud_failure("cloud_authentication_failed")
        except (TuyaCloudConfigurationError, ValidationError):
            return self._cloud_failure("cloud_configuration_invalid")
        except TuyaCloudNetworkError:
            return self._cloud_failure("network_error")
        except TuyaCloudTimeoutError:
            return self._cloud_failure("timeout")
        except TuyaCloudMalformedResponseError:
            return self._cloud_failure("cloud_malformed_response")
        except TuyaCloudDeviceFetchError:
            return self._cloud_failure("cloud_device_fetch_failed")

        token, onboarding = self.onboarding_store.create(devices)
        response = TuyaCloudDiscoveryResponse(
            success=True,
            message="Tuya Cloud devices retrieved.",
            onboarding_session=token,
            devices=[
                TuyaCloudCandidateResponse(
                    device_ref=candidate.device_ref,
                    name=candidate.name,
                    product_id=candidate.product_id,
                    category=candidate.category,
                    model=candidate.model,
                    online=candidate.online,
                    local_configuration_available=candidate.local_key is not None,
                )
                for candidate in onboarding.candidates.values()
            ],
        )
        self._audit("Tuya Cloud candidates retrieved", result="success")
        self.session.flush()
        return response

    def scan_lan(self, setup_code: str, onboarding_token: str) -> TuyaScanResponse:
        SetupService(self.session).authorize_tuya_stage(setup_code)
        try:
            onboarding = self.onboarding_store.get(onboarding_token)
        except TuyaOnboardingSessionError:
            return self._scan_failure("onboarding_session_invalid")
        if not _TUYA_SCAN_LOCK.acquire(blocking=False):
            raise TuyaScanInProgressError("A Tuya LAN scan is already in progress")
        try:
            try:
                lan_devices = self.lan_discovery.scan(
                    maxretry=self.environment.tuya_onboarding_scan_maxretry
                )
            except TuyaScanTimeoutError:
                return self._scan_failure("scan_timeout")
            except TuyaScanError:
                return self._scan_failure("no_devices_found")

            fallback_count = 0
            for candidate in onboarding.candidates.values():
                matched = lan_devices.get(candidate.device_id)
                if matched is not None and matched.device_id != candidate.device_id:
                    matched = None
                if (
                    matched is None
                    and candidate.local_key is not None
                    and fallback_count < _MAX_EXACT_FIND_FALLBACKS
                ):
                    fallback_count += 1
                    matched = self.lan_discovery.find_exact(candidate.device_id)
                    if matched is not None and matched.device_id != candidate.device_id:
                        matched = None
                candidate.lan = matched

            matched_candidates = [
                candidate for candidate in onboarding.candidates.values()
                if candidate.lan is not None
            ]
            if not matched_candidates:
                return self._scan_failure("no_devices_found")
            cloud_ids = {
                candidate.device_id for candidate in onboarding.candidates.values()
            }
            response = TuyaScanResponse(
                success=True,
                message="Tuya LAN scan completed.",
                matched=[self._matched_response(candidate) for candidate in matched_candidates],
                cloud_only=[
                    candidate.device_ref
                    for candidate in onboarding.candidates.values()
                    if candidate.lan is None
                ],
                lan_only_count=len(set(lan_devices) - cloud_ids),
            )
            self._audit("Tuya LAN scan completed", result="success")
            self.session.flush()
            return response
        finally:
            _TUYA_SCAN_LOCK.release()

    def configuration_status(self, setup_code: str) -> TuyaConfigurationStatusResponse:
        """Return only setup-safe persisted device metadata without hardware I/O."""

        state = SetupService(self.session).authorize_tuya_stage(setup_code)
        document = self.runtime_configuration.get_tuya_device_configuration() or []
        devices = [
            TuyaConfiguredDeviceSummary(
                friendly_name=item["name"],
                area=item["area"],
            )
            for item in document
        ]
        return TuyaConfigurationStatusResponse(
            configured=state.tuya_configured,
            devices_verified=state.devices_verified,
            configured_device_count=len(devices),
            devices=devices,
        )

    def configure_devices(
        self,
        payload: TuyaDeviceConfigurationRequest,
    ) -> TuyaDeviceConfigurationResponse:
        with _TUYA_CONFIGURATION_LOCK:
            setup = SetupService(self.session)
            state = setup.authorize_tuya_stage(payload.setup_code)
            token = payload.onboarding_session.get_secret_value()
            try:
                onboarding = self.onboarding_store.get(token)
            except TuyaOnboardingSessionError:
                return self._configuration_failure(
                    setup,
                    "onboarding_session_invalid",
                )
            refs = [selection.device_ref for selection in payload.devices]
            if len(refs) != len(set(refs)):
                return self._configuration_failure(setup, "device_id_mismatch")

            configurations: list[tuple[TuyaDeviceConfig, TuyaOnboardingCandidate]] = []
            verification: list[TuyaDeviceVerificationResponse] = []
            for selection in payload.devices:
                candidate = onboarding.candidates.get(selection.device_ref)
                if candidate is None:
                    return self._configuration_failure(
                        setup,
                        "device_id_mismatch",
                        devices=verification,
                    )
                if candidate.local_key is None:
                    return self._configuration_failure(
                        setup,
                        "unsupported_device",
                        devices=verification,
                    )
                sensitive_labels = {
                    candidate.device_id,
                    candidate.local_key.get_secret_value(),
                }
                if selection.friendly_name in sensitive_labels or selection.area in sensitive_labels:
                    return self._configuration_failure(
                        setup,
                        "configuration_invalid",
                        devices=verification,
                    )
                if candidate.lan is None:
                    return self._configuration_failure(
                        setup,
                        "device_not_on_lan",
                        devices=verification,
                    )
                protocol = candidate.lan.protocol_version or candidate.cloud_protocol_version
                if protocol is None:
                    return self._configuration_failure(
                        setup,
                        "protocol_error",
                        devices=verification,
                    )
                try:
                    config = TuyaDeviceConfig(
                        device_id=candidate.device_id,
                        friendly_name=selection.friendly_name,
                        area=selection.area,
                        local_key=candidate.local_key,
                        ip_address=candidate.lan.ip_address,
                        protocol_version=protocol,
                        enabled=True,
                    )
                except ValidationError:
                    return self._configuration_failure(
                        setup,
                        "configuration_invalid",
                        devices=verification,
                    )
                result = self._verify_local(selection.device_ref, config)
                verification.append(result)
                if not result.verified:
                    return self._configuration_failure(
                        setup,
                        result.category or "local_connection_failed",
                        devices=verification,
                    )
                configurations.append((config, candidate))

            document = [
                self._persisted_entry(config, candidate)
                for config, candidate in configurations
            ]
            try:
                with self.session.begin_nested():
                    self.runtime_configuration.set_tuya_device_configuration(document)
                    persisted = self.runtime_configuration.get_tuya_device_configuration()
                    if persisted is None:
                        raise RuntimeConfigurationError(
                            "Persisted Tuya device configuration is unavailable"
                        )
                    resolved = parse_breaker_configs(
                        persisted,
                        require_supported_metadata=False,
                        strict=True,
                    )
                    if [item.device_id for item in resolved] != [
                        item.device_id for item, _ in configurations
                    ]:
                        raise RuntimeConfigurationError(
                            "Persisted Tuya device configuration does not match"
                        )
            except (
                RuntimeConfigurationError,
                RuntimeSecretError,
                TuyaConfigurationError,
                ValidationError,
            ):
                return self._configuration_failure(
                    setup,
                    "configuration_invalid",
                    devices=verification,
                )

            state.tuya_configured = True
            state.devices_verified = True
            self._audit("Tuya devices verified and persisted", result="success")
            self.session.flush()
            response = TuyaDeviceConfigurationResponse(
                success=True,
                message="Tuya breakers verified and configured.",
                devices=verification,
                setup=setup.progress(),
                runtime_activation="restart_required",
            )
            self.onboarding_store.destroy(token)
            return response

    def _production_client(self, config: TuyaDeviceConfig) -> TuyaClient:
        return TuyaClient(
            config,
            max_attempts=self.environment.telemetry_retry_attempts,
            socket_timeout_seconds=self.environment.tuya_socket_timeout_seconds,
            retry_delay_seconds=self.environment.telemetry_retry_delay_seconds,
        )

    def _verify_local(
        self,
        device_ref: str,
        config: TuyaDeviceConfig,
    ) -> TuyaDeviceVerificationResponse:
        client = None
        try:
            client = self.client_factory(config)
            breaker = self.adapter.read(client)
            if not isinstance(breaker.switch_on, bool):
                return self._device_failure(device_ref, config, "unsupported_device")
            return TuyaDeviceVerificationResponse(
                device_ref=device_ref,
                friendly_name=config.friendly_name,
                area=config.area,
                verified=True,
                connectivity="online",
                relay_state=breaker.switch_on,
                voltage_v=breaker.electrical.voltage_volts,
                current_a=breaker.electrical.current_amperes,
                power_w=breaker.electrical.active_power_watts,
                protocol_version=config.protocol_version,
                message="Breaker telemetry verified.",
            )
        except TuyaTimeoutError:
            return self._device_failure(device_ref, config, "timeout")
        except (TuyaOfflineError, TuyaCommunicationError):
            return self._device_failure(device_ref, config, "local_connection_failed")
        except TuyaMalformedResponseError:
            return self._device_failure(device_ref, config, "malformed_response")
        except TuyaConfigurationError:
            return self._device_failure(device_ref, config, "protocol_error")
        except Exception:
            return self._device_failure(device_ref, config, "local_connection_failed")
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    @staticmethod
    def _device_failure(
        device_ref: str,
        config: TuyaDeviceConfig,
        category: TuyaSetupErrorCategory,
    ) -> TuyaDeviceVerificationResponse:
        return TuyaDeviceVerificationResponse(
            device_ref=device_ref,
            friendly_name=config.friendly_name,
            area=config.area,
            verified=False,
            connectivity="unavailable",
            protocol_version=config.protocol_version,
            category=category,
            message=_MESSAGES[category],
        )

    @staticmethod
    def _matched_response(candidate: TuyaOnboardingCandidate) -> TuyaMatchedDeviceResponse:
        assert candidate.lan is not None
        return TuyaMatchedDeviceResponse(
            device_ref=candidate.device_ref,
            name=candidate.name,
            ip_address=candidate.lan.ip_address,
            protocol_version=(
                candidate.lan.protocol_version or candidate.cloud_protocol_version
            ),
            product_id=candidate.product_id or candidate.lan.product_id,
            compatible=None,
            local_configuration_available=candidate.local_key is not None,
        )

    @staticmethod
    def _persisted_entry(
        config: TuyaDeviceConfig,
        candidate: TuyaOnboardingCandidate,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": config.device_id,
            "name": config.friendly_name,
            "area": config.area,
            "key": config.local_key.get_secret_value(),
            "ip": str(config.ip_address),
            "version": config.protocol_version,
            "enabled": config.enabled,
        }
        for key, value in (
            ("product_id", candidate.product_id),
            ("category", candidate.category),
            ("model", candidate.model),
        ):
            if value:
                entry[key] = value
        return entry

    def _cloud_failure(
        self,
        category: TuyaSetupErrorCategory,
    ) -> TuyaCloudDiscoveryResponse:
        self._audit("Tuya Cloud candidate retrieval failed", result=category)
        self.session.flush()
        return TuyaCloudDiscoveryResponse(
            success=False,
            category=category,
            message=_MESSAGES[category],
        )

    def _scan_failure(
        self,
        category: TuyaSetupErrorCategory,
    ) -> TuyaScanResponse:
        self._audit("Tuya LAN scan failed", result=category)
        self.session.flush()
        return TuyaScanResponse(
            success=False,
            category=category,
            message=_MESSAGES[category],
        )

    def _configuration_failure(
        self,
        setup: SetupService,
        category: TuyaSetupErrorCategory,
        *,
        devices: list[TuyaDeviceVerificationResponse] | None = None,
    ) -> TuyaDeviceConfigurationResponse:
        self._audit("Tuya device configuration failed", result=category)
        self.session.flush()
        return TuyaDeviceConfigurationResponse(
            success=False,
            category=category,
            message=_MESSAGES[category],
            devices=devices or [],
            setup=setup.progress(),
        )

    def _audit(self, message: str, *, result: str) -> None:
        self.session.add(SystemEventRecord(
            category="installation.tuya",
            severity="info" if result == "success" else "warning",
            message=message,
            details={"result": result},
        ))


__all__ = ["TuyaClientFactory", "TuyaScanInProgressError", "TuyaSetupService"]
