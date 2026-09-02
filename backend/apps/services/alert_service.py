"""Persistent alert lifecycle with active-alert deduplication."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.models.persistence import AlertRecord, AreaRecord, DeviceRecord, UserRecord
from apps.realtime.manager import sanitize_payload
from apps.schemas.alert import AlertList, AlertSeverity, AlertView


class AlertNotFoundError(LookupError):
    pass


class AlertService:
    def __init__(self, session: Session, *, clock=None) -> None:
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))

    def raise_alert(
        self,
        *,
        dedup_key: str,
        category: str,
        severity: AlertSeverity,
        message: str,
        device_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[AlertRecord, bool]:
        now = self.clock()
        existing = self.session.scalar(
            select(AlertRecord).where(AlertRecord.dedup_key == dedup_key, AlertRecord.active.is_(True))
        )
        clean_metadata = sanitize_payload(metadata or {})
        if existing is not None:
            existing.last_seen = now
            existing.timestamp = now
            existing.message = message
            existing.alert_metadata = clean_metadata
            return existing, False
        device = None
        if device_reference:
            device = self.session.scalar(select(DeviceRecord).where(DeviceRecord.external_reference == device_reference))
        alert = AlertRecord(
            id=uuid.uuid4(), timestamp=now, first_seen=now, last_seen=now,
            severity=severity.value, title=category.replace(".", " ").title(),
            message=message, active=True, category=category, dedup_key=dedup_key,
            device_id=device.id if device else None, area_id=device.area_id if device else None,
            alert_metadata=clean_metadata,
        )
        self.session.add(alert)
        self.session.flush()
        return alert, True

    def resolve(self, dedup_key: str) -> AlertRecord | None:
        alert = self.session.scalar(
            select(AlertRecord).where(AlertRecord.dedup_key == dedup_key, AlertRecord.active.is_(True))
        )
        if alert is not None:
            now = self.clock()
            alert.active = False
            alert.resolved_at = now
            alert.last_seen = now
        return alert

    def acknowledge(self, alert_id: uuid.UUID, user: UserRecord) -> AlertRecord:
        alert = self.session.get(AlertRecord, alert_id)
        if alert is None:
            raise AlertNotFoundError
        if alert.acknowledged_at is None:
            alert.acknowledged_at = self.clock()
            alert.acknowledged_by = user.id
        return alert

    def list_alerts(
        self,
        *,
        active: bool | None = True,
        severity: AlertSeverity | None = None,
        category: str | None = None,
        device_id: str | None = None,
        area_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> AlertList:
        statement = (
            select(AlertRecord, DeviceRecord.external_reference, AreaRecord.name)
            .outerjoin(DeviceRecord, AlertRecord.device_id == DeviceRecord.id)
            .outerjoin(AreaRecord, AlertRecord.area_id == AreaRecord.id)
            .order_by(AlertRecord.last_seen.desc(), AlertRecord.timestamp.desc())
            .limit(limit)
        )
        if active is not None:
            statement = statement.where(AlertRecord.active.is_(active))
        if severity is not None:
            statement = statement.where(AlertRecord.severity == severity.value)
        if category is not None:
            statement = statement.where(AlertRecord.category == category)
        if device_id is not None:
            statement = statement.where(DeviceRecord.external_reference == device_id)
        if area_id is not None:
            statement = statement.where(AlertRecord.area_id == area_id)
        items = [self._view(*row) for row in self.session.execute(statement).all()]
        return AlertList(items=items, total=len(items))

    def get_alert(self, alert_id: uuid.UUID) -> AlertView:
        row = self.session.execute(
            select(AlertRecord, DeviceRecord.external_reference, AreaRecord.name)
            .outerjoin(DeviceRecord, AlertRecord.device_id == DeviceRecord.id)
            .outerjoin(AreaRecord, AlertRecord.area_id == AreaRecord.id)
            .where(AlertRecord.id == alert_id)
        ).one_or_none()
        if row is None:
            raise AlertNotFoundError
        return self._view(*row)

    def view(self, alert: AlertRecord) -> AlertView:
        device_reference = None
        area_name = None
        if alert.device_id:
            device = self.session.get(DeviceRecord, alert.device_id)
            device_reference = device.external_reference if device else None
        if alert.area_id:
            area = self.session.get(AreaRecord, alert.area_id)
            area_name = area.name if area else None
        return self._view(alert, device_reference, area_name)

    @staticmethod
    def _view(alert: AlertRecord, device_reference: str | None, area_name: str | None) -> AlertView:
        first_seen = alert.first_seen or alert.timestamp
        last_seen = alert.last_seen or alert.timestamp
        return AlertView(
            id=alert.id, severity=alert.severity, first_seen=first_seen, last_seen=last_seen,
            resolved_at=alert.resolved_at, acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by, device=device_reference, area=area_name,
            category=alert.category or "uncategorized", message=alert.message,
            metadata=alert.alert_metadata or {},
        )
