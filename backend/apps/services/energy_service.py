"""Energy telemetry application service."""

from __future__ import annotations


def get_energy_summary() -> dict[str, object]:
    """Return normalized site energy summary data for the dashboard layer."""

    return {
        "generated_watts": 0.0,
        "consumed_watts": 0.0,
        "grid_power_watts": 0.0,
        "site_status": "unknown",
    }


def list_energy_points() -> list[dict[str, object]]:
    """Return an empty list until a live telemetry source is connected."""

    return []

