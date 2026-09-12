"""Tuya cloud/LAN onboarding, verification, persistence, and API tests."""

from __future__ import annotations

import json
from collections import deque

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.setup import (
    get_runtime_configuration_service,
    get_tuya_cloud_gateway,
    get_tuya_lan_discovery,
    get_tuya_onboarding_store,
    get_tuya_setup_client_factory,
    setup_limiter,
)
from apps.core.config import Settings
from apps.db.base import Base
from apps.db.session import get_db
from apps.integrations.tuya.client import (
    TuyaCommunicationError,
    TuyaDeviceConfig,
    TuyaMalformedResponseError,
    TuyaTimeoutError,
)
from apps.integrations.tuya.onboarding import (
    TinyTuyaCloudGateway,
    TinyTuyaLanDiscovery,
    TuyaCloudAuthenticationError,
    TuyaCloudConfig,
    TuyaCloudConfigurationError,
    TuyaCloudDevice,
    TuyaCloudDeviceFetchError,
    TuyaCloudMalformedResponseError,
    TuyaCloudNetworkError,
    TuyaCloudTimeoutError,
    TuyaLanDevice,
)
from apps.main import app
from apps.models.persistence import InstallationStateRecord, RuntimeConfigurationRecord
from apps.schemas.setup import (
    TuyaCloudSetupRequest,
    TuyaDeviceConfigurationRequest,
)
from apps.security.runtime_secrets import initialize_runtime_master_key
from apps.services.runtime_configuration_service import RuntimeConfigurationService
from apps.services.runtime_configuration_service import RuntimeConfigurationError
from apps.services.setup_service import SetupService, SetupStateError
from apps.services.tuya_onboarding_store import TuyaOnboardingStore
from apps.services.tuya_setup_service import (
    TuyaScanInProgressError,
    TuyaSetupService,
    _TUYA_SCAN_LOCK,
)


LOCAL_KEY_ONE = "fake-local-key-one-not-real"
LOCAL_KEY_TWO = "fake-local-key-two-not-real"
STATUS_ON_ZERO = {"dps": {"1": True, "17": 0, "18": 0, "19": 0, "20": 2300}}
STATUS_OFF = {"dps": {"1": False, "18": 125, "19": 315, "20": 2294}}


class FakeCloudObject:
    def __init__(self, response, **kwargs) -> None:
        self.response = response
        self.arguments = kwargs
        self.apiKey = kwargs.get("apiKey")
        self.apiSecret = kwargs.get("apiSecret")
        self.apiDeviceID = kwargs.get("apiDeviceID")
        self.token = "temporary-cloud-token"

    def getdevices(self):
        return self.response


class FakeCloudFactory:
    def __init__(self, response) -> None:
        self.response = response
        self.instances = []

    def __call__(self, **kwargs):
        cloud = FakeCloudObject(self.response, **kwargs)
        self.instances.append(cloud)
        return cloud


class FakeCloudGateway:
    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def get_devices(self, _config):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeDiscovery:
    def __init__(self, scanned=None, found=None) -> None:
        self.scanned = scanned or {}
        self.found = found or {}
        self.scan_calls = []
        self.find_calls = []

    def scan(self, *, maxretry):
        self.scan_calls.append(maxretry)
        if isinstance(self.scanned, BaseException):
            raise self.scanned
        return self.scanned

    def find_exact(self, device_id):
        self.find_calls.append(device_id)
        return self.found.get(device_id)


class FakeLocalClient:
    def __init__(self, config, outcome) -> None:
        self.config = config
        self.outcome = outcome
        self.closed = False
        self.write_calls = []

    def read_status(self):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def write_datapoint(self, *args):
        self.write_calls.append(args)
        raise AssertionError("Onboarding must not write datapoints")

    def set_switch_state(self, *args):
        self.write_calls.append(args)
        raise AssertionError("Onboarding must not switch relays")

    def close(self):
        self.closed = True


class FakeLocalFactory:
    def __init__(self, *outcomes) -> None:
        self.outcomes = deque(outcomes)
        self.clients = []

    def __call__(self, config):
        outcome = self.outcomes.popleft() if len(self.outcomes) > 1 else self.outcomes[0]
        client = FakeLocalClient(config, outcome)
        self.clients.append(client)
        return client


