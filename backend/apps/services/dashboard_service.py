"""Collector/cache-first dashboard aggregation with persistence fallback."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.jobs.energy_collector import CollectorSnapshot, EnergyCollector
from apps.models import (
    BatteryTelemetryStatus, ConnectivityType, DataFreshness, DataSource, DataStatus,
    GridTelemetryStatus, InverterTelemetryStatus, SolarTelemetryStatus, SourceStatus,
)
from apps.models.persistence import (
    AlertRecord, AreaRecord, BatteryReadingRecord, BreakerReadingRecord,
    DeviceRecord, GridReadingRecord, InverterReadingRecord, SolarReadingRecord,
)
from apps.schemas.dashboard import (
    ComponentHealth, DashboardArea, DashboardAreas, DashboardSnapshot, DashboardSystem, OverallHealth,
)
from apps.services.battery_runtime_service import BatteryRuntimeEstimator


class DashboardService:
    def __init__(
        self,
        session: Session,
        collector: EnergyCollector | None,
        *,
        clock=None,
    ) -> None:
        self.session = session
        self.collector = collector
        self.clock = clock or (lambda: datetime.now(UTC))
        self.battery_runtime_estimator = BatteryRuntimeEstimator(clock=self.clock)

    async def get_dashboard(self) -> DashboardSnapshot:
        cache = await self.collector.get_snapshot() if self.collector else CollectorSnapshot()
        inverter, battery, solar, grid = self._inverter_categories(cache)
        data_status = self._inverter_data_status(cache)
        areas = self._areas(cache)
        system = self._system(cache, areas, data_status)
        return DashboardSnapshot(
            system=system, inverter=inverter, battery=battery, solar=solar, grid=grid,
            battery_runtime=self.battery_runtime_estimator.estimate(
                cache.inverter, data_status, cache.inverter_load_samples,
            ),
            data_status=data_status, areas=areas,
        )

    async def get_summary(self) -> DashboardSystem:
        cache = await self.collector.get_snapshot() if self.collector else CollectorSnapshot()
        return self._system(cache, self._areas(cache), self._inverter_data_status(cache))

    async def get_areas(self) -> DashboardAreas:
        cache = await self.collector.get_snapshot() if self.collector else CollectorSnapshot()
        areas = self._areas(cache)
        latest = max((area.last_seen for area in areas if area.last_seen), default=None)
        return DashboardAreas(last_update=latest, items=areas, total=len(areas))

    def _inverter_categories(self, cache: CollectorSnapshot):
        if cache.inverter is not None:
            return (
                cache.inverter.inverter, cache.inverter.battery,
                cache.inverter.solar, cache.inverter.grid,
            )
        inverter = self.session.scalar(select(InverterReadingRecord).order_by(InverterReadingRecord.timestamp.desc()).limit(1))
        battery = self.session.scalar(select(BatteryReadingRecord).order_by(BatteryReadingRecord.timestamp.desc()).limit(1))
        solar = self.session.scalar(select(SolarReadingRecord).order_by(SolarReadingRecord.timestamp.desc()).limit(1))
        grid = self.session.scalar(select(GridReadingRecord).order_by(GridReadingRecord.timestamp.desc()).limit(1))
        return (
            InverterTelemetryStatus(
                status=inverter.status, rated_power_w=inverter.rated_power_w,
                output_voltage=inverter.output_voltage, output_frequency=inverter.output_frequency,
                output_power_w=inverter.output_power_w, load_percentage=inverter.load_percentage,
            ) if inverter else InverterTelemetryStatus(),
            BatteryTelemetryStatus(
                soc=battery.soc, voltage=battery.voltage,
                charging_current=battery.charging_current, discharge_current=battery.discharge_current,
                power_w=battery.power_w, status=battery.status,
                charge_stage=battery.charge_stage, type=battery.battery_type,
            ) if battery else BatteryTelemetryStatus(),
            SolarTelemetryStatus(
                connected=solar.connected, pv1_voltage=solar.pv1_voltage,
                pv1_power_w=solar.pv1_power_w, pv2_voltage=solar.pv2_voltage,
                pv2_power_w=solar.pv2_power_w, total_power_w=solar.total_power_w,
                daily_energy_kwh=solar.daily_energy_kwh,
                monthly_energy_kwh=solar.monthly_energy_kwh,
                total_energy_kwh=solar.total_energy_kwh,
            ) if solar else SolarTelemetryStatus(),
            GridTelemetryStatus(voltage=grid.voltage, frequency=grid.frequency, power_w=grid.power_w)
            if grid else GridTelemetryStatus(),
        )

    def _inverter_data_status(self, cache: CollectorSnapshot) -> DataStatus:
        state = next(
            (item for item in cache.devices.values() if item.data_source is DataSource.BEVE_CLOUD),
            None,
        )
        if state is not None:
            connected = state.source_status is SourceStatus.CONNECTED
            return DataStatus(
                connectivity_type=ConnectivityType.CLOUD,
                data_source=DataSource.BEVE_CLOUD,
                available=connected and cache.inverter is not None,
                stale=state.stale,
                source_status=state.source_status,
                data_freshness=state.data_freshness,
                last_successful_update=state.last_successful_update,
                last_attempt_at=state.last_attempt_at,
                last_successful_poll_at=state.last_successful_poll_at,
                source_timestamp=state.source_timestamp,
                source_changed=state.source_changed,
                source_age_seconds=state.source_age_seconds,
                last_failure_category=state.last_failure_category,
            )
        latest = self.session.scalar(select(func.max(InverterReadingRecord.timestamp)))
        return DataStatus(
            connectivity_type=ConnectivityType.CLOUD,
            data_source=DataSource.BEVE_CLOUD,
            available=False,
            stale=latest is not None,
            source_status=SourceStatus.UNKNOWN,
            data_freshness=DataFreshness.STALE if latest is not None else DataFreshness.UNAVAILABLE,
            last_successful_update=latest,
            source_timestamp=latest,
            source_age_seconds=max(0.0, (self.clock() - latest).total_seconds()) if latest else None,
        )

    def _areas(self, cache: CollectorSnapshot) -> list[DashboardArea]:
        areas: dict[str, DashboardArea] = {}
        for device_id, breaker in cache.breakers.items():
            areas[device_id] = DashboardArea(
                device_id=device_id, area=breaker.area, online=breaker.online,
                is_on=breaker.status.switch_on,
                voltage_v=breaker.status.electrical.voltage_volts,
                current_a=breaker.status.electrical.current_amperes,
                power_w=breaker.status.electrical.active_power_watts,
                accumulated_energy=breaker.status.energy.accumulated_energy,
                last_seen=breaker.last_seen,
            )
        devices = self.session.execute(
            select(DeviceRecord, AreaRecord.name)
            .outerjoin(AreaRecord, DeviceRecord.area_id == AreaRecord.id)
            .where(DeviceRecord.enabled.is_(True), DeviceRecord.device_type == "breaker")
        ).all()
        latest_times = (
            select(
                BreakerReadingRecord.device_id,
                func.max(BreakerReadingRecord.timestamp).label("latest_timestamp"),
            )
            .group_by(BreakerReadingRecord.device_id)
            .subquery()
        )
        readings = self.session.scalars(
            select(BreakerReadingRecord).join(
                latest_times,
                (BreakerReadingRecord.device_id == latest_times.c.device_id)
                & (BreakerReadingRecord.timestamp == latest_times.c.latest_timestamp),
            )
        ).all()
        latest_by_device = {reading.device_id: reading for reading in readings}
        for device, area_name in devices:
            if device.external_reference in areas:
                continue
            reading = latest_by_device.get(device.id)
            areas[device.external_reference] = DashboardArea(
                device_id=device.external_reference,
                area=area_name or device.friendly_name,
                online=reading.online if reading else False,
                is_on=reading.switch_state if reading else None,
                voltage_v=reading.voltage_v if reading else None,
                current_a=reading.current_a if reading else None,
                power_w=reading.power_w if reading else None,
                accumulated_energy=reading.accumulated_energy if reading else None,
                last_seen=device.last_seen,
            )
        return sorted(areas.values(), key=lambda item: (item.area.lower(), item.device_id))

    def _system(
        self, cache: CollectorSnapshot, areas: list[DashboardArea], data_status: DataStatus
    ) -> DashboardSystem:
        now = self.clock()
        device_rows = self.session.scalars(
            select(DeviceRecord).where(
                DeviceRecord.enabled.is_(True), DeviceRecord.device_type == "breaker"
            )
        ).all()
        states: dict[str, tuple[bool, bool, datetime | None]] = {}
        for device in device_rows:
            last_seen = device.last_seen
            stale = last_seen is None or (now - last_seen).total_seconds() >= settings.device_stale_after_seconds
            states[device.external_reference] = (last_seen is not None and not stale, stale, last_seen)
        for device_id, state in cache.devices.items():
            if state.connectivity_type is ConnectivityType.LOCAL:
                states[device_id] = (state.online is True, state.stale, state.last_seen)
        for area in areas:
            states.setdefault(area.device_id, (area.online, self._stale(area.last_seen, now), area.last_seen))
        online = sum(1 for value in states.values() if value[0])
        offline = sum(1 for value in states.values() if not value[0])
        stale = sum(1 for value in states.values() if value[1])
        active_alerts = self.session.scalar(select(func.count()).select_from(AlertRecord).where(AlertRecord.active.is_(True))) or 0
        last_updates = [value[2] for value in states.values() if value[2] is not None]
        if data_status.last_successful_update is not None:
            last_updates.append(data_status.last_successful_update)
        breakers_health = ComponentHealth.UNKNOWN
        if areas:
            online_areas = sum(1 for area in areas if area.online)
            breakers_health = (
                ComponentHealth.HEALTHY if online_areas == len(areas)
                else ComponentHealth.DEGRADED if online_areas
                else ComponentHealth.UNAVAILABLE
            )
        inverter_cloud_health = (
            ComponentHealth.HEALTHY
            if data_status.source_status is SourceStatus.CONNECTED
            else ComponentHealth.DEGRADED
            if data_status.last_successful_poll_at is not None
            else ComponentHealth.UNAVAILABLE
        )
        inverter_data_health = (
            ComponentHealth.HEALTHY if data_status.data_freshness is DataFreshness.LIVE
            else ComponentHealth.DEGRADED if data_status.source_timestamp is not None
            else ComponentHealth.UNAVAILABLE
        )
        components = {
            "inverter_cloud": inverter_cloud_health,
            "inverter_data": inverter_data_health,
            "breakers": breakers_health,
            "database": ComponentHealth.HEALTHY,
            "realtime": ComponentHealth.HEALTHY,
        }
        health = OverallHealth.UNKNOWN
        known_components = [value for value in components.values() if value is not ComponentHealth.UNKNOWN]
        if known_components:
            if (
                components["inverter_cloud"] is ComponentHealth.UNAVAILABLE
                and components["breakers"] is ComponentHealth.UNAVAILABLE
            ):
                health = OverallHealth.CRITICAL
            elif any(value is not ComponentHealth.HEALTHY for value in known_components) or active_alerts:
                health = OverallHealth.DEGRADED
            else:
                health = OverallHealth.HEALTHY
        return DashboardSystem(
            overall_health=health, system_status=health, components=components,
            last_update=max(last_updates, default=None),
            online_devices=online, offline_devices=offline,
            stale_devices=stale, active_alerts=active_alerts,
        )

    @staticmethod
    def _stale(last_seen: datetime | None, now: datetime) -> bool:
        return last_seen is None or (now - last_seen).total_seconds() >= settings.device_stale_after_seconds
