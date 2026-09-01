"""Collector/cache-first dashboard aggregation with persistence fallback."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.jobs.energy_collector import CollectorSnapshot, EnergyCollector
from apps.models import (
    BatteryTelemetryStatus, GridTelemetryStatus, InverterTelemetryStatus,
    SolarTelemetryStatus,
)
from apps.models.persistence import (
    AlertRecord, AreaRecord, BatteryReadingRecord, BreakerReadingRecord,
    DeviceRecord, GridReadingRecord, InverterReadingRecord, SolarReadingRecord,
)
from apps.schemas.dashboard import (
    DashboardArea, DashboardAreas, DashboardSnapshot, DashboardSystem, OverallHealth,
)


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

    async def get_dashboard(self) -> DashboardSnapshot:
        cache = await self.collector.get_snapshot() if self.collector else CollectorSnapshot()
        inverter, battery, solar, grid = self._inverter_categories(cache)
        areas = self._areas(cache)
        system = self._system(cache, areas)
        return DashboardSnapshot(
            system=system, inverter=inverter, battery=battery, solar=solar, grid=grid,
            areas=areas,
        )

    async def get_summary(self) -> DashboardSystem:
        cache = await self.collector.get_snapshot() if self.collector else CollectorSnapshot()
        return self._system(cache, self._areas(cache))

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

    def _areas(self, cache: CollectorSnapshot) -> list[DashboardArea]:
        areas: dict[str, DashboardArea] = {}
        for device_id, breaker in cache.breakers.items():
            areas[device_id] = DashboardArea(
                device_id=device_id, area=breaker.area, online=breaker.online,
                is_on=breaker.status.switch_on,
                voltage_v=breaker.status.electrical.voltage_volts,
                current_a=breaker.status.electrical.current_amperes,
                power_w=breaker.status.electrical.active_power_watts,
                accumulated_energy=breaker.status.energy.total_kwh,
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

    def _system(self, cache: CollectorSnapshot, areas: list[DashboardArea]) -> DashboardSystem:
        now = self.clock()
        device_rows = self.session.scalars(select(DeviceRecord).where(DeviceRecord.enabled.is_(True))).all()
        states: dict[str, tuple[bool, bool, datetime | None]] = {}
        for device in device_rows:
            last_seen = device.last_seen
            stale = last_seen is None or (now - last_seen).total_seconds() >= settings.device_stale_after_seconds
            states[device.external_reference] = (last_seen is not None and not stale, stale, last_seen)
        for device_id, state in cache.devices.items():
            states[device_id] = (state.online, state.stale, state.last_seen)
        for area in areas:
            states.setdefault(area.device_id, (area.online, self._stale(area.last_seen, now), area.last_seen))
        online = sum(1 for value in states.values() if value[0])
        offline = sum(1 for value in states.values() if not value[0])
        stale = sum(1 for value in states.values() if value[1])
        active_alerts = self.session.scalar(select(func.count()).select_from(AlertRecord).where(AlertRecord.active.is_(True))) or 0
        last_updates = [value[2] for value in states.values() if value[2] is not None]
        if cache.inverter is not None:
            last_updates.append(cache.inverter.timestamp)
        health = OverallHealth.UNKNOWN
        if states:
            if offline == len(states):
                health = OverallHealth.CRITICAL
            elif offline or stale or active_alerts:
                health = OverallHealth.DEGRADED
            else:
                health = OverallHealth.HEALTHY
        return DashboardSystem(
            overall_health=health, last_update=max(last_updates, default=None),
            online_devices=online, offline_devices=offline,
            stale_devices=stale, active_alerts=active_alerts,
        )

    @staticmethod
    def _stale(last_seen: datetime | None, now: datetime) -> bool:
        return last_seen is None or (now - last_seen).total_seconds() >= settings.device_stale_after_seconds
