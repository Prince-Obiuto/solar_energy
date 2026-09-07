"""Initialize the external runtime-configuration encryption key."""

from apps.core.config import settings
from apps.security.runtime_secrets import RuntimeSecretError, initialize_runtime_master_key


def main() -> int:
    destination = settings.runtime_master_key_path
    if destination is None:
        print("RUNTIME_MASTER_KEY_FILE is not configured.")
        return 1
    try:
        created = initialize_runtime_master_key(destination)
    except RuntimeSecretError as exc:
        print(f"Runtime configuration key initialization failed: {exc}")
        return 1
    if created:
        print("Runtime configuration key created:")
    else:
        print("Runtime configuration key already exists:")
    print(f"    {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
