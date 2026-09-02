"""Battery-SOC policy evaluation using the existing verified breaker controls."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.core.config import Settings
from apps.db.session import session_scope
from apps.models import CommandStatus
from apps.models.persistence import DeviceRecord, LoadSheddingStateRecord
from apps.schemas.load_management import (
    LoadManagementStage, LoadManagementStatus, LoadPolicyStatus, PendingTransition,
)
from apps.services.breaker_service import BreakerNotFoundError, BreakerService
from apps.services.control_service import BreakerControlService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadSheddingPolicy:
    name: str
    display_name: str
    breaker_id: str | None
    shed_soc: float
    restore_soc: float
    priority: int


class LoadSheddingService:
    """Evaluate generic hysteresis policies from successful live SOC reads only."""

    def __init__(
        self,
        config: Settings,
        breaker_service: BreakerService,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] | None = None,
        control_factory: Callable[[Session, BreakerService], BreakerControlService] | None = None,
    ) -> None:
        self.enabled = config.load_shedding_enabled
        self.confirmation_required = config.load_shedding_confirm_readings
        self.breakers = breaker_service
        self.session_factory = session_factory
        self.clock = clock or (lambda: datetime.now(UTC))
        self.control_factory = control_factory or (lambda session, breakers: BreakerControlService(session, breakers))
        self.policies = tuple(sorted((
            LoadSheddingPolicy("lecturer_offices", "Lecturer Offices", config.load_shedding_lecturer_breaker_id, config.load_shedding_lecturer_shed_soc, config.load_shedding_lecturer_restore_soc, 1),
            LoadSheddingPolicy("admin_office", "Admin Office", config.load_shedding_admin_breaker_id, config.load_shedding_admin_shed_soc, config.load_shedding_admin_restore_soc, 2),
        ), key=lambda item: item.priority))
        self._streaks: dict[str, tuple[PendingTransition | None, int]] = {}
        self._current_soc: float | None = None
        self._available = False
        self._breaker_states: dict[str, tuple[bool, bool | None]] = {}
        self._lock = threading.RLock()

    def evaluate(self, soc: float | int | None) -> list[tuple[str, dict[str, Any]]]:
        """Evaluate one successful, current BEVE sample and return events to publish."""

        with self._lock:
            if not self.enabled:
                return []
            if not self._valid_soc(soc):
                self.mark_unavailable()
                logger.info("Load shedding skipped because current SOC is unavailable")
                return []
            self._current_soc = float(soc)
            self._available = True
            events: list[tuple[str, dict[str, Any]]] = []
            for policy in self.policies:
                if not policy.breaker_id:
                    continue
                try:
                    event = self._evaluate_policy(policy, float(soc))
                    if event:
                        events.append(event)
                except Exception:
                    logger.error("Automatic breaker command failed for policy %s", policy.name)
                    self._set_error(policy, "Automatic breaker command failed")
                    events.append(("load_management.action_failed", self._event(policy, float(soc), None, False)))
            return events

    def mark_unavailable(self) -> None:
        with self._lock:
            self._available = False
            self._current_soc = None
            self._streaks.clear()

    def get_status(self) -> LoadManagementStatus:
        with self._lock, session_scope(self.session_factory) as session:
            statuses = [self._policy_status(session, policy) for policy in self.policies]
            if not self.enabled:
                stage = LoadManagementStage.DISABLED
            elif not self._available:
                stage = LoadManagementStage.UNAVAILABLE
            elif any(item.policy_name == "admin_office" and item.automatically_shed for item in statuses):
                stage = LoadManagementStage.CRITICAL_CONSERVATION
            elif any(item.automatically_shed for item in statuses):
                stage = LoadManagementStage.CONSERVATION
            else:
                stage = LoadManagementStage.NORMAL
            return LoadManagementStatus(
                enabled=self.enabled,
                active=self.enabled and any(item.enabled for item in statuses),
                current_soc=self._current_soc,
                current_stage=stage,
                policies=statuses,
            )

    def _evaluate_policy(self, policy: LoadSheddingPolicy, soc: float):
        with session_scope(self.session_factory) as session:
            state, device = self._state(session, policy)
            breaker = self.breakers.get_breaker(policy.breaker_id or "")
            self._breaker_states[policy.name] = (breaker.online, breaker.status.switch_on)
            if not breaker.online or breaker.status.switch_on is None:
                state.last_error = "Breaker is unavailable"
                self._streaks[policy.name] = (None, 0)
                return None
            transition = self._transition(policy, state.automatically_shed, soc)
            if transition is None:
                self._streaks[policy.name] = (None, 0)
                return None
            previous_transition, count = self._streaks.get(policy.name, (None, 0))
            count = count + 1 if previous_transition is transition else 1
            self._streaks[policy.name] = (transition, count)
            if count < self.confirmation_required:
                return None
            desired = transition is PendingTransition.RESTORE
            if breaker.status.switch_on is desired:
                if transition is PendingTransition.RESTORE and state.automatically_shed:
                    self._record_success(state, transition)
                self._streaks[policy.name] = (None, 0)
                return None
            result = self.control_factory(session, self.breakers).execute(
                request_id=str(uuid.uuid4()), breaker_id=policy.breaker_id or "", action="switch",
                requested_value=desired, user=None,
                reason=f"Automatic battery SOC {transition.value} policy",
                client_ip=None, system_actor="battery_load_shedding",
                audit_details={"automation": "battery_load_shedding", "soc": soc,
                    "threshold": policy.shed_soc if transition is PendingTransition.SHED else policy.restore_soc,
                    "transition": transition.value, "policy": policy.name},
            )
            verified = result.status is CommandStatus.SUCCEEDED and result.data.get("verified_value") is desired
            if verified:
                self._record_success(state, transition)
                self._streaks[policy.name] = (None, 0)
                logger.info("Load management transition verified for policy %s", policy.name)
                return ("load_management.shed" if transition is PendingTransition.SHED else "load_management.restored", self._event(policy, soc, transition, True))
            state.last_error = result.message or "Breaker command was not verified"
            return ("load_management.action_failed", self._event(policy, soc, transition, False))

    def _state(self, session: Session, policy: LoadSheddingPolicy):
        device = session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == policy.breaker_id))
        if device is None:
            raise BreakerNotFoundError("Configured load-management breaker is not registered")
        state = session.scalar(select(LoadSheddingStateRecord).where(LoadSheddingStateRecord.policy_name == policy.name))
        if state is None:
            state = LoadSheddingStateRecord(policy_name=policy.name, device_id=device.id)
            session.add(state)
            session.flush()
        elif state.device_id != device.id:
            state.device_id = device.id
            state.automatically_shed = False
            state.last_transition = None
            state.last_transition_at = None
        return state, device

    def _policy_status(self, session: Session, policy: LoadSheddingPolicy) -> LoadPolicyStatus:
        state = session.scalar(select(LoadSheddingStateRecord).where(LoadSheddingStateRecord.policy_name == policy.name))
        transition, count = self._streaks.get(policy.name, (None, 0))
        online, relay = self._breaker_states.get(policy.name, (None, None))
        area = None
        error = state.last_error if state else None
        enabled = self.enabled and bool(policy.breaker_id)
        if policy.breaker_id:
            device = session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == policy.breaker_id))
            area = device.area.name if device and device.area else None
            if policy.breaker_id not in self.breakers.registered_breaker_ids:
                enabled = False
                error = "Configured breaker is unavailable"
        return LoadPolicyStatus(
            policy_name=policy.name, breaker_id=policy.breaker_id, display_name=policy.display_name,
            area=area, enabled=enabled, shed_soc=policy.shed_soc, restore_soc=policy.restore_soc,
            current_soc=self._current_soc, breaker_online=online, relay_on=relay,
            automatically_shed=state.automatically_shed if state else False,
            pending_transition=transition, confirmation_count=count,
            confirmation_required=self.confirmation_required,
            last_transition=state.last_transition if state else None,
            last_transition_at=state.last_transition_at if state else None, last_error=error,
        )

    @staticmethod
    def _transition(policy, automatically_shed, soc):
        if soc <= policy.shed_soc:
            return PendingTransition.SHED
        if automatically_shed and soc >= policy.restore_soc:
            return PendingTransition.RESTORE
        return None

    def _record_success(self, state, transition):
        state.automatically_shed = transition is PendingTransition.SHED
        state.last_transition = transition.value
        state.last_transition_at = self.clock()
        state.last_error = None

    def _set_error(self, policy, message):
        try:
            with session_scope(self.session_factory) as session:
                state, _ = self._state(session, policy)
                state.last_error = message
        except Exception:
            return

    def _event(self, policy, soc, transition, verified):
        return {"policy": policy.name, "device_id": policy.breaker_id, "soc": soc,
                "transition": transition.value if transition else None, "verified": verified,
                "timestamp": self.clock()}

    @staticmethod
    def _valid_soc(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100