@pytest.fixture(autouse=True)
def isolate_tuya_rate_limits():
    for operation in ("tuya-cloud", "tuya-scan", "tuya-devices"):
        setup_limiter.reset(f"{operation}:testclient")
    yield
    for operation in ("tuya-cloud", "tuya-scan", "tuya-devices"):
        setup_limiter.reset(f"{operation}:testclient")


@pytest.fixture
def tuya_setup_context(tmp_path):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    key_file = tmp_path / "master.key"
    initialize_runtime_master_key(key_file)
    environment = Settings(
        _env_file=None,
        app_env="test",
        runtime_master_key_file=key_file,
        tuya_device_file=tmp_path / "missing-devices.json",
        tuya_onboarding_scan_maxretry=2,
        beve_username=None,
        beve_password=None,
        beve_station_id=None,
        beve_device_id=None,
    )
    try:
        yield sessions, key_file, environment
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def authorize_tuya(sessions) -> str:
    with sessions() as session:
        setup = SetupService(session)
        code = setup.initialize()
        state = setup.get_state()
        state.admin_configured = True
        state.beve_configured = True
        session.commit()
        return code


def candidates(include_missing_key=False):
    return [
        TuyaCloudDevice(
            device_id="cloud-device-one",
            local_key=SecretStr(LOCAL_KEY_ONE),
            name="Same breaker name",
            product_id="ruqchkg5f9loztw2",
            category="znjdq",
            model="TMPH",
            online=True,
            protocol_version="3.5",
        ),
        TuyaCloudDevice(
            device_id="cloud-device-two",
            local_key=None if include_missing_key else SecretStr(LOCAL_KEY_TWO),
            name="Same breaker name",
            product_id="different-future-product",
            category="znjdq",
            model="TMPH",
            online=False,
            protocol_version="3.5",
        ),
    ]


def cloud_payload(code):
    return TuyaCloudSetupRequest(
        setup_code=code,
        region="eu",
        access_id="fake-access-id-not-real",
        access_secret="fake-access-secret-not-real",
        anchor_device_id="fake-anchor-device",
    )


def build_service(session, key_file, environment, store, cloud, discovery, local):
    return TuyaSetupService(
        session,
        RuntimeConfigurationService(
            session,
            environment=environment,
            master_key_file=str(key_file),
        ),
        store,
        cloud_gateway=cloud,
        lan_discovery=discovery,
        client_factory=local,
        environment=environment,
    )


def scanned_devices():
    return {
        "cloud-device-one": TuyaLanDevice(
            "cloud-device-one", "192.0.2.31", "3.5", "ruqchkg5f9loztw2"
        ),
        "cloud-device-two": TuyaLanDevice(
            "cloud-device-two", "192.0.2.32", "3.5", "different-future-product"
        ),
        "unrelated-device": TuyaLanDevice(
            "unrelated-device", "192.0.2.99", "3.3", None
        ),
    }


def configure_payload(code, token, refs):
    return TuyaDeviceConfigurationRequest(
        setup_code=code,
        onboarding_session=token,
        devices=[
            {
                "device_ref": refs[0],
                "friendly_name": "Library",
                "area": "Library",
            },
            {
                "device_ref": refs[1],
                "friendly_name": "Admin offices",
                "area": "Admin offices",
            },
        ],
    )


def test_cloud_gateway_uses_installed_api_contract_and_erases_credentials() -> None:
    factory = FakeCloudFactory([
        {
            "id": "device-one",
            "key": LOCAL_KEY_ONE,
            "name": "Breaker",
            "product_id": "product",
            "category": "znjdq",
            "version": "3.5",
        }
    ])
    gateway = TinyTuyaCloudGateway(factory)
    config = TuyaCloudConfig(
        region="eu",
        access_id="temporary-access-id",
        access_secret="temporary-access-secret",
        anchor_device_id="anchor-device",
    )

    devices = gateway.get_devices(config)

    assert devices[0].device_id == "device-one"
    assert devices[0].local_key.get_secret_value() == LOCAL_KEY_ONE
    assert repr(devices[0]) == "TuyaCloudDevice(<redacted>)"
    cloud = factory.instances[0]
    assert cloud.arguments == {
        "apiRegion": "eu",
        "apiKey": "temporary-access-id",
        "apiSecret": "temporary-access-secret",
        "apiDeviceID": "anchor-device",
    }
    assert cloud.apiKey is cloud.apiSecret is cloud.apiDeviceID is cloud.token is None


