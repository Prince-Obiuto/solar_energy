"""Safe, audited, read-back-verified Tuya breaker control service."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.integrations.tuya.adapter import TuyaBreakerAdapter
from apps.integrations.tuya.client import TuyaIntegrationError, TuyaTimeoutError
from apps.integrations.tuya.constants import (
    DP_CHILD_LOCK, DP_COUNTDOWN, DP_INDICATOR_MODE, DP_RELAY_RESTORE_MODE, DP_SWITCH,
)
from apps.models import CommandResult, CommandStatus
from apps.models.persistence import ControlEventRecord, DeviceRecord, UserRecord
from apps.services.breaker_service import BreakerNotFoundError, BreakerService
from apps.schemas.alert import AlertSeverity
from apps.services.alert_service import AlertService


class BreakerControlService:
    """Execute only verified TMPH commands and persist their complete audit lifecycle."""

    _execution_lock = threading.Lock()

    def __init__(
        self,
        session: Session,
        breaker_service: BreakerService,
        *,
        adapter: TuyaBreakerAdapter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
        verify_delay_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.breakers = breaker_service
        self.adapter = adapter or TuyaBreakerAdapter()
        self.sleep = sleep
        self.clock = clock or (lambda: datetime.now(UTC))
        self.verify_delay_seconds = settings.tuya_control_verify_delay_seconds if verify_delay_seconds is None else verify_delay_seconds
        self.alerts = AlertService(session, clock=self.clock)
        self.alert_changes = []

    def execute(
        self,
        *,
        request_id: str,
        breaker_id: str,
        action: str,
        requested_value: Any,
        user: UserRecord | None,
        reason: str | None,
        client_ip: str | None,
        system_actor: str | None = None,
        audit_details: dict[str, Any] | None = None,
    ) -> CommandResult:
        if user is None and system_actor is None:
            raise ValueError("A human or trusted system actor is required")
        with self._execution_lock:
            duplicate = self.session.scalar(select(ControlEventRecord).where(ControlEventRecord.request_id == request_id))
            if duplicate is not None:
                return self._result(duplicate, duplicate=True)

            registration = self.breakers.get_registration(breaker_id)
            device = self.session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == breaker_id))
            if device is None:
                raise BreakerNotFoundError(f"Breaker {breaker_id!r} is not registered in persistence")

            datapoint = self._datapoint(action)
            event = ControlEventRecord(
                timestamp=self.clock(), requested_at=self.clock(), request_id=request_id,
                user_id=user.id if user else None, role=user.role if user else "system", device_id=device.id, area_id=device.area_id,
                command=action, action=action, status=CommandStatus.RUNNING.value,
                requested_by=user.email if user else system_actor, requested_value=requested_value, reason=reason,
                client_ip=client_ip, hardware_acknowledgement=False,
                details={"external_device_reference": breaker_id, **(audit_details or {})},
            )
            self.session.add(event)
            try:
                self.session.flush()
            except IntegrityError:
                # The unique request ID is the cross-process idempotency guard.
                # A concurrent worker may have won after our initial lookup.
                self.session.rollback()
                duplicate = self.session.scalar(
                    select(ControlEventRecord).where(ControlEventRecord.request_id == request_id)
                )
                if duplicate is None:
                    raise
                return self._result(duplicate, duplicate=True)

            capability = {
                "switch": registration.capabilities.switching,
                "countdown": registration.capabilities.countdown,
                "relay_restore_mode": registration.capabilities.remote_configuration,
                "indicator_mode": registration.capabilities.remote_configuration,
                "child_lock": registration.capabilities.remote_configuration,
            }[action]
            if not capability:
                event.status = CommandStatus.REJECTED.value
                event.error_information = "Command is unsupported by this breaker"
                event.completed_at = self.clock()
                self.session.flush()
                return self._result(event)

            try:
                previous = self.adapter.read_control_value(registration.client, datapoint)
                event.previous_value = previous
                self._write(registration.client, action, requested_value)
                event.hardware_acknowledgement = True
                if self.verify_delay_seconds:
                    self.sleep(self.verify_delay_seconds)
                verified = self.adapter.read_control_value(registration.client, datapoint)
                event.verified_value = verified
                if type(verified) is not type(requested_value) or verified != requested_value:
                    event.status = CommandStatus.FAILED.value
                    event.error_information = "Hardware read-back did not match the requested value"
                else:
                    event.status = CommandStatus.SUCCEEDED.value
            except TuyaTimeoutError:
                event.status = CommandStatus.TIMED_OUT.value
                event.error_information = "Breaker communication timed out"
            except TuyaIntegrationError:
                event.status = CommandStatus.FAILED.value
                event.error_information = "Breaker communication failed"
            except ValueError:
                event.status = CommandStatus.REJECTED.value
                event.error_information = "Command validation failed"
            event.completed_at = self.clock()
            if event.status in {CommandStatus.FAILED.value, CommandStatus.TIMED_OUT.value}:
                alert, created = self.alerts.raise_alert(
                    dedup_key=f"{breaker_id}:breaker.control_failure",
                    category="breaker.control_failure", severity=AlertSeverity.WARNING,
                    message="Breaker control command failed verification or communication",
                    device_reference=breaker_id,
                    metadata={"action": action, "status": event.status},
                )
                self.alert_changes.append(("alert.created" if created else "alert.updated", self.alerts.view(alert)))
            elif event.status == CommandStatus.SUCCEEDED.value:
                alert = self.alerts.resolve(f"{breaker_id}:breaker.control_failure")
                if alert:
                    self.alert_changes.append(("alert.resolved", self.alerts.view(alert)))
            self.session.flush()
            return self._result(event)

    @staticmethod
    def _datapoint(action: str) -> int:
        mapping = {
            "switch": DP_SWITCH, "countdown": DP_COUNTDOWN,
            "relay_restore_mode": DP_RELAY_RESTORE_MODE,
            "indicator_mode": DP_INDICATOR_MODE, "child_lock": DP_CHILD_LOCK,
        }
        try:
            return mapping[action]
        except KeyError:
            raise ValueError("Unsupported breaker command") from None

    def _write(self, client, action: str, value: Any) -> None:
        methods = {
            "switch": self.adapter.set_switch,
            "countdown": self.adapter.set_countdown,
            "relay_restore_mode": self.adapter.set_relay_restore_mode,
            "indicator_mode": self.adapter.set_indicator_mode,
            "child_lock": self.adapter.set_child_lock,
        }
        methods[action](client, value)

    @staticmethod
    def _result(event: ControlEventRecord, *, duplicate: bool = False) -> CommandResult:
        external_id = (event.details or {}).get("external_device_reference")
        return CommandResult(
            command_id=event.request_id or str(event.id), device_id=str(external_id or event.device_id),
            status=CommandStatus(event.status), completed_at=event.completed_at,
            message=event.error_information,
            data={
                "duplicate": duplicate,
                "previous_value": event.previous_value,
                "requested_value": event.requested_value,
                "hardware_acknowledgement": event.hardware_acknowledgement,
                "verified_value": event.verified_value,
            },
        )
