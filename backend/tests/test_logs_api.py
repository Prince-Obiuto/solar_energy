"""Presentation-safe activity log tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from apps.api.logs import list_logs
from apps.db.base import Base
from apps.models.persistence import AreaRecord, ControlEventRecord, DeviceRecord, SystemEventRecord


@pytest.mark.asyncio
async def test_control_and_system_levels_are_normalized_without_losing_status() -> None:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        area = AreaRecord(name="Admin offices")
        device = DeviceRecord(external_reference="log-breaker", friendly_name="Admin Office", device_type="breaker", area=area)
        session.add_all([area, device]); session.flush()
        for status in ("running", "succeeded", "failed", "timed_out", "rejected"):
            session.add(ControlEventRecord(command="switch", action="switch", status=status,
                device_id=device.id, area_id=area.id, requested_by="admin@example.test", role="admin",
                previous_value=True, requested_value=False, verified_value=False,
                reason="Approved maintenance", error_information="Failed" if status == "failed" else None))
        for severity in ("debug", "healthy", "warn", "critical", "future"):
            session.add(SystemEventRecord(category="system.test", severity=severity, message="Test"))
    with factory() as session:
        response = await list_logs(limit=20, session=session)
    assert {item["level"] for item in response["items"]} <= {"info", "success", "warning", "error"}
    control = [item for item in response["items"] if item["category"] == "Controls"]
    assert {item["raw_status"] for item in control} == {"running", "succeeded", "failed", "timed_out", "rejected"}
    succeeded = next(item for item in control if item["raw_status"] == "succeeded")
    assert succeeded["title"] == "Admin Office — Turned OFF"
    assert succeeded["device"] == "Admin Office" and succeeded["area"] == "Admin offices"
    assert succeeded["previous_value"] is True and succeeded["verified_value"] is False
