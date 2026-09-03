"""Explicit, confirmed physical relay diagnostic using the production Tuya client."""
from __future__ import annotations
import argparse
import time
from apps.core.config import settings
from apps.core.runtime import build_application_runtime, configure_application_runtime
from apps.integrations.tuya.constants import DP_SWITCH
from apps.integrations.tuya.client import TuyaIntegrationError
from apps.integrations.tuya.adapter import TuyaBreakerAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-back-verified breaker relay test")
    parser.add_argument("--device", required=True, help="Configured breaker reference")
    parser.add_argument("--state", required=True, choices=("on", "off"))
    args = parser.parse_args()
    requested = args.state == "on"
    runtime = build_application_runtime(settings, provision=False)
    try:
        if args.device not in runtime.breaker_service.registered_breaker_ids:
            print("Configured breaker was not found.")
            return 2
        registration = runtime.breaker_service.get_registration(args.device)
        name = registration.client.config.friendly_name
        adapter = TuyaBreakerAdapter()
        with runtime.breaker_service.hardware_access(args.device):
            previous = adapter.read_control_value(registration.client, DP_SWITCH)
            print(f"Current relay state: {'ON' if previous is True else 'OFF' if previous is False else 'UNKNOWN'}")
            answer = input(f'About to switch "{name}" {args.state.upper()}.\nContinue? [y/N] ')
            if answer.strip().lower() != "y":
                print("Cancelled.")
                return 1
            adapter.set_switch(registration.client, requested)
            if settings.tuya_control_verify_delay_seconds:
                time.sleep(settings.tuya_control_verify_delay_seconds)
            verified = adapter.read_control_value(registration.client, DP_SWITCH)
        succeeded = type(verified) is bool and verified == requested
        print(f"Previous: {'ON' if previous else 'OFF'}")
        print(f"Requested: {'ON' if requested else 'OFF'}")
        print(f"Verified: {'ON' if verified is True else 'OFF' if verified is False else 'UNKNOWN'}")
        print(f"Result: {'SUCCESS' if succeeded else 'FAILED'}")
        return 0 if succeeded else 1
    except TuyaIntegrationError as exc:
        print(f"Result: FAILED ({runtime.breaker_service.get_last_error_category(args.device) or type(exc).__name__})")
        return 1
    finally:
        runtime.breaker_service.close()
        configure_application_runtime(None)


if __name__ == "__main__":
    raise SystemExit(main())
