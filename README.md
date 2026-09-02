# Smart Renewable Energy Management System

Monitoring and administration software for the Department of Information
Technology. The repository contains a React frontend and a FastAPI backend for
read-only BEVE inverter telemetry, local TinyTuya TMPH breaker telemetry,
historical reporting, alerts, audited breaker control, and operations.

See [docs/system-guide.md](docs/system-guide.md) for architecture, setup,
configuration, endpoint inventories, deployment, security, and known limits.

Quick checks:

```bash
cd backend
python -m pytest

cd ../frontend
npm run lint
npm run build
```