@pytest.mark.parametrize("code", ["909", "911"])
def test_cloud_authentication_errors_are_normalized(code) -> None:
    gateway = TinyTuyaCloudGateway(FakeCloudFactory({"Error": "unsafe", "Err": code}))
    with pytest.raises(TuyaCloudAuthenticationError) as captured:
        gateway.get_devices(TuyaCloudConfig(
            region="us",
            access_id="id",
            access_secret="secret-value",
        ))
    assert "secret-value" not in str(captured.value)
    assert "unsafe" not in str(captured.value)


def test_cloud_device_without_local_key_is_retained_but_not_configurable() -> None:
    gateway = TinyTuyaCloudGateway(FakeCloudFactory([
        {"id": "device-one", "key": "", "name": "Breaker"}
    ]))
    device = gateway.get_devices(TuyaCloudConfig(
        region="eu", access_id="id", access_secret="secret"
    ))[0]
    assert device.local_key is None


@pytest.mark.parametrize(
    ("outcome", "category"),
    [
        (TuyaCloudAuthenticationError("unsafe"), "cloud_authentication_failed"),
        (TuyaCloudConfigurationError("unsafe"), "cloud_configuration_invalid"),
        (TuyaCloudNetworkError("unsafe"), "network_error"),
        (TuyaCloudTimeoutError("unsafe"), "timeout"),
        (TuyaCloudMalformedResponseError("unsafe"), "cloud_malformed_response"),
        (TuyaCloudDeviceFetchError("unsafe"), "cloud_device_fetch_failed"),
    ],
)
def test_cloud_failures_have_safe_categories_and_no_session(
    tuya_setup_context, outcome, category
) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        result = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(outcome), FakeDiscovery(), FakeLocalFactory(STATUS_ON_ZERO),
        ).retrieve_cloud_devices(cloud_payload(code))
        assert result.success is False and result.category == category
        assert "unsafe" not in result.message
        assert result.onboarding_session is None
        assert store.active_session_count == 0


def test_onboarding_store_expires_and_bounds_secret_sessions() -> None:
    now = [100.0]
    store = TuyaOnboardingStore(
        ttl_seconds=10,
        max_sessions=1,
        monotonic=lambda: now[0],
    )
    first_token, first = store.create(candidates()[:1])
    second_token, _ = store.create(candidates()[1:])
    assert first.candidates == {}
    assert store.get(second_token)
    now[0] = 111
    with pytest.raises(Exception, match="invalid or expired"):
        store.get(second_token)
    assert store.active_session_count == 0
    assert first_token != second_token


def test_lan_discovery_uses_direct_scan_and_exact_find_contract() -> None:
    calls = []

    def scan(**kwargs):
        calls.append(kwargs)
        return {
            "192.0.2.40": {"gwId": "exact-device", "version": "3.5"},
            "wrong-name-is-irrelevant": {
                "gwId": "different-device", "ip": "192.0.2.41", "version": "3.3"
            },
        }

    find_calls = []

    def find(**kwargs):
        find_calls.append(kwargs)
        return {"id": kwargs["dev_id"], "ip": "192.0.2.55", "version": "3.5"}

    discovery = TinyTuyaLanDiscovery(scan=scan, find=find)
    result = discovery.scan(maxretry=7)
    found = discovery.find_exact("moved-device")

    assert calls == [{
        "verbose": False,
        "maxretry": 7,
        "color": False,
        "poll": False,
        "forcescan": False,
        "byID": True,
    }]
    assert result["exact-device"].ip_address == "192.0.2.40"
    assert result["different-device"].device_id == "different-device"
    assert find_calls == [{"dev_id": "moved-device"}]
    assert found.device_id == "moved-device"


