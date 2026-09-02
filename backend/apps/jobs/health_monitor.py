"""Event-driven and periodic application health monitoring."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from apps.core.config import settings
from apps.db.session import SessionLocal, session_scope
from apps.jobs.energy_collector import CollectorSnapshot, get_energy_collector
from apps.realtime.manager import connection_manager, telemetry_event_publisher
from apps.schemas.alert import AlertSeverity, AlertView
from apps.services.alert_service import AlertService


@dataclass(frozen=True)
class ElectricalThresholds:
    low_voltage_v: float | None = None
    high_voltage_v: float | None = None
    high_current_a: float | None = None
    high_power_w: float | None = None

    @classmethod
    def from_settings(cls) -> "ElectricalThresholds":
        return cls(
            low_voltage_v=settings.alert_low_voltage_v,
            high_voltage_v=settings.alert_high_voltage_v,
            high_current_a=settings.alert_high_current_a,
            high_power_w=settings.alert_high_power_w,
        )


class HealthMonitoringEngine:
    def __init__(self, alert_service: AlertService, *, thresholds: ElectricalThresholds | None = None) -> None:
        self.alerts = alert_service
        self.thresholds = thresholds or ElectricalThresholds.from_settings()

    def process_event(self, event_type: str, payload: dict[str, Any]) -> list[tuple[str, AlertView]]:
        device_id = payload.get("device_id") or payload.get("id")
        changes: list[tuple[str, AlertView]] = []
        if event_type == "breaker.poll_failed":
            failure = payload.get("failure_type", "polling_failure")
            category = {
                "malformed_response": "breaker.malformed_response",
                "offline": "breaker.offline",
                "polling_timeout": "breaker.polling_failure",
            }.get(failure, "breaker.polling_failure")
            changes += self._raise(category, AlertSeverity.WARNING, self._message(category), device_id)
        elif event_type == "breaker.telemetry":
            for category in ("breaker.offline", "breaker.polling_failure", "breaker.malformed_response", "breaker.stale"):
                changes += self._resolve(f"{device_id}:{category}")
            changes += self._electrical(device_id, payload)
        elif event_type == "inverter.poll_failed":
            failure = payload.get("failure_type", "unreachable")
            category = {
                "authentication_failed": "inverter.authentication_failure",
                "authentication_failure": "inverter.authentication_failure",
                "cloud_error": "inverter.malformed_telemetry",
                "malformed_telemetry": "inverter.malformed_telemetry",
            }.get(failure, "inverter.unreachable")
            severity = AlertSeverity.CRITICAL if category == "inverter.authentication_failure" else AlertSeverity.WARNING
            changes += self._raise(category, severity, self._message(category), device_id)
        elif event_type == "inverter.telemetry":
            for category in ("inverter.authentication_failure", "inverter.unreachable", "inverter.malformed_telemetry", "inverter.stale"):
                changes += self._resolve(f"{device_id}:{category}")
            changes += self._inverter_electrical(device_id, payload)
        elif event_type == "control.failed":
            changes += self._raise("breaker.control_failure", AlertSeverity.WARNING, "Breaker control command failed verification or communication", device_id, payload)
        elif event_type.startswith("system.") and event_type.endswith("_failure"):
            category = event_type
            changes += self._raise(category, AlertSeverity.CRITICAL, self._message(category), None, payload)
        elif event_type.startswith("system.") and event_type.endswith("_healthy"):
            changes += self._resolve(f"None:{event_type.removesuffix('_healthy')}_failure")
        return changes

    def evaluate_snapshot(self, snapshot: CollectorSnapshot) -> list[tuple[str, AlertView]]:
        changes = []
        breaker_ids = set(snapshot.breakers)
        for device_id, state in snapshot.devices.items():
            category = "breaker.stale" if device_id in breaker_ids else "inverter.stale"
            key = f"{device_id}:{category}"
            if state.stale:
                changes += self._raise(category, AlertSeverity.WARNING, self._message(category), device_id)
            else:
                changes += self._resolve(key)
        return changes

    def _electrical(self, device_id: str | None, payload: dict[str, Any]):
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        electrical = status.get("electrical") if isinstance(status.get("electrical"), dict) else {}
        return self._threshold_changes(
            device_id,
            voltage=electrical.get("voltage_volts"),
            current=electrical.get("current_amperes"),
            power=electrical.get("active_power_watts"),
        )

    def _inverter_electrical(self, device_id: str | None, payload: dict[str, Any]):
        inverter = payload.get("inverter") if isinstance(payload.get("inverter"), dict) else {}
        return self._threshold_changes(
            device_id, voltage=inverter.get("output_voltage"), current=None,
            power=inverter.get("output_power_w"),
        )

    def _threshold_changes(self, device_id, *, voltage, current, power):
        checks = (
            ("electrical.low_voltage", voltage, self.thresholds.low_voltage_v, lambda value, threshold: value < threshold),
            ("electrical.high_voltage", voltage, self.thresholds.high_voltage_v, lambda value, threshold: value > threshold),
            ("electrical.high_current", current, self.thresholds.high_current_a, lambda value, threshold: value > threshold),
            ("electrical.high_power", power, self.thresholds.high_power_w, lambda value, threshold: value > threshold),
        )
        changes = []
        for category, value, threshold, breached in checks:
            key = f"{device_id}:{category}"
            if threshold is None:
                changes += self._resolve(key)
                continue
            if value is None:
                continue
            if breached(value, threshold):
                changes += self._raise(
                    category, AlertSeverity.WARNING, f"Configured {category.replace('.', ' ')} threshold exceeded",
                    device_id, {"value": value, "threshold": threshold},
                )
            else:
                changes += self._resolve(key)
        return changes

    def _raise(self, category, severity, message, device_id, metadata=None):
        alert, created = self.alerts.raise_alert(
            dedup_key=f"{device_id}:{category}", category=category, severity=severity,
            message=message, device_reference=device_id, metadata=metadata,
        )
        return [("alert.created" if created else "alert.updated", self.alerts.view(alert))]

    def _resolve(self, key):
        alert = self.alerts.resolve(key)
        return [("alert.resolved", self.alerts.view(alert))] if alert else []

    @staticmethod
    def _message(category: str) -> str:
        return {
            "breaker.offline": "Breaker is offline",
            "breaker.polling_failure": "Breaker telemetry polling failed",
            "breaker.malformed_response": "Breaker returned an invalid telemetry response",
            "breaker.stale": "Breaker telemetry is stale",
            "inverter.authentication_failure": "BEVE cloud authentication failed",
            "inverter.unreachable": "BEVE cloud telemetry source is unreachable",
            "inverter.malformed_telemetry": "BEVE cloud returned malformed telemetry",
            "inverter.stale": "Last-known inverter telemetry is stale",
            "system.collector_failure": "Telemetry collector health check failed",
            "system.database_failure": "Database health check failed",
            "system.websocket_failure": "Realtime WebSocket subsystem failed",
        }.get(category, "System health issue detected")


class HealthEventPublisher:
    """Persist health transitions, then forward normalized realtime events."""

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        await telemetry_event_publisher.publish(event_type, payload)
        try:
            changes = await asyncio.to_thread(self._process, event_type, payload)
        except Exception:
            await telemetry_event_publisher.publish(
                "system.status", {"data": {"status": "degraded", "database": "unavailable"}}
            )
            return
        for change_type, alert in changes:
            await telemetry_event_publisher.publish(
                change_type,
                {"device_id": alert.device, "timestamp": alert.last_seen, "data": alert.model_dump(mode="json")},
            )

    @staticmethod
    def _process(event_type: str, payload: dict[str, Any]):
        with session_scope(SessionLocal) as session:
            return HealthMonitoringEngine(AlertService(session)).process_event(event_type, payload)

    async def evaluate_snapshot(self, snapshot: CollectorSnapshot) -> None:
        try:
            changes = await asyncio.to_thread(self._evaluate, snapshot)
        except Exception:
            return
        for change_type, alert in changes:
            await telemetry_event_publisher.publish(
                change_type,
                {"device_id": alert.device, "timestamp": alert.last_seen, "data": alert.model_dump(mode="json")},
            )

    @staticmethod
    def _evaluate(snapshot):
        with session_scope(SessionLocal) as session:
            return HealthMonitoringEngine(AlertService(session)).evaluate_snapshot(snapshot)


class HealthMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="application-health-monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(settings.health_monitor_interval_seconds)
                collector = get_energy_collector()
                if collector is not None:
                    try:
                        await health_event_publisher.evaluate_snapshot(await collector.get_snapshot())
                        await health_event_publisher.publish("system.collector_healthy", {})
                    except Exception:
                        await health_event_publisher.publish("system.collector_failure", {})
                if not connection_manager.heartbeat_healthy:
                    await health_event_publisher.publish("system.websocket_failure", {})
                else:
                    await health_event_publisher.publish("system.websocket_healthy", {})
        except asyncio.CancelledError:
            raise


health_event_publisher = HealthEventPublisher()
health_monitor = HealthMonitor()
