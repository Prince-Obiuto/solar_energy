"""Read-only battery-runtime estimates from fresh BEVE-normalized telemetry."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from apps.core.config import Settings
from apps.integrations.inverter import VERIFIED_BEVE_RESPONSE
from apps.jobs.energy_collector import InverterLoadSample
from apps.models import (
    ConnectivityType, DataFreshness, DataSource, DataStatus, InverterTelemetry,
    SourceStatus,
)
from apps.services.battery_runtime_service import BatteryRuntimeEstimator


NOW = datetime(2026, 9, 1, 12, 19, 6, tzinfo=UTC)


def telemetry(**changes) -> InverterTelemetry:
    payload = deepcopy(VERIFIED_BEVE_RESPONSE)
    payload["inverter"]["output_power_w"] = 1000
    payload["battery"]["soc"] = 50
    for category, fields in changes.items():
        payload[category].update(fields)
    return InverterTelemetry.model_validate(payload)


def live_status(timestamp=NOW) -> DataStatus:
    return DataStatus(
        connectivity_type=ConnectivityType.CLOUD,
        data_source=DataSource.BEVE_CLOUD,
        available=True, stale=False,
        source_status=SourceStatus.CONNECTED,
        data_freshness=DataFreshness.LIVE,
        source_timestamp=timestamp,
    )


def estimator() -> BatteryRuntimeEstimator:
    config = Settings(
        _env_file=None, app_env="test", battery_nominal_capacity_kwh=5.0,
        battery_runtime_min_load_w=50.0,
    )
    return BatteryRuntimeEstimator(config, clock=lambda: NOW)


@pytest.mark.parametrize(("soc", "minutes"), [(100, 300), (50, 150), (5, 15)])
def test_verified_battery_mode_uses_nominal_capacity_and_current_load(soc, minutes):
    state = telemetry(battery={"soc": soc})
    result = estimator().estimate(state, live_status())
    assert result.state == "battery"
    assert result.estimated_minutes_remaining == minutes
    assert result.estimated_hours_remaining == round(minutes / 60, 2)
    assert result.current_soc_percent == soc
    assert result.load_power_w == result.calculation_load_w == 1000
    assert result.calculated_at == result.source_timestamp == NOW


def test_not_on_battery_never_produces_runtime():
    state = telemetry(inverter={"status": "Other operating mode"}, battery={"status": "Charging Status"})
    result = estimator().estimate(state, live_status())
    assert result.state == "not_on_battery"
    assert result.estimated_minutes_remaining is None
    assert result.estimated_hours_remaining is None


@pytest.mark.parametrize("power", [0, 12, None])
def test_zero_low_or_missing_load_never_divides_by_zero_or_invents_runtime(power):
    result = estimator().estimate(telemetry(inverter={"output_power_w": power}), live_status())
    assert result.state == "unavailable"
    assert result.estimated_minutes_remaining is None
    assert result.load_power_w == power


def test_missing_soc_is_unavailable():
    result = estimator().estimate(telemetry(battery={"soc": None}), live_status())
    assert result.state == "unavailable"
    assert result.estimated_minutes_remaining is None
    assert result.current_soc_percent is None


def test_stale_or_unavailable_source_never_uses_old_soc_or_load():
    state = telemetry()
    source = live_status()
    source.stale = True
    source.data_freshness = DataFreshness.STALE
    assert estimator().estimate(state, source).state == "unavailable"

    source = live_status()
    source.available = False
    source.source_status = SourceStatus.TIMEOUT
    assert estimator().estimate(state, source).estimated_minutes_remaining is None

    old = state.model_copy(update={"timestamp": NOW - timedelta(minutes=20)})
    assert estimator().estimate(old, live_status(old.timestamp)).state == "unavailable"
    assert estimator().estimate(None, live_status()).state == "unavailable"


def test_conflicting_or_missing_discharge_signal_is_not_a_runtime():
    for status in (None, "Charging Status"):
        result = estimator().estimate(telemetry(battery={"status": status}), live_status())
        assert result.state == "unavailable"
        assert result.estimated_minutes_remaining is None
    conflicting = telemetry(inverter={"status": "Other operating mode"})
    assert estimator().estimate(conflicting, live_status()).state == "unavailable"


def test_recent_load_median_smooths_changes_without_filling_missing_samples():
    samples = [
        InverterLoadSample(timestamp=NOW - timedelta(seconds=60), output_power_w=500,
                           inverter_status="Battery Mode", battery_status="Discharging Status"),
        InverterLoadSample(timestamp=NOW - timedelta(seconds=30), output_power_w=None,
                           inverter_status="Battery Mode", battery_status="Discharging Status"),
        InverterLoadSample(timestamp=NOW - timedelta(minutes=10), output_power_w=4000,
                           inverter_status="Battery Mode", battery_status="Discharging Status"),
    ]
    result = estimator().estimate(telemetry(), live_status(), samples)
    assert result.state == "battery"
    assert result.load_power_w == 1000
    assert result.calculation_load_w == 750
    assert result.estimated_minutes_remaining == 200


@pytest.mark.parametrize("grid_power", [-4000, 0, 4000, None])
def test_grid_power_sign_does_not_enter_battery_runtime_decision(grid_power):
    result = estimator().estimate(telemetry(grid={"power_w": grid_power}), live_status())
    assert result.state == "battery"
    assert result.estimated_minutes_remaining == 150
