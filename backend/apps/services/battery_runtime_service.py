"""Estimate battery-supported runtime from fresh normalized BEVE telemetry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Sequence

from apps.core.config import Settings, settings
from apps.jobs.energy_collector import InverterLoadSample
from apps.models import DataFreshness, DataStatus, InverterTelemetry, SourceStatus
from apps.schemas.dashboard import BatteryRuntimeEstimate


class BatteryRuntimeEstimator:
    """Use nominal capacity and a short median of actual source load samples."""

    def __init__(self, config: Settings = settings, *, clock=None) -> None:
        self.config = config
        self.clock = clock or (lambda: datetime.now(UTC))

    def estimate(
        self,
        telemetry: InverterTelemetry | None,
        data_status: DataStatus,
        samples: Sequence[InverterLoadSample] = (),
    ) -> BatteryRuntimeEstimate:
        now = self.clock()
        if telemetry is None or not self._fresh(telemetry, data_status, now):
            return BatteryRuntimeEstimate(
                source_timestamp=data_status.source_timestamp,
            )

        source_timestamp = telemetry.timestamp
        mode = (telemetry.inverter.status or "").strip().casefold()
        battery_status = (telemetry.battery.status or "").strip().casefold()
        if mode != "battery mode":
            # A conflicting discharge indication is not proof of grid operation.
            state = "unavailable" if not mode or battery_status == "discharging status" else "not_on_battery"
            return BatteryRuntimeEstimate(
                state=state, source_timestamp=source_timestamp,
            )
        if battery_status != "discharging status":
            return BatteryRuntimeEstimate(source_timestamp=source_timestamp)

        soc = telemetry.battery.soc
        load = telemetry.inverter.output_power_w
        metadata = dict(
            current_soc_percent=soc,
            load_power_w=load,
            source_timestamp=source_timestamp,
        )
        if soc is None or load is None or load <= self.config.battery_runtime_min_load_w:
            return BatteryRuntimeEstimate(**metadata)

        cutoff = source_timestamp - timedelta(seconds=self.config.battery_runtime_smoothing_window_seconds)
        powers = {
            sample.timestamp: sample.output_power_w
            for sample in samples
            if cutoff <= sample.timestamp <= source_timestamp
            and (sample.inverter_status or "").strip().casefold() == "battery mode"
            and (sample.battery_status or "").strip().casefold() == "discharging status"
            and sample.output_power_w is not None
            and sample.output_power_w >= 0
        }
        powers[source_timestamp] = load
        calculation_load = float(median(powers.values()))
        if calculation_load <= self.config.battery_runtime_min_load_w:
            return BatteryRuntimeEstimate(**metadata, calculation_load_w=calculation_load)

        hours = self.config.battery_nominal_capacity_kwh * (soc / 100) / (calculation_load / 1000)
        return BatteryRuntimeEstimate(
            state="battery",
            estimated_minutes_remaining=round(hours * 60),
            estimated_hours_remaining=round(hours, 2),
            calculation_load_w=calculation_load,
            calculated_at=now,
            **metadata,
        )

    def _fresh(self, telemetry: InverterTelemetry, data_status: DataStatus, now: datetime) -> bool:
        timestamp = data_status.source_timestamp
        if (
            not data_status.available
            or data_status.stale
            or data_status.data_freshness is not DataFreshness.LIVE
            or data_status.source_status is not SourceStatus.CONNECTED
            or timestamp is None
            or timestamp != telemetry.timestamp
            or timestamp.tzinfo is None
        ):
            return False
        age_seconds = (now - timestamp).total_seconds()
        return 0 <= age_seconds < self.config.beve_source_stale_after_seconds
