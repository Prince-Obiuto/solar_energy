"""Initialize or rotate the one-time first-run setup code."""
import argparse
from apps.db.session import session_scope
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize first-run application setup")
    parser.add_argument("--rotate-token", action="store_true", help="Invalidate and replace an incomplete setup code")
    args = parser.parse_args()
    try:
        with session_scope() as session:
            code = SetupService(session).initialize(rotate=args.rotate_token)
    except (SetupLockedError, SetupStateError) as exc:
        print(str(exc))
        return 1
    print("Solar Energy Management System")
    if code is None:
        print("Setup is already initialized.")
        print("Use --rotate-token before administrator creation if a replacement code is required.")
        return 0
    print("First-time setup token rotated." if args.rotate_token else "First-time setup initialized.")
    print("\nSetup URL:\n    /setup")
    print(f"\nOne-time setup code:\n    {code}")
    print("\nKeep this code safe. It is required to create the first administrator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
