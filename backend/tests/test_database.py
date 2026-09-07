"""Database model, transaction, index, and migration tests."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import sessionmaker

from apps.db.base import Base
from apps.db.session import session_scope
from apps.integrations.inverter import InverterAdapter, MockBeveClient
from apps.jobs.energy_collector import SQLAlchemyTelemetryPersistence
from apps.models import BreakerDevice, BreakerStatus, DeviceCapability, DeviceStatus
from apps.models.persistence import (
    AlertRecord,
    AreaRecord,
    BatteryReadingRecord,
    BreakerReadingRecord,
    ControlEventRecord,
    DeviceRecord,
    GridReadingRecord,
    InverterReadingRecord,
    SolarReadingRecord,
    SystemEventRecord,
)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_models_persist_normalized_readings_and_retain_zero_and_null(db_engine) -> None:
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    timestamp = datetime(2026, 9, 1, 12, 19, 6, tzinfo=UTC)

    with session_scope(Session) as session:
        area = AreaRecord(name="Test area")
        inverter = DeviceRecord(
            external_reference="inverter-external-test",
            friendly_name="Test inverter",
            device_type="inverter",
            area=area,
            manufacturer="FiveStar",
            model="Hybrid inverter",
            protocol="BEVE",
        )
        breaker = DeviceRecord(
            external_reference="breaker-external-test",
            friendly_name="Test breaker",
            device_type="breaker",
            area=area,
            manufacturer="Tuya",
            model="TMPH",
            protocol="3.5",
        )
        session.add_all([inverter, breaker])
        session.flush()
        session.add_all(
            [
                InverterReadingRecord(
                    timestamp=timestamp, device_id=inverter.id, status="Battery Mode",
                    rated_power_w=6000, output_voltage=219.9, output_frequency=50,
                    output_power_w=12, load_percentage=0,
                ),
                BatteryReadingRecord(
                    timestamp=timestamp, device_id=inverter.id, soc=100, voltage=53.4,
                    charging_current=0, discharge_current=1, power_w=61,
                    status="Discharging Status", charge_stage="No Charging",
                    battery_type="PYLON_485",
                ),
                SolarReadingRecord(
                    timestamp=timestamp, device_id=inverter.id, connected="PV Not Connected",
                    pv1_voltage=0, pv1_power_w=0, pv2_voltage=None, pv2_power_w=None,
                    total_power_w=0, daily_energy_kwh=0, monthly_energy_kwh=0,
                    total_energy_kwh=8,
                ),
                GridReadingRecord(
                    timestamp=timestamp, device_id=inverter.id, voltage=0,
                    frequency=0, power_w=0,
                ),
                BreakerReadingRecord(
                    timestamp=timestamp, device_id=breaker.id, online=True,
                    switch_state=True, voltage_v=None, current_a=0, power_w=0,
                    accumulated_energy=12.5, raw_datapoints={"test": 0},
                ),
            ]
        )

    with Session() as session:
        grid = session.scalar(select(GridReadingRecord))
        solar = session.scalar(select(SolarReadingRecord))
        breaker_reading = session.scalar(select(BreakerReadingRecord))

        assert grid is not None and grid.voltage == 0 and grid.timestamp.tzinfo is UTC
        assert solar is not None and solar.pv1_power_w == 0 and solar.pv2_voltage is None
        assert breaker_reading is not None
        assert breaker_reading.accumulated_energy == 12.5
        assert "total_energy_kwh" not in BreakerReadingRecord.__table__.columns


def test_events_alerts_and_nullable_device_foreign_keys(db_engine) -> None:
    Session = sessionmaker(bind=db_engine)
    now = datetime.now(UTC)

    with session_scope(Session) as session:
        session.add_all(
            [
                ControlEventRecord(timestamp=now, command="test", status="succeeded"),
                SystemEventRecord(
                    timestamp=now, category="system", severity="info", message="test event"
                ),
                AlertRecord(
                    timestamp=now, severity="warning", title="Test alert", message="test"
                ),
            ]
        )

    with Session() as session:
        assert session.scalar(select(ControlEventRecord)) is not None
        assert session.scalar(select(SystemEventRecord)) is not None
        assert session.scalar(select(AlertRecord)) is not None


def test_foreign_keys_and_timezone_awareness_are_enforced(db_engine) -> None:
    Session = sessionmaker(bind=db_engine)
    with pytest.raises(IntegrityError):
        with session_scope(Session) as session:
            session.add(
                GridReadingRecord(
                    timestamp=datetime.now(UTC),
                    device_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                )
            )

    with session_scope(Session) as session:
        device = DeviceRecord(
            external_reference="timezone-test",
            friendly_name="Timezone test",
            device_type="inverter",
        )
        session.add(device)
        session.flush()
        device_id = device.id

    with pytest.raises(StatementError):
        with session_scope(Session) as session:
            session.add(GridReadingRecord(timestamp=datetime(2026, 9, 1), device_id=device_id))


def test_transaction_scope_rolls_back_on_failure(db_engine) -> None:
    Session = sessionmaker(bind=db_engine)

    with pytest.raises(RuntimeError):
        with session_scope(Session) as session:
            session.add(AreaRecord(name="Rolled back area"))
            raise RuntimeError("force rollback")

    with Session() as session:
        assert session.scalar(select(AreaRecord)) is None


def test_device_table_has_no_plaintext_secret_columns() -> None:
    columns = set(DeviceRecord.__table__.columns.keys())
    forbidden = {"password", "local_key", "secret", "token", "api_key"}

    assert columns.isdisjoint(forbidden)


def test_historical_report_indexes_exist() -> None:
    expected = {
        "ix_inverter_readings_device_timestamp",
        "ix_battery_readings_device_timestamp",
        "ix_solar_readings_device_timestamp",
        "ix_grid_readings_device_timestamp",
        "ix_breaker_readings_device_timestamp",
    }
    actual = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert expected <= actual


def test_collector_persistence_writes_normalized_snapshots(db_engine) -> None:
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    with session_scope(Session) as session:
        inverter = DeviceRecord(
            external_reference="collector-inverter",
            friendly_name="Collector inverter",
            device_type="inverter",
        )
        breaker = DeviceRecord(
            external_reference="collector-breaker",
            friendly_name="Collector breaker",
            device_type="breaker",
        )
        session.add_all([inverter, breaker])

    repository = SQLAlchemyTelemetryPersistence(Session)
    inverter_telemetry = InverterAdapter().read(MockBeveClient())
    collected_at = datetime(2026, 9, 1, 12, 20, tzinfo=UTC)
    breaker_telemetry = BreakerDevice(
        id="collector-breaker",
        friendly_name="Collector breaker",
        area="Test area",
        online=True,
        last_seen=collected_at,
        capabilities=DeviceCapability(),
        status=BreakerStatus(
            device_id="collector-breaker",
            status=DeviceStatus.ONLINE,
            switch_on=True,
        ),
    )

    repository.persist_inverter("collector-inverter", inverter_telemetry)
    repository.persist_breaker("collector-breaker", breaker_telemetry, collected_at)

    with Session() as session:
        assert len(session.scalars(select(InverterReadingRecord)).all()) == 1
        assert len(session.scalars(select(BatteryReadingRecord)).all()) == 1
        assert len(session.scalars(select(SolarReadingRecord)).all()) == 1
        assert len(session.scalars(select(GridReadingRecord)).all()) == 1
        assert len(session.scalars(select(BreakerReadingRecord)).all()) == 1
        stored_breaker = session.scalar(
            select(DeviceRecord).where(DeviceRecord.external_reference == "collector-breaker")
        )
        assert stored_breaker is not None and stored_breaker.last_seen == collected_at


def test_alembic_upgrade_and_downgrade(tmp_path) -> None:
    database_path = tmp_path / "migration-test.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    required_tables = {
        "areas", "devices", "inverter_readings", "battery_readings", "solar_readings",
        "grid_readings", "breaker_readings", "control_events", "system_events", "alerts", "users",
        "backup_runs", "installation_state",
        "runtime_configuration",
    }
    assert required_tables <= set(inspect(engine).get_table_names())
    installation_columns = {
        column["name"] for column in inspect(engine).get_columns("installation_state")
    }
    assert {"created_at", "updated_at", "setup_token_hash"} <= installation_columns
    runtime_columns = {
        column["name"] for column in inspect(engine).get_columns("runtime_configuration")
    }
    assert {
        "id", "namespace", "key", "value", "is_secret", "created_at", "updated_at"
    } == runtime_columns
    assert any(
        set(constraint["column_names"]) == {"namespace", "key"}
        for constraint in inspect(engine).get_unique_constraints("runtime_configuration")
    )

    command.downgrade(config, "base")
    assert required_tables.isdisjoint(inspect(engine).get_table_names())
    engine.dispose()


def test_installation_migration_preserves_existing_users_and_disables_first_admin(
    tmp_path,
) -> None:
    database_path = tmp_path / "existing-installation.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "20260902_06")

    engine = create_engine(f"sqlite:///{database_path}")
    metadata = MetaData()
    users = Table("users", metadata, autoload_with=engine)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(users.insert().values(
            id=uuid.uuid4().hex,
            email="existing-admin@example.test",
            full_name="Existing Admin",
            password_hash="not-a-real-login-hash",
            role="admin",
            is_active=True,
            created_at=now,
            updated_at=now,
        ))

    command.upgrade(config, "head")
    migrated = MetaData()
    installation = Table("installation_state", migrated, autoload_with=engine)
    users_after = Table("users", migrated, autoload_with=engine)
    with engine.connect() as connection:
        state = connection.execute(select(installation)).mappings().one()
        assert state["id"] == 1
        assert state["setup_initialized"] is True
        assert state["admin_configured"] is True
        assert state["setup_token_hash"] is None
        assert connection.scalar(select(func.count()).select_from(users_after)) == 1

    command.downgrade(config, "20260902_06")
    assert "installation_state" not in inspect(engine).get_table_names()
    assert "users" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(users_after)) == 1
    engine.dispose()
