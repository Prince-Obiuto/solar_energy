# Backend

FastAPI backend for the Smart Renewable Energy Management System.

Database backup and restore operations are documented in
[`docs/database-backups.md`](docs/database-backups.md).

The complete architecture, setup, security, API, deployment, and hardware guide
is available at [`../docs/system-guide.md`](../docs/system-guide.md).

Implementation is intentionally staged. Device integrations, database persistence, realtime telemetry, authentication, controls, reporting, and alerts should be developed behind service and adapter boundaries so the frontend is not coupled to vendor-specific protocols.
