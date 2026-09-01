"""Inverter protocol constants placeholder.

These constants are intentionally generic. Actual register names must be defined
only in the deployed hardware integration and never spread into the application
layer.
"""

from __future__ import annotations

STATUS_VALUES = {"online", "offline", "normal", "fault", "running", "stopped"}
POWER_FIELDS = {"grid_power_w", "grid_power_watts", "pv_power_w", "pv_power_watts"}
BATTERY_FIELDS = {"battery_soc", "state_of_charge"}

