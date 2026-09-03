"""Safely exercise the production breaker integration without exposing secrets."""

from __future__ import annotations

import time

from apps.core.config import settings
from apps.core.runtime import build_application_runtime, configure_application_runtime


def _display(value: object) -> str:
    return "--" if value is None else str(value)


def main() -> int:
    runtime = build_application_runtime(settings, provision=False)
    try:
        ids = runtime.breaker_service.registered_breaker_ids
        print(f"Registered breakers: {len(ids)}")
        if not ids:
            print("No enabled breaker registrations were found.")
            return 1

        failures = 0
        for breaker_id in ids:
            started = time.monotonic()
            breaker = runtime.breaker_service.get_breaker(breaker_id)
            elapsed = time.monotonic() - started
            error = runtime.breaker_service.get_last_error_category(breaker_id)
            client = runtime.breaker_service.get_registration(breaker_id).client
            electrical = breaker.status.electrical
            print(
                f"{breaker.friendly_name}: "
                f"protocol={client.config.protocol_version} "
                f"configured_address_reachable={str(breaker.online and not getattr(client, 'rediscovery_used', False)).lower()} "
                f"persistent_connection={str(getattr(client, 'persistent_connection_created', False)).lower()} "
                f"status={'success' if breaker.online else 'failure'} "
                f"online={str(breaker.online).lower()} "
                f"relay={_display(breaker.status.switch_on)} "
                f"voltage_v={_display(electrical.voltage_volts)} "
                f"current_a={_display(electrical.current_amperes)} "
                f"power_w={_display(electrical.active_power_watts)} "
                f"failure={error or 'none'} elapsed_ms={elapsed * 1000:.1f} "
                f"rediscovery_needed={str(getattr(client, 'rediscovery_used', False)).lower()}"
            )
            failures += int(not breaker.online)
        return 1 if failures else 0
    finally:
        runtime.breaker_service.close()
        configure_application_runtime(None)


if __name__ == "__main__":
    raise SystemExit(main())
