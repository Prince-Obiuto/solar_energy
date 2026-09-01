"""Tuya datapoint and command constants.

Keep any vendor datapoint names in this module only. Application code should not
reference them directly.
"""

from __future__ import annotations

SUPPORTED_SWITCH_STATES = {"on", "off", "open", "closed"}
SUPPORTED_POWER_FIELDS = {"power_w", "power_watts", "power"}
SUPPORTED_VOLTAGE_FIELDS = {"voltage_v", "voltage"}
SUPPORTED_CURRENT_FIELDS = {"current_ma", "current_amps"}

