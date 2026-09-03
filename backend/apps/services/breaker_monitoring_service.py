"""Cache-first breaker monitoring with persistence fallback and no LAN I/O."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.jobs.energy_collector import EnergyCollector, get_energy_collector
from apps.models import (
    BreakerDevice, BreakerStatus, ConnectivityType, DataFreshness, DataSource,
    DataStatus, DeviceStatus, ElectricalMeasurement, EnergyMeasurement, SourceStatus,
)
from apps.models.persistence import BreakerReadingRecord, DeviceRecord
from apps.services.breaker_service import BreakerNotFoundError, BreakerService, get_breaker_service


class BreakerMonitoringService:
    """Serve normalized monitoring state without initiating TinyTuya requests."""

    def __init__(
        self,
        session: Session,
        breakers: BreakerService,
        collector: EnergyCollector | None,
        *,
        clock=None,
    ) -> None:
        self.session = session
        self.breakers = breakers
        self.collector = collector
        self.clock = clock or (lambda: datetime.now(UTC))

    async def list_breakers(self) -> list[BreakerDevice]:
        snapshot = await self.collector.get_snapshot() if self.collector else None
        return [self._resolve(device_id, snapshot) for device_id in self.breakers.registered_breaker_ids]

    async def get_breaker(self, breaker_id: str) -> BreakerDevice:
        if breaker_id not in self.breakers.registered_breaker_ids:
            raise BreakerNotFoundError(f"Breaker {breaker_id!r} is not registered")
        snapshot = await self.collector.get_snapshot() if self.collector else None
        return self._resolve(breaker_id, snapshot)

    def _resolve(self, breaker_id: str, snapshot) -> BreakerDevice:
        metadata = self.breakers.describe_breaker(breaker_id)
        if snapshot and breaker_id in snapshot.breakers:
            breaker = snapshot.breakers[breaker_id].model_copy(deep=True)
            state = snapshot.devices.get(breaker_id)
            if state is not None:
                breaker.data_status = DataStatus(
                    connectivity_type=ConnectivityType.LOCAL,
                    data_source=DataSource.TINYTUYA,
                    available=state.online is True and not state.stale,
                    stale=state.stale,
                    source_status=state.source_status,
                    data_freshness=state.data_freshness,
                    last_successful_update=state.last_successful_update,
                    last_attempt_at=state.last_attempt_at,
                    last_successful_poll_at=state.last_successful_poll_at,
                    last_failure_category=state.last_failure_category,
                )
            return breaker
        device = self.session.scalar(
            select(DeviceRecord).where(DeviceRecord.external_reference == breaker_id)
        )
        if device is None:
            return metadata
        reading = self.session.scalar(
            select(BreakerReadingRecord)
            .where(BreakerReadingRecord.device_id == device.id)
            .order_by(BreakerReadingRecord.timestamp.desc())
            .limit(1)
        )
        if reading is None:
            return metadata.model_copy(update={
                "friendly_name": device.friendly_name,
                "area": device.area.name if device.area else metadata.area,
            })
        stale = (self.clock() - reading.timestamp).total_seconds() >= settings.device_stale_after_seconds
        return BreakerDevice(
            id=breaker_id, friendly_name=device.friendly_name,
            area=device.area.name if device.area else metadata.area,
            online=reading.online, last_seen=reading.timestamp,
            capabilities=metadata.capabilities,
            data_status=DataStatus(
                connectivity_type=ConnectivityType.LOCAL, data_source=DataSource.TINYTUYA,
                available=reading.online and not stale, stale=stale,
                source_status=SourceStatus.CONNECTED if reading.online else SourceStatus.UNREACHABLE,
                data_freshness=DataFreshness.STALE if stale else DataFreshness.LIVE,
                last_successful_update=reading.timestamp if reading.online else device.last_seen,
                last_successful_poll_at=reading.timestamp,
            ),
            status=BreakerStatus(
                device_id=breaker_id, name=device.friendly_name,
                status=DeviceStatus.ONLINE if reading.online else DeviceStatus.OFFLINE,
                switch_on=reading.switch_state,
                electrical=ElectricalMeasurement(
                    voltage_volts=reading.voltage_v,
                    current_amperes=reading.current_a,
                    active_power_watts=reading.power_w,
                ),
                energy=EnergyMeasurement(accumulated_energy=reading.accumulated_energy),
            ),
        )


def get_breaker_monitoring_service(session: Session) -> BreakerMonitoringService:
    return BreakerMonitoringService(session, get_breaker_service(), get_energy_collector())
