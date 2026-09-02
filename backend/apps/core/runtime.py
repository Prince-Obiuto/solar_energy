"""Production hardware composition and idempotent device provisioning."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.core.config import Settings, settings
from apps.db.session import SessionLocal, session_scope
from apps.integrations.inverter import BeveConfig
from apps.models.persistence import AreaRecord, DeviceRecord

if TYPE_CHECKING:
    from apps.jobs.energy_collector import EnergyCollector
    from apps.services.breaker_service import BreakerRegistration, BreakerService
    from apps.services.device_service import DeviceService
    from apps.services.energy_service import EnergyService
    from apps.services.inverter_service import InverterService

logger = logging.getLogger(__name__)


class RuntimeConfigurationError(RuntimeError):
    """Safe startup error for incomplete hardware configuration."""


@dataclass(slots=True)
class ApplicationRuntime:
    inverter_service: InverterService
    breaker_service: BreakerService
    device_service: DeviceService
    energy_service: EnergyService
    collector: EnergyCollector | None
    inverter_device_reference: str | None


_runtime: ApplicationRuntime | None = None


def get_application_runtime() -> ApplicationRuntime | None:
    return _runtime


def configure_application_runtime(runtime: ApplicationRuntime | None) -> None:
    from apps.jobs.energy_collector import configure_energy_collector

    global _runtime
    _runtime = runtime
    configure_energy_collector(runtime.collector if runtime else None)


def build_application_runtime(
    config: Settings = settings,
    *,
    beve_client_factory: Callable[[BeveConfig], object] | None = None,
    tuya_client_factory: Callable[[Any], object] | None = None,
    session_factory: sessionmaker[Session] = SessionLocal,
    provision: bool = True,
) -> ApplicationRuntime:
    """Compose configured hardware without making a network request."""

    from apps.integrations.inverter import BeveClient
    from apps.integrations.tuya.client import TuyaClient
    from apps.integrations.tuya.device_loader import load_breaker_registrations
    from apps.jobs.energy_collector import EnergyCollector, SQLAlchemyTelemetryPersistence
    from apps.services.breaker_service import BreakerService
    from apps.services.device_service import DeviceService
    from apps.services.energy_service import EnergyService
    from apps.services.inverter_service import InverterService

    beve_client_factory = beve_client_factory or BeveClient
    if tuya_client_factory is None:
        tuya_client_factory = lambda item: TuyaClient(
            item, max_attempts=config.telemetry_retry_attempts,
            socket_timeout_seconds=config.tuya_socket_timeout_seconds,
            retry_delay_seconds=config.telemetry_retry_delay_seconds,
        )
    registrations = load_breaker_registrations(config.tuya_device_file, client_factory=tuya_client_factory)
    beve_config = _beve_config(config)
    inverter_reference = beve_config.device_id if beve_config else None
    if provision and (inverter_reference or registrations):
        provision_hardware_devices(session_factory, registrations, inverter_reference=inverter_reference)
        registrations = _apply_database_breaker_metadata(
            session_factory, registrations, client_factory=tuya_client_factory
        )
    inverter = InverterService(beve_client_factory(beve_config) if beve_config else None)
    breakers = BreakerService(registrations)
    devices = DeviceService(inverter, breakers, inverter_id=inverter_reference)
    energy = EnergyService(inverter, breakers)
    collector = None
    if inverter_reference or registrations:
        collector = EnergyCollector(
            inverter, breakers, inverter_device_reference=inverter_reference,
            persistence=SQLAlchemyTelemetryPersistence(session_factory),
        )
    runtime = ApplicationRuntime(inverter, breakers, devices, energy, collector, inverter_reference)
    configure_application_runtime(runtime)
    return runtime


def provision_hardware_devices(
    session_factory: sessionmaker[Session],
    registrations: list[BreakerRegistration],
    *,
    inverter_reference: str | None,
) -> None:
    """Create missing hardware rows while preserving customized existing rows."""

    with session_scope(session_factory) as session:
        for registration in registrations:
            item = registration.client.config
            if session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == item.device_id)):
                continue
            session.add(DeviceRecord(
                external_reference=item.device_id, friendly_name=item.friendly_name,
                device_type="breaker", area=_area(session, item.area), manufacturer="Tuya",
                model="TMPH", protocol=item.protocol_version, enabled=item.enabled,
            ))
        if inverter_reference and not session.scalar(
            select(DeviceRecord).where(DeviceRecord.external_reference == inverter_reference)
        ):
            session.add(DeviceRecord(
                external_reference=inverter_reference, friendly_name="Smart hybrid inverter",
                device_type="inverter", area=_area(session, "Department of Information Technology"),
                manufacturer="FiveStar", protocol="BEVE cloud", enabled=True,
            ))
    logger.info("Hardware device provisioning completed")


def _area(session: Session, name: str) -> AreaRecord:
    area = session.scalar(select(AreaRecord).where(AreaRecord.name == name))
    if area is None:
        area = AreaRecord(name=name)
        session.add(area)
        session.flush()
    return area


def _apply_database_breaker_metadata(
    session_factory: sessionmaker[Session],
    registrations: list[BreakerRegistration],
    *,
    client_factory: Callable[[Any], object],
) -> list[BreakerRegistration]:
    """Prefer administrator-customized names/areas without touching secrets."""

    with session_factory() as session:
        records = {
            record.external_reference: record
            for record in session.scalars(
                select(DeviceRecord).where(DeviceRecord.external_reference.in_(
                    [item.client.config.device_id for item in registrations]
                ))
            )
        }
        result = []
        for registration in registrations:
            original = registration.client.config
            record = records.get(original.device_id)
            if record is None:
                result.append(registration)
                continue
            configured = original.model_copy(update={
                "friendly_name": record.friendly_name,
                "area": record.area.name if record.area else original.area,
            })
            result.append(type(registration)(
                client=client_factory(configured), capabilities=registration.capabilities
            ))
        return result


def _beve_config(config: Settings) -> BeveConfig | None:
    required = {
        "username": config.beve_username, "password": config.beve_password,
        "app_id": config.beve_app_id, "app_secret_encrypted": config.beve_app_secret_encrypted,
        "station_id": config.beve_station_id, "device_id": config.beve_device_id,
    }
    present = {name for name, value in required.items() if value is not None and str(value) != ""}
    if not present:
        return None
    if len(present) != len(required):
        missing = ", ".join(sorted(set(required) - present))
        raise RuntimeConfigurationError(f"BEVE configuration is incomplete; missing: {missing}")
    return BeveConfig(**required, time_zone=config.beve_time_zone, timeout_seconds=config.beve_timeout_seconds)
