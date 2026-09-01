"""Tuya client interface and connection placeholder.

The app should obtain credentials from environment variables or secret stores,
never from committed config files or hard-coded values.
"""

from __future__ import annotations

from typing import Any


class TuyaClient:
    """Minimal vendor client wrapper with a clear TODO boundary."""

    def __init__(
        self,
        *,
        access_id: str | None = None,
        access_secret: str | None = None,
        endpoint: str | None = None,
        project_code: str | None = None,
    ) -> None:
        self.access_id = access_id
        self.access_secret = access_secret
        self.endpoint = endpoint
        self.project_code = project_code

    def connect(self) -> bool:
        """Return whether a client connection is configured."""

        return bool(self.access_id and self.access_secret and self.endpoint)

    def fetch_device_state(self, device_id: str) -> dict[str, Any]:
        """Placeholder for vendor-specific device fetch logic."""

        raise NotImplementedError(
            "Tuya client logic is intentionally deferred until the target hardware and "
            "credentials are available. Keep vendor-specific calls in this integration class."
        )