def test_scan_matches_exact_ids_uses_fallback_and_leaks_no_lan_metadata(
    tuya_setup_context,
) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    discovery = FakeDiscovery(
        scanned={
            "cloud-device-one": TuyaLanDevice(
                "cloud-device-one", "192.0.2.88", "3.5"
            ),
            "unrelated-device": TuyaLanDevice(
                "unrelated-device", "192.0.2.99", "3.3"
            ),
        },
        found={
            "cloud-device-two": TuyaLanDevice(
                "cloud-device-two", "192.0.2.77", "3.5"
            )
        },
    )
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), discovery, FakeLocalFactory(STATUS_ON_ZERO),
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        result = service.scan_lan(code, cloud.onboarding_session)

        assert result.success is True
        assert [item.device_ref for item in result.matched] == [
            item.device_ref for item in cloud.devices
        ]
        assert result.matched[0].ip_address == "192.0.2.88"
        assert result.matched[1].ip_address == "192.0.2.77"
        assert result.lan_only_count == 1
        assert "unrelated-device" not in result.model_dump_json()
        assert discovery.find_calls == ["cloud-device-two"]
        assert SetupService(session).progress()["next_step"] == "tuya"


def test_scan_reports_unmatched_cloud_by_opaque_ref_only(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    discovery = FakeDiscovery(scanned={
        "cloud-device-one": scanned_devices()["cloud-device-one"],
        # Even a malformed lookup keyed as device two must not match when the
        # discovered record itself carries a different exact device ID.
        "cloud-device-two": TuyaLanDevice(
            "different-device", "192.0.2.60", "3.5"
        ),
    })
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), discovery, FakeLocalFactory(STATUS_ON_ZERO),
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        # Disable the optional exact-ID recovery result for device two.
        result = service.scan_lan(code, cloud.onboarding_session)
        assert result.cloud_only == [cloud.devices[1].device_ref]
        assert "cloud-device-two" not in result.model_dump_json()


def test_overlapping_scan_is_rejected(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), FakeDiscovery(scanned_devices()),
            FakeLocalFactory(STATUS_ON_ZERO),
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        _TUYA_SCAN_LOCK.acquire()
        try:
            with pytest.raises(TuyaScanInProgressError):
                service.scan_lan(code, cloud.onboarding_session)
        finally:
            _TUYA_SCAN_LOCK.release()


def test_successful_read_only_verification_encrypts_devices_and_advances_state(
    tuya_setup_context,
) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    local = FakeLocalFactory(STATUS_ON_ZERO, STATUS_OFF)
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), FakeDiscovery(scanned_devices()), local,
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        scan = service.scan_lan(code, cloud.onboarding_session)
        assert scan.success is True
        result = service.configure_devices(configure_payload(
            code,
            cloud.onboarding_session,
            [item.device_ref for item in cloud.devices],
        ))
        session.commit()

        assert result.success is True
        assert result.runtime_activation == "restart_required"
        assert [item.relay_state for item in result.devices] == [True, False]
        assert result.devices[0].current_a == 0
        assert result.devices[0].power_w == 0
        assert result.setup.tuya_configured is True
        assert result.setup.devices_verified is True
        assert result.setup.next_step == "confirm"
        assert all(client.closed and not client.write_calls for client in local.clients)
        record = session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "tuya_devices"
        ))
        assert record.is_secret is True
        assert LOCAL_KEY_ONE not in record.value and LOCAL_KEY_TWO not in record.value
        assert "fake-access" not in record.value
        runtime = RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )
        persisted = runtime.get_tuya_device_configuration()
        assert [item["key"] for item in persisted] == [LOCAL_KEY_ONE, LOCAL_KEY_TWO]
        assert store.active_session_count == 0
        serialized = result.model_dump_json()
        assert LOCAL_KEY_ONE not in serialized and LOCAL_KEY_TWO not in serialized
        assert "cloud-device" not in serialized


