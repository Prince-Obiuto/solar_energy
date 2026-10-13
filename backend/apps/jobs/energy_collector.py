"""Independent, resilient hardware telemetry collection engine."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.core.config import settings
from apps.db.session import SessionLocal, session_scope
from apps.models import (
    BreakerDevice, ConnectivityType, DataFreshness, DataSource, DomainModel,
    InverterTelemetry, SourceStatus,
)
from apps.models.persistence import (
    BatteryReadingRecord,
    BreakerReadingRecord,
    DeviceRecord,
    GridReadingRecord,
    InverterReadingRecord,
    SolarReadingRecord,
)
from apps.services.breaker_service import BreakerService
from apps.services.inverter_service import InverterService
from apps.services.load_shedding_service import LoadSheddingService

logger = logging.getLogger(__name__)


class CollectorConfig(DomainModel):
    """Polling, persistence, retry, and freshness controls."""

    beve_poll_interval_seconds: float = Field(gt=0)
    beve_poll_stale_after_seconds: float = Field(default=90, gt=0)
    beve_source_stale_after_seconds: float = Field(default=900, gt=0)
    tuya_poll_interval_seconds: float = Field(gt=0)
    telemetry_persist_interval_seconds: float = Field(gt=0)
    device_stale_after_seconds: float = Field(gt=0)
    retry_attempts: int = Field(ge=1, le=5)
    retry_delay_seconds: float = Field(ge=0)

    @classmethod
    def from_application_settings(cls) -> CollectorConfig:
        return cls(
            beve_poll_interval_seconds=settings.beve_poll_interval_seconds,
            beve_poll_stale_after_seconds=settings.beve_poll_stale_after_seconds,
            beve_source_stale_after_seconds=settings.beve_source_stale_after_seconds,
            tuya_poll_interval_seconds=settings.tuya_poll_interval_seconds,
            telemetry_persist_interval_seconds=settings.telemetry_persist_interval_seconds,
            device_stale_after_seconds=settings.device_stale_after_seconds,
            retry_attempts=settings.telemetry_retry_attempts,
            retry_delay_seconds=settings.telemetry_retry_delay_seconds,
        )


class DeviceCollectionState(DomainModel):
    """Current reachability and freshness state for one source."""

    device_id: str
    online: bool | None = False
    stale: bool = True
    last_seen: datetime | None = None
    last_attempt: datetime | None = None
    last_attempt_at: datetime | None = None
    consecutive_failures: int = 0
    connectivity_type: ConnectivityType | None = None
    data_source: DataSource | None = None
    source_status: SourceStatus = SourceStatus.UNKNOWN
    data_freshness: DataFreshness = DataFreshness.UNAVAILABLE
    last_successful_update: datetime | None = None
    last_successful_poll_at: datetime | None = None
    source_timestamp: datetime | None = None
    source_changed: bool | None = None
    source_age_seconds: float | None = Field(default=None, ge=0)
    last_failure_category: str | None = None


class InverterLoadSample(DomainModel):
    """One verified, normalized BEVE source sample for runtime smoothing."""

    timestamp: datetime
    output_power_w: float | None = None
    inverter_status: str | None = None
    battery_status: str | None = None


class CollectorSnapshot(DomainModel):
    """Secret-free in-memory snapshot consumed by later API/WebSocket layers."""

    inverter: InverterTelemetry | None = None
    inverter_load_samples: list[InverterLoadSample] = Field(default_factory=list)
    breakers: dict[str, BreakerDevice] = Field(default_factory=dict)
    devices: dict[str, DeviceCollectionState] = Field(default_factory=dict)


class TelemetryPersistence(Protocol):
    def persist_inverter(self, device_reference: str, telemetry: InverterTelemetry) -> None: ...

    def persist_breaker(
        self, device_reference: str, breaker: BreakerDevice, collected_at: datetime
    ) -> None: ...


class EventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> Awaitable[None] | None: ...


class NullEventPublisher:
    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        return None


class SQLAlchemyTelemetryPersistence:
    """Transactional persistence adapter for normalized collector output."""

    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def persist_inverter(self, device_reference: str, telemetry: InverterTelemetry) -> None:
        with session_scope(self._session_factory) as session:
            device = self._device(session, device_reference)
            device.last_seen = telemetry.timestamp
            session.add_all(
                [
                    InverterReadingRecord(
                        timestamp=telemetry.timestamp,
                        device_id=device.id,
                        status=telemetry.inverter.status,
                        rated_power_w=telemetry.inverter.rated_power_w,
                        output_voltage=telemetry.inverter.output_voltage,
                        output_frequency=telemetry.inverter.output_frequency,
                        output_power_w=telemetry.inverter.output_power_w,
                        load_percentage=telemetry.inverter.load_percentage,
                    ),
                    BatteryReadingRecord(
                        timestamp=telemetry.timestamp,
                        device_id=device.id,
                        soc=telemetry.battery.soc,
                        voltage=telemetry.battery.voltage,
                        charging_current=telemetry.battery.charging_current,
                        discharge_current=telemetry.battery.discharge_current,
                        power_w=telemetry.battery.power_w,
                        status=telemetry.battery.status,
                        charge_stage=telemetry.battery.charge_stage,
                        battery_type=telemetry.battery.type,
                    ),
                    SolarReadingRecord(
                        timestamp=telemetry.timestamp,
                        device_id=device.id,
                        connected=telemetry.solar.connected,
                        pv1_voltage=telemetry.solar.pv1_voltage,
                        pv1_power_w=telemetry.solar.pv1_power_w,
                        pv2_voltage=telemetry.solar.pv2_voltage,
                        pv2_power_w=telemetry.solar.pv2_power_w,
                        total_power_w=telemetry.solar.total_power_w,
                        daily_energy_kwh=telemetry.solar.daily_energy_kwh,
                        monthly_energy_kwh=telemetry.solar.monthly_energy_kwh,
                        total_energy_kwh=telemetry.solar.total_energy_kwh,
                    ),
                    GridReadingRecord(
                        timestamp=telemetry.timestamp,
                        device_id=device.id,
                        voltage=telemetry.grid.voltage,
                        frequency=telemetry.grid.frequency,
                        power_w=telemetry.grid.power_w,
                    ),
                ]
            )

    def persist_breaker(
        self, device_reference: str, breaker: BreakerDevice, collected_at: datetime
    ) -> None:
        timestamp = collected_at
        with session_scope(self._session_factory) as session:
            device = self._device(session, device_reference)
            if breaker.online and breaker.last_seen is not None:
                device.last_seen = breaker.last_seen
            session.add(
                BreakerReadingRecord(
                    timestamp=timestamp,
                    device_id=device.id,
                    online=breaker.online,
                    switch_state=breaker.status.switch_on,
                    voltage_v=breaker.status.electrical.voltage_volts,
                    current_a=breaker.status.electrical.current_amperes,
                    power_w=breaker.status.electrical.active_power_watts,
                    accumulated_energy=breaker.status.energy.accumulated_energy,
                    raw_datapoints=breaker.status.raw_datapoints,
                )
            )

    @staticmethod
    def _device(session: Session, external_reference: str) -> DeviceRecord:
        device = session.scalar(
            select(DeviceRecord).where(DeviceRecord.external_reference == external_reference)
        )
        if device is None:
            raise LookupError("Telemetry device is not registered in persistence")
        return device


class EnergyCollector:
    """Poll BEVE and each Tuya breaker independently and publish normalized state."""

    def __init__(
        self,
        inverter_service: InverterService,
        breaker_service: BreakerService,
        *,
        inverter_device_reference: str | None,
        config: CollectorConfig | None = None,
        persistence: TelemetryPersistence | None = None,
        publisher: EventPublisher | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        load_shedding_service: LoadSheddingService | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inverter_service = inverter_service
        self._breaker_service = breaker_service
        self._inverter_device_reference = inverter_device_reference
        self.config = config or CollectorConfig.from_application_settings()
        self._persistence = persistence
        if publisher is None:
            from apps.jobs.health_monitor import health_event_publisher

            publisher = health_event_publisher
        self._publisher = publisher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._load_shedding_service = load_shedding_service
        self._monotonic = monotonic
        self._snapshot = CollectorSnapshot()
        self._state_lock = asyncio.Lock()
        self._source_locks: dict[str, asyncio.Lock] = {}
        self._last_persisted: dict[str, datetime] = {}
        self._last_persisted_online: dict[str, bool] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._task_health: dict[str, dict[str, Any]] = {}
        self._running = False
        self._last_load_management_status: dict[str, Any] | None = None
        self._last_persisted_inverter_source_timestamp: datetime | None = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start one task per source; safe to call more than once."""

        if self._running:
            return
        self._running = True
        if self._inverter_device_reference and self._inverter_service.configured:
            self._create_task(
                self._poll_loop(
                    self._inverter_device_reference,
                    self.config.beve_poll_interval_seconds,
                    self.collect_inverter_once,
                ),
                "beve-telemetry-collector",
            )
        for breaker_id in self._breaker_service.registered_breaker_ids:
            self._create_task(
                self._poll_loop(
                    breaker_id,
                    self.config.tuya_poll_interval_seconds,
                    lambda breaker_id=breaker_id: self.collect_breaker_once(breaker_id),
                ),
                f"tuya-telemetry-{breaker_id}",
            )

    async def stop(self) -> None:
        """Cancel polling and await task cleanup without leaking cancellation."""

        if not self._running:
            return
        self._running = False
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def collect_inverter_once(self) -> bool:
        if not self._inverter_device_reference:
            return False
        source_id = self._inverter_device_reference
        async with self._source_lock(source_id):
            now = self._clock()
            started = self._monotonic()
            try:
                telemetry = await self._with_retry(self._inverter_service.get_current_state)
            except Exception as exc:
                source_status = self._beve_source_status(exc)
                await self._record_inverter_failure(source_id, now, source_status)
                if self._load_shedding_service is not None:
                    self._load_shedding_service.mark_unavailable()
                await self._publish(
                    "inverter.poll_failed",
                    {"device_id": source_id, "timestamp": now, "failure_type": source_status.value},
                )
                await self._publish(
                    "system.status",
                    {"device_id": source_id, "timestamp": now, "data": {
                        "component": "inverter_cloud", "status": "unavailable",
                        "source_status": source_status.value,
                    }},
                )
                logger.warning("BEVE telemetry poll failed category=%s", source_status.value)
                return False
            completed_at = self._clock()
            logger.debug("BEVE telemetry poll completed duration_seconds=%.3f", self._monotonic() - started)
            async with self._state_lock:
                self._snapshot.inverter = telemetry
                samples = self._snapshot.inverter_load_samples
                if not samples or telemetry.timestamp > samples[-1].timestamp:
                    samples.append(InverterLoadSample(
                        timestamp=telemetry.timestamp,
                        output_power_w=telemetry.inverter.output_power_w,
                        inverter_status=telemetry.inverter.status,
                        battery_status=telemetry.battery.status,
                    ))
                    self._snapshot.inverter_load_samples = samples[-5:]
                self._record_inverter_success_locked(source_id, telemetry.timestamp, completed_at)
                inverter_source_state = self._snapshot.devices[source_id].model_copy(deep=True)
                breaker_cache = self._snapshot.breakers.copy()
                stale_breakers = {
                    device_id for device_id, state in self._snapshot.devices.items()
                    if state.connectivity_type is ConnectivityType.LOCAL and state.stale
                }
            if telemetry.timestamp != self._last_persisted_inverter_source_timestamp:
                persisted = await self._persist_if_due(
                    source_id, lambda: self._persistence.persist_inverter(source_id, telemetry)
                    if self._persistence else None,
                )
                if persisted:
                    self._last_persisted_inverter_source_timestamp = telemetry.timestamp
            await self._publish(
                "inverter.telemetry",
                {**telemetry.model_dump(mode="json"), "device_id": source_id,
                 "data_status": inverter_source_state.model_dump(mode="json")},
            )
            if self._load_shedding_service is not None:
                try:
                    events = await self._run_sync(
                        self._load_shedding_service.evaluate,
                        telemetry.battery.soc,
                        telemetry.timestamp,
                        completed_at,
                        breaker_cache,
                        stale_breakers,
                    )
                    for event_type, payload in events:
                        await self._publish(event_type, payload)
                    status_model = await self._run_sync(self._load_shedding_service.get_status)
                    load_status = status_model.model_dump(mode="json")
                    if load_status != self._last_load_management_status:
                        await self._publish("load_management.status", load_status)
                        self._last_load_management_status = load_status
                except Exception:
                    logger.exception("Load shedding evaluation failed")
            return True

    async def collect_breaker_once(self, breaker_id: str) -> bool:
        async with self._source_lock(breaker_id):
            now = self._clock()
            started = self._monotonic()
            breaker: BreakerDevice | None
            unexpected = False
            try:
                # TuyaClient owns bounded communication retries. The collector
                # records one resulting poll outcome and waits for the next cadence.
                breaker = await self._run_sync(self._breaker_service.get_breaker, breaker_id)
            except Exception:
                breaker = None
                unexpected = True
                logger.exception(
                    "Unexpected breaker polling error device_id=%s category=internal_error",
                    breaker_id,
                )
            if breaker is None or not breaker.online:
                prior_state = self._snapshot.devices.get(breaker_id)
                category = (
                    "internal_error" if unexpected
                    else self._breaker_service.get_last_error_category(breaker_id) or "polling_failure"
                )
                confirms_offline = category in {"polling_timeout", "offline", "polling_failure"}
                async with self._state_lock:
                    previous = self._snapshot.breakers.get(breaker_id)
                    if confirms_offline:
                        self._snapshot.breakers[breaker_id] = self._offline_view(
                            breaker_id, previous, breaker
                        )
                await self._record_failure(
                    breaker_id, now, category=category, confirms_offline=confirms_offline
                )
                logger.warning(
                    "Breaker poll failed device_id=%s category=%s client_attempts=%s",
                    breaker_id, category,
                    getattr(self._breaker_service.get_registration(breaker_id).client, "max_attempts", 1),
                )
                if confirms_offline and (prior_state is None or prior_state.online is not False):
                    logger.info("Breaker changed online -> offline device_id=%s", breaker_id)
                await self._publish(
                    "breaker.poll_failed",
                    {
                        "device_id": breaker_id,
                        "timestamp": now,
                        "failure_type": category,
                    },
                )
                if confirms_offline and breaker is not None:
                    await self._persist_if_due(
                        breaker_id, lambda: self._persistence.persist_breaker(
                            breaker_id, self._snapshot.breakers[breaker_id], now
                        )
                        if self._persistence else None,
                        online=False,
                    )
                if confirms_offline:
                    await self._publish("breaker.offline", {"device_id": breaker_id})
                return False
            previous_online = self._snapshot.devices.get(breaker_id)
            async with self._state_lock:
                self._snapshot.breakers[breaker_id] = breaker
                successful_at = self._clock()
                self._record_success_locked(breaker_id, successful_at)
            if previous_online is not None and previous_online.online is False:
                logger.info("Breaker recovered device_id=%s online=true", breaker_id)
            logger.debug(
                "Breaker poll succeeded device_id=%s online=true duration_seconds=%.3f",
                breaker_id, self._monotonic() - started,
            )
            await self._persist_if_due(
                breaker_id, lambda: self._persistence.persist_breaker(breaker_id, breaker, now)
                if self._persistence else None,
                online=True,
            )
            await self._publish("breaker.telemetry", breaker.model_dump(mode="json"))
            return True

    async def get_snapshot(self) -> CollectorSnapshot:
        async with self._state_lock:
            self._refresh_stale_locked(self._clock())
            return self._snapshot.model_copy(deep=True)

    async def _poll_loop(
        self,
        source_id: str,
        interval: float,
        collect: Callable[[], Awaitable[bool]],
    ) -> None:
        next_run = self._monotonic()
        try:
            while self._running:
                try:
                    await collect()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Collector iteration failed source_id=%s; polling will continue",
                        source_id,
                    )
                next_run += interval
                now = self._monotonic()
                if next_run < now:
                    next_run = now
                await self._sleep(max(0.0, next_run - now))
        except asyncio.CancelledError:
            raise

    async def _with_retry(self, operation: Callable[[], Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts):
            try:
                return await self._run_sync(operation)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.config.retry_attempts and self.config.retry_delay_seconds:
                    await self._sleep(self.config.retry_delay_seconds)
        if last_error is None:  # pragma: no cover
            raise RuntimeError("Telemetry collection failed")
        raise last_error

    async def _record_failure(
        self, source_id: str, attempted_at: datetime, *,
        category: str = "polling_failure", confirms_offline: bool = True,
    ) -> None:
        async with self._state_lock:
            state = self._snapshot.devices.get(source_id) or DeviceCollectionState(device_id=source_id)
            if confirms_offline:
                state.online = False
            elif state.last_successful_poll_at is None:
                # A mapper/programming failure does not prove LAN reachability
                # either way when no prior successful poll exists.
                state.online = None
            state.last_attempt = attempted_at
            state.last_attempt_at = attempted_at
            state.consecutive_failures += 1
            state.stale = self._is_stale(state.last_successful_poll_at or state.last_seen, attempted_at)
            state.connectivity_type = ConnectivityType.LOCAL
            state.data_source = DataSource.TINYTUYA
            state.source_status = (
                SourceStatus.UNREACHABLE if confirms_offline else SourceStatus.UNKNOWN
            )
            state.last_failure_category = category
            state.data_freshness = (
                DataFreshness.STALE if state.stale and state.last_seen
                else DataFreshness.LIVE if state.last_seen
                else DataFreshness.UNAVAILABLE
            )
            state.last_successful_update = state.last_seen
            self._snapshot.devices[source_id] = state

    async def _record_inverter_failure(
        self, source_id: str, attempted_at: datetime, source_status: SourceStatus
    ) -> None:
        async with self._state_lock:
            state = self._snapshot.devices.get(source_id) or DeviceCollectionState(device_id=source_id)
            state.online = None
            state.last_attempt = attempted_at
            state.last_attempt_at = attempted_at
            state.consecutive_failures += 1
            state.connectivity_type = ConnectivityType.CLOUD
            state.data_source = DataSource.BEVE_CLOUD
            state.source_status = source_status
            state.last_failure_category = source_status.value
            state.stale = state.last_successful_update is not None
            self._refresh_inverter_freshness_locked(state, attempted_at)
            self._snapshot.devices[source_id] = state

    def _record_success_locked(self, source_id: str, seen_at: datetime) -> None:
        state = self._snapshot.devices.get(source_id) or DeviceCollectionState(device_id=source_id)
        state.online = True
        state.stale = False
        state.last_seen = seen_at
        state.last_attempt = self._clock()
        state.last_attempt_at = state.last_attempt
        state.consecutive_failures = 0
        state.connectivity_type = ConnectivityType.LOCAL
        state.data_source = DataSource.TINYTUYA
        state.source_status = SourceStatus.CONNECTED
        state.data_freshness = DataFreshness.LIVE
        state.last_successful_update = seen_at
        state.last_successful_poll_at = seen_at
        state.last_failure_category = None
        self._snapshot.devices[source_id] = state

    def _record_inverter_success_locked(
        self, source_id: str, source_timestamp: datetime, polled_at: datetime
    ) -> None:
        state = self._snapshot.devices.get(source_id) or DeviceCollectionState(device_id=source_id)
        previous_source_timestamp = state.source_timestamp
        state.online = None
        state.last_seen = polled_at
        state.last_successful_update = polled_at
        state.last_successful_poll_at = polled_at
        state.last_attempt = polled_at
        state.last_attempt_at = polled_at
        state.source_timestamp = source_timestamp
        state.source_changed = previous_source_timestamp is None or source_timestamp > previous_source_timestamp
        state.consecutive_failures = 0
        state.connectivity_type = ConnectivityType.CLOUD
        state.data_source = DataSource.BEVE_CLOUD
        state.source_status = SourceStatus.CONNECTED
        state.last_failure_category = None
        self._refresh_inverter_freshness_locked(state, polled_at)
        self._snapshot.devices[source_id] = state
        if state.source_changed:
            logger.info("BEVE source telemetry timestamp advanced")

    def _refresh_stale_locked(self, now: datetime) -> None:
        for state in self._snapshot.devices.values():
            if state.connectivity_type is ConnectivityType.CLOUD:
                self._refresh_inverter_freshness_locked(state, now)
            else:
                timed_out = self._is_stale(state.last_successful_update or state.last_seen, now)
                state.stale = state.stale or timed_out
                if state.stale and state.data_freshness is DataFreshness.LIVE:
                    state.data_freshness = DataFreshness.STALE

    def _refresh_inverter_freshness_locked(
        self, state: DeviceCollectionState, now: datetime
    ) -> None:
        poll_stale = self._older_than(
            state.last_successful_poll_at, now, self.config.beve_poll_stale_after_seconds
        )
        if state.source_timestamp is None:
            state.source_age_seconds = None
            state.data_freshness = DataFreshness.UNAVAILABLE
            state.stale = True
            return
        state.source_age_seconds = max(0.0, (now - state.source_timestamp).total_seconds())
        source_stale = state.source_age_seconds >= self.config.beve_source_stale_after_seconds
        state.stale = source_stale
        state.data_freshness = DataFreshness.STALE if source_stale else DataFreshness.LIVE
        if poll_stale and state.source_status is SourceStatus.CONNECTED:
            state.source_status = SourceStatus.UNKNOWN

    @staticmethod
    def _older_than(value: datetime | None, now: datetime, seconds: float) -> bool:
        return value is None or (now - value).total_seconds() >= seconds

    def _is_stale(self, last_seen: datetime | None, now: datetime) -> bool:
        if last_seen is None:
            return True
        return (now - last_seen).total_seconds() >= self.config.device_stale_after_seconds

    @staticmethod
    def _beve_source_status(exc: Exception) -> SourceStatus:
        return {
            "authentication_failed": SourceStatus.AUTHENTICATION_FAILED,
            "timeout": SourceStatus.TIMEOUT,
            "unreachable": SourceStatus.UNREACHABLE,
            "cloud_error": SourceStatus.CLOUD_ERROR,
        }.get(getattr(exc, "category", "unknown"), SourceStatus.UNKNOWN)

    async def _persist_if_due(
        self,
        source_id: str,
        persist: Callable[[], None],
        *,
        online: bool | None = None,
    ) -> bool:
        if self._persistence is None:
            return False
        now = self._clock()
        previous = self._last_persisted.get(source_id)
        state_changed = online is not None and self._last_persisted_online.get(source_id) != online
        if not state_changed and previous is not None and (
            now - previous
        ).total_seconds() < self.config.telemetry_persist_interval_seconds:
            return False
        try:
            await self._run_sync(persist)
        except Exception:
            logger.error("Telemetry persistence failed for source %s", source_id)
            await self._publish(
                "system.database_failure",
                {"device_id": source_id, "timestamp": now, "failure_type": "persistence"},
            )
            return False
        self._last_persisted[source_id] = now
        if online is not None:
            self._last_persisted_online[source_id] = online
        return True

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            result = self._publisher.publish(event_type, payload)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "Telemetry event publication failed event_type=%s device_id=%s",
                event_type, payload.get("device_id", "system"),
            )

    def _source_lock(self, source_id: str) -> asyncio.Lock:
        return self._source_locks.setdefault(source_id, asyncio.Lock())

    async def _run_sync(self, operation: Callable[..., Any], *args: Any) -> Any:
        """Run bounded blocking I/O and let it finish safely during cancellation."""

        task = asyncio.create_task(asyncio.to_thread(operation, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise

    def _create_task(self, coroutine: Awaitable[None], name: str) -> None:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        self._task_health[name] = {"running": True, "last_failure": None}

        def completed(done: asyncio.Task[None]) -> None:
            self._tasks.discard(done)
            health = self._task_health.setdefault(name, {})
            health["running"] = False
            if done.cancelled():
                return
            error = done.exception()
            if error is not None:
                health["last_failure"] = type(error).__name__
                logger.error(
                    "Collector task terminated unexpectedly task_name=%s error_type=%s",
                    name, type(error).__name__, exc_info=(type(error), error, error.__traceback__),
                )
            elif self._running:
                logger.error("Collector task exited unexpectedly task_name=%s", name)

        task.add_done_callback(completed)

    def get_task_health(self) -> dict[str, dict[str, Any]]:
        """Return a secret-free copy of internal poll-task health."""

        return {name: values.copy() for name, values in self._task_health.items()}

    def _offline_view(
        self, breaker_id: str, previous: BreakerDevice | None,
        failed: BreakerDevice | None,
    ) -> BreakerDevice:
        """Preserve last-known measurements while recording confirmed reachability failure."""

        base = previous or failed or self._breaker_service.describe_breaker(breaker_id)
        status = base.status.model_copy(update={"status": "offline"})
        return base.model_copy(update={"online": False, "status": status})


_application_collector: EnergyCollector | None = None


def configure_energy_collector(collector: EnergyCollector | None) -> None:
    """Set the application collector during deployment composition."""

    global _application_collector
    _application_collector = collector


def get_energy_collector() -> EnergyCollector | None:
    return _application_collector
