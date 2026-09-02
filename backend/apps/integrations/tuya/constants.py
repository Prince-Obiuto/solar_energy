"""Verified device metadata and TinyTuya error classifications.

Datapoint mappings intentionally remain in ``mapper.py`` for Phase 4.
"""

TUYA_PRODUCT_NAME = "WIFl Smart Meter Pro"
TUYA_MODEL = "TMPH"
TUYA_CATEGORY = "znjdq"
TUYA_PRODUCT_ID = "ruqchkg5f9loztw2"
DEFAULT_PROTOCOL_VERSION = "3.5"

TINYTUYA_MALFORMED_ERROR_CODES = frozenset({"900", "904"})
TINYTUYA_OFFLINE_ERROR_CODES = frozenset({"901", "905"})
TINYTUYA_TIMEOUT_ERROR_CODES = frozenset({"902"})

# Verified TMPH control allowlist. Calibration and unknown datapoints are
# intentionally absent, making arbitrary writes impossible through this layer.
DP_SWITCH = 1
DP_COUNTDOWN = 9
DP_RELAY_RESTORE_MODE = 38
DP_INDICATOR_MODE = 40
DP_CHILD_LOCK = 41
DP_ACCUMULATED_ENERGY = 17
DP_CURRENT = 18
DP_ACTIVE_POWER = 19
DP_VOLTAGE = 20
CONTROL_DATAPOINTS = frozenset(
    {DP_SWITCH, DP_COUNTDOWN, DP_RELAY_RESTORE_MODE, DP_INDICATOR_MODE, DP_CHILD_LOCK}
)
CALIBRATION_DATAPOINTS = frozenset({22, 23, 24, 25})
UNEXPOSED_DATAPOINTS = frozenset({21, 26, 42})
DIAGNOSTIC_DATAPOINTS = CALIBRATION_DATAPOINTS | UNEXPOSED_DATAPOINTS
RELAY_RESTORE_MODES = frozenset({"off", "on", "memory"})
INDICATOR_MODES = frozenset({"relay", "pos", "none", "on"})