@pytest.mark.parametrize(
    ("outcome", "category"),
    [
        (TuyaTimeoutError("unsafe"), "timeout"),
        (TuyaCommunicationError("wrong key unsafe"), "local_connection_failed"),
        (TuyaMalformedResponseError("unsafe dps"), "malformed_response"),
        ({"dps": {"18": 0, "19": 0}}, "unsupported_device"),
    ],
)
def test_local_verification_failure_preserves_previous_configuration(
    tuya_setup_context, outcome, category
) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        runtime = RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )
        runtime.set_tuya_device_configuration([{
            "id": "known-good-device",
            "name": "Known good",
            "area": "Known good",
            "key": "known-good-key",
            "ip": "192.0.2.10",
            "version": "3.5",
        }])
        state = session.get(InstallationStateRecord, 1)
        state.tuya_configured = True
        state.devices_verified = True
        session.commit()
        service = TuyaSetupService(
            session,
            runtime,
            store,
            cloud_gateway=FakeCloudGateway(candidates()[:1]),
            lan_discovery=FakeDiscovery({
                "cloud-device-one": scanned_devices()["cloud-device-one"]
            }),
            client_factory=FakeLocalFactory(outcome),
            environment=environment,
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        service.scan_lan(code, cloud.onboarding_session)
        request = TuyaDeviceConfigurationRequest(
            setup_code=code,
            onboarding_session=cloud.onboarding_session,
            devices=[{
                "device_ref": cloud.devices[0].device_ref,
                "friendly_name": "Replacement",
                "area": "Replacement",
            }],
        )
        result = service.configure_devices(request)
        session.commit()

        assert result.success is False and result.category == category
        persisted = runtime.get_tuya_device_configuration()
        assert persisted[0]["id"] == "known-good-device"
        state = session.get(InstallationStateRecord, 1)
        assert state.tuya_configured is True and state.devices_verified is True


def test_missing_cloud_local_key_cannot_be_selected(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates(include_missing_key=True)),
            FakeDiscovery(scanned_devices()), FakeLocalFactory(STATUS_ON_ZERO),
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        service.scan_lan(code, cloud.onboarding_session)
        result = service.configure_devices(configure_payload(
            code,
            cloud.onboarding_session,
            [item.device_ref for item in cloud.devices],
        ))
        assert result.success is False and result.category == "unsupported_device"
        assert session.scalar(select(RuntimeConfigurationRecord).where(
            RuntimeConfigurationRecord.namespace == "tuya_devices"
        )) is None


def test_failed_persisted_readback_rolls_back_known_good_configuration(
    tuya_setup_context,
) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        original_runtime = RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )
        original_runtime.set_tuya_device_configuration([{
            "id": "known-good-device",
            "name": "Known good",
            "area": "Known good",
            "key": "known-good-key",
            "ip": "192.0.2.10",
            "version": "3.5",
        }])
        session.commit()

        class FailedReadbackRuntime(RuntimeConfigurationService):
            def get_tuya_device_configuration(self):
                raise RuntimeConfigurationError("unsafe internal detail")

        runtime = FailedReadbackRuntime(
            session, environment=environment, master_key_file=str(key_file)
        )
        service = TuyaSetupService(
            session,
            runtime,
            store,
            cloud_gateway=FakeCloudGateway(candidates()[:1]),
            lan_discovery=FakeDiscovery({
                "cloud-device-one": scanned_devices()["cloud-device-one"]
            }),
            client_factory=FakeLocalFactory(STATUS_ON_ZERO),
            environment=environment,
        )
        cloud = service.retrieve_cloud_devices(cloud_payload(code))
        service.scan_lan(code, cloud.onboarding_session)
        result = service.configure_devices(TuyaDeviceConfigurationRequest(
            setup_code=code,
            onboarding_session=cloud.onboarding_session,
            devices=[{
                "device_ref": cloud.devices[0].device_ref,
                "friendly_name": "Replacement",
                "area": "Replacement",
            }],
        ))
        session.commit()

        assert result.success is False and result.category == "configuration_invalid"
        restored = original_runtime.get_tuya_device_configuration()
        assert restored[0]["id"] == "known-good-device"


def test_cloud_credentials_are_never_persisted_or_returned(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    with sessions() as session:
        result = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), FakeDiscovery(),
            FakeLocalFactory(STATUS_ON_ZERO),
        ).retrieve_cloud_devices(cloud_payload(code))
        session.commit()
        assert result.success is True
        serialized = result.model_dump_json()
        assert "fake-access-id" not in serialized
        assert "fake-access-secret" not in serialized
        assert LOCAL_KEY_ONE not in serialized
        assert session.scalar(select(RuntimeConfigurationRecord)) is None


