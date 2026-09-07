"""Persistent runtime configuration, resolution, and secret-safety tests."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from apps.core.config import Settings
from apps.db.base import Base
from apps.models.persistence import RuntimeConfigurationRecord, SystemEventRecord
from apps.security.runtime_secrets import (
    InvalidRuntimeCiphertextError,
    RuntimeMasterKeyMissingError,
    initialize_runtime_master_key,
)
from apps.services.runtime_configuration_service import (
    ConfigurationSource,
    RuntimeConfigurationService,
    RuntimeSecretClassificationError,
    is_secret_configuration_key,
)


@pytest.fixture
def runtime_context(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    key_file = tmp_path / "master.key"
    initialize_runtime_master_key(key_file)
    try:
        yield factory, key_file
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def environment(**updates) -> Settings:
    values = {
        "app_env": "test",
        "beve_username": None,
        "beve_password": None,
        "beve_station_id": None,
        "beve_device_id": None,
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


def test_non_secret_and_encrypted_secret_roundtrip(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        service.set_non_secret("beve", "station_id", "station-test")
        secret_record = service.set_secret("beve", "password", "dummy-secret")
        session.commit()

        assert service.get_setting("beve", "station_id") == "station-test"
        assert service.get_setting("beve", "password") == "dummy-secret"
        assert secret_record.value != "dummy-secret"
        assert "dummy-secret" not in secret_record.value
        assert secret_record.is_secret is True


def test_namespace_key_is_unique_and_write_updates_existing(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        first = service.set_non_secret("system", "site_name", "First")
        second = service.set_non_secret("system", "site_name", "Updated")
        session.commit()

        assert first.id == second.id
        assert service.get_setting("system", "site_name") == "Updated"
        assert session.scalar(select(func.count()).select_from(RuntimeConfigurationRecord)) == 1


@pytest.mark.parametrize(
    ("namespace", "key"),
    [
        ("beve", "username"),
        ("beve", "password"),
        ("tuya_cloud", "access_id"),
        ("tuya_cloud", "access_secret"),
        ("tuya_devices", "device-1.local_key"),
    ],
)
def test_known_credentials_cannot_be_stored_as_plaintext(
    runtime_context, namespace, key
) -> None:
    factory, key_file = runtime_context
    assert is_secret_configuration_key(namespace, key) is True
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        with pytest.raises(RuntimeSecretClassificationError, match="encrypted"):
            service.set_non_secret(namespace, key, "dummy-secret")
        assert session.scalar(select(RuntimeConfigurationRecord)) is None


def test_beve_environment_fallback_is_typed_and_secret_safe(runtime_context) -> None:
    factory, key_file = runtime_context
    configured_environment = environment(
        beve_username=SecretStr("environment-user"),
        beve_password=SecretStr("environment-password"),
        beve_station_id="environment-station",
        beve_device_id="environment-device",
    )
    with factory() as session:
        resolved = RuntimeConfigurationService(
            session,
            environment=configured_environment,
        ).get_beve_configuration()

        assert resolved.configured is True
        assert resolved.username.get_secret_value() == "environment-user"
        assert resolved.password.get_secret_value() == "environment-password"
        assert resolved.sources["password"] == ConfigurationSource.ENVIRONMENT
        assert "environment-password" not in repr(resolved)
        assert "environment-password" not in resolved.model_dump_json()


def test_persisted_beve_values_override_environment(runtime_context) -> None:
    factory, key_file = runtime_context
    configured_environment = environment(
        beve_username=SecretStr("environment-user"),
        beve_password=SecretStr("environment-password"),
        beve_station_id="environment-station",
        beve_device_id="environment-device",
    )
    with factory() as session:
        service = RuntimeConfigurationService(
            session,
            environment=configured_environment,
            master_key_file=str(key_file),
        )
        service.set_secret("beve", "password", "persisted-password")
        service.set_non_secret("beve", "device_id", "persisted-device")
        session.commit()

        resolved = service.get_beve_configuration()
        assert resolved.password.get_secret_value() == "persisted-password"
        assert resolved.device_id == "persisted-device"
        assert resolved.station_id == "environment-station"
        assert resolved.sources["password"] == ConfigurationSource.PERSISTED
        assert resolved.sources["station_id"] == ConfigurationSource.ENVIRONMENT


def test_missing_configuration_has_explicit_status(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(
            session,
            environment=environment(),
            master_key_file=str(key_file),
        )
        resolved = service.get_beve_configuration()
        status = service.get_namespace_status("beve")

        assert resolved.configured is False
        assert set(resolved.missing_fields) == {
            "username", "password", "station_id", "device_id"
        }
        assert resolved.sources["password"] == ConfigurationSource.MISSING
        assert status.configured is False
        assert status.fields["password"].model_dump() == {
            "configured": False,
            "source": ConfigurationSource.MISSING,
            "secret": True,
        }


def test_missing_key_does_not_fall_back_over_persisted_secret(runtime_context, tmp_path) -> None:
    factory, key_file = runtime_context
    configured_environment = environment(
        beve_username=SecretStr("environment-user"),
        beve_password=SecretStr("environment-password"),
        beve_station_id="environment-station",
        beve_device_id="environment-device",
    )
    with factory() as session:
        writer = RuntimeConfigurationService(session, master_key_file=str(key_file))
        writer.set_secret("beve", "password", "persisted-password")
        session.commit()

        reader = RuntimeConfigurationService(
            session,
            environment=configured_environment,
            master_key_file=str(tmp_path / "missing.key"),
        )
        status = reader.get_namespace_status("beve")
        assert status.fields["password"].source == ConfigurationSource.PERSISTED
        with pytest.raises(RuntimeMasterKeyMissingError, match="missing") as error:
            reader.get_beve_configuration()
        assert "persisted-password" not in str(error.value)
        assert "environment-password" not in str(error.value)


def test_corrupted_ciphertext_is_not_returned_or_overwritten(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        record = service.set_secret("beve", "password", "dummy-secret")
        record.value = "corrupted-ciphertext"
        session.commit()

        with pytest.raises(InvalidRuntimeCiphertextError, match="invalid") as error:
            service.get_setting("beve", "password")
        assert "corrupted-ciphertext" not in str(error.value)
        assert session.get(RuntimeConfigurationRecord, record.id).value == "corrupted-ciphertext"


def test_metadata_and_audit_events_never_serialize_values(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        service.set_secret("beve", "password", "dummy-secret", actor_id="test-admin")
        status = service.get_namespace_status("beve")
        event = session.scalar(
            select(SystemEventRecord).where(
                SystemEventRecord.category == "installation.configuration"
            )
        )
        serialized_status = status.model_dump_json()
        serialized_event = json.dumps(event.details)

        assert "dummy-secret" not in serialized_status
        assert "dummy-secret" not in serialized_event
        assert event.details == {
            "namespace": "beve",
            "changed_keys": ["password"],
            "action": "created",
            "secret": True,
            "actor_id": "test-admin",
        }


def test_caller_transaction_rollback_removes_setting_and_audit(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        service.set_non_secret("system", "site_name", "Temporary")
        session.rollback()

        assert session.scalar(select(RuntimeConfigurationRecord)) is None
        assert session.scalar(select(SystemEventRecord)) is None


def test_delete_setting_removes_value_and_records_safe_audit(runtime_context) -> None:
    factory, key_file = runtime_context
    with factory() as session:
        service = RuntimeConfigurationService(session, master_key_file=str(key_file))
        service.set_non_secret("system", "site_name", "Test site")
        assert service.delete_setting("system", "site_name") is True
        assert service.delete_setting("system", "site_name") is False
        session.commit()

        assert service.get_setting("system", "site_name") is None
        deleted = session.scalar(
            select(SystemEventRecord).where(
                SystemEventRecord.message == "system runtime configuration deleted"
            )
        )
        assert deleted is not None
        assert "Test site" not in json.dumps(deleted.details)
