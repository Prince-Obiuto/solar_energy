"""Verified read-only BEVE/Solar-of-Things protocol constants."""

DEFAULT_BASE_URL = "https://solar.siseli.com"
LATEST_STATE_PATH = "/apis/deviceState/simple/state/latest/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0

FIELD_KEYS = {
    "workingStates",
    "ratedActivePower",
    "outputVoltage",
    "outputFrequency",
    "acOutputActivePower",
    "loadPercentage",
    "batteryCapacity",
    "batteryVoltage",
    "batteryChargingCurrent",
    "batteryDischargeCurrent",
    "batteryPower",
    "batteryStatus",
    "batteryChargeStep",
    "batteryType",
    "pvAccessSign",
    "pvInputVoltage",
    "pvInputPower",
    "pv2InputVoltage",
    "pv2InputPower",
    "generationPower",
    "pvGeneratedEnergyOfDay",
    "pvGeneratedEnergyThisMonth",
    "totalPVGeneratedEnergy",
    "acInputVoltage",
    "acInputFrequency",
    "GridPower",
}
