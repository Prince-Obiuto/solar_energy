"""Inverter API client interface.

Keep all hardware-specific protocol calls in this module and keep them behind an
interface so the rest of the application only sees domain models.
"""

from __future__ import annotations

from typing import Any


class InverterClient:
    """Minimal inverter client stub for later hardware integration."""

    def __init__(self, *, host: str | None = None, api_token: str | None = None) -> None:
        self.host = host
        self.api_token = api_token

    def connect(self) -> bool:
        """Return whether a configured inverter connection is available."""

        return bool(self.host)

    def fetch_snapshot(self) -> dict[str, Any]:
        """Placeholder for the real inverter protocol implementation."""

        raise NotImplementedError(
            "Inverter protocol logic is intentionally deferred until the actual hardware "
            "specification is available. Keep the vendor driver isolated here."
        )