def test_tuya_api_contract_is_secret_safe_and_stage_gated(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()
    cloud_gateway = FakeCloudGateway(candidates()[:1])
    discovery = FakeDiscovery({
        "cloud-device-one": scanned_devices()["cloud-device-one"]
    })
    local = FakeLocalFactory(STATUS_ON_ZERO)

    def override_db():
        with sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def override_runtime(session=Depends(get_db)):
        return RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    app.dependency_overrides[get_tuya_onboarding_store] = lambda: store
    app.dependency_overrides[get_tuya_cloud_gateway] = lambda: cloud_gateway
    app.dependency_overrides[get_tuya_lan_discovery] = lambda: discovery
    app.dependency_overrides[get_tuya_setup_client_factory] = lambda: local
    client = TestClient(app, base_url="https://testserver")
    request = {
        "setup_code": code,
        "region": "eu",
        "access_id": "api-access-id-not-real",
        "access_secret": "api-access-secret-not-real",
        "anchor_device_id": "api-anchor-device",
    }
    try:
        cloud = client.post("/api/v1/setup/tuya/cloud", json=request)
        assert cloud.status_code == 200 and cloud.json()["success"] is True
        assert cloud.headers["cache-control"] == "no-store"
        assert "api-access" not in cloud.text and LOCAL_KEY_ONE not in cloud.text
        token = cloud.json()["onboarding_session"]
        device_ref = cloud.json()["devices"][0]["device_ref"]
        scan = client.post("/api/v1/setup/tuya/scan", json={
            "setup_code": code,
            "onboarding_session": token,
        })
        assert scan.status_code == 200 and scan.json()["success"] is True
        configured = client.post("/api/v1/setup/tuya/devices", json={
            "setup_code": code,
            "onboarding_session": token,
            "devices": [{
                "device_ref": device_ref,
                "friendly_name": "Library",
                "area": "Library",
            }],
        })
        assert configured.status_code == 200
        assert configured.json()["setup"]["next_step"] == "confirm"
        assert LOCAL_KEY_ONE not in configured.text and "cloud-device-one" not in configured.text

        completed = client.post("/api/v1/setup/tuya/cloud", json=request)
        assert completed.status_code == 200
        with sessions() as session:
            session.get(InstallationStateRecord, 1).setup_completed = True
            session.commit()
        locked = client.post("/api/v1/setup/tuya/cloud", json=request)
        assert locked.status_code == 410
    finally:
        app.dependency_overrides.clear()


def test_tuya_cloud_failures_are_rate_limited(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    code = authorize_tuya(sessions)
    store = TuyaOnboardingStore()

    def override_db():
        with sessions() as session:
            yield session
            session.commit()

    def override_runtime(session=Depends(get_db)):
        return RuntimeConfigurationService(
            session, environment=environment, master_key_file=str(key_file)
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_runtime_configuration_service] = override_runtime
    app.dependency_overrides[get_tuya_onboarding_store] = lambda: store
    app.dependency_overrides[get_tuya_cloud_gateway] = lambda: FakeCloudGateway(
        TuyaCloudAuthenticationError("unsafe secret")
    )
    client = TestClient(app, base_url="https://testserver")
    request = {
        "setup_code": code,
        "region": "eu",
        "access_id": "id-not-real",
        "access_secret": "secret-not-real",
    }
    try:
        for _ in range(setup_limiter.attempts):
            response = client.post("/api/v1/setup/tuya/cloud", json=request)
            assert response.status_code == 200
            assert response.json()["category"] == "cloud_authentication_failed"
        limited = client.post("/api/v1/setup/tuya/cloud", json=request)
        assert limited.status_code == 429
        assert "secret-not-real" not in limited.text
    finally:
        app.dependency_overrides.clear()


def test_invalid_setup_stage_or_token_does_not_create_session(tuya_setup_context) -> None:
    sessions, key_file, environment = tuya_setup_context
    with sessions() as session:
        code = SetupService(session).initialize()
        state = SetupService(session).get_state()
        state.admin_configured = True
        session.commit()
    store = TuyaOnboardingStore()
    with sessions() as session:
        service = build_service(
            session, key_file, environment, store,
            FakeCloudGateway(candidates()), FakeDiscovery(),
            FakeLocalFactory(STATUS_ON_ZERO),
        )
        with pytest.raises(SetupStateError, match="authorization"):
            service.retrieve_cloud_devices(cloud_payload(code))
        state = session.get(InstallationStateRecord, 1)
        state.beve_configured = True
        session.commit()
        with pytest.raises(SetupStateError, match="authorization"):
            service.retrieve_cloud_devices(cloud_payload("wrong-code"))
        assert store.active_session_count == 0
