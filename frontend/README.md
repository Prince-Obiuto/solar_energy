# Energy Management frontend

React/Vite monitoring frontend for the Smart Renewable Energy Management
System. It uses the authenticated FastAPI REST API at `/api/v1` and realtime
telemetry at `/api/v1/ws/energy`.

```bash
npm install
npm run dev
npm run lint
npm run build
```

Copy `.env.example` to the ignored `.env` file when an API or WebSocket URL must
be overridden. Authentication uses the backend's HttpOnly cookie; tokens and
hardware secrets are not stored in browser storage.

See [the system guide](../docs/system-guide.md) for architecture, setup, role
behavior, deployment, and known limitations.
