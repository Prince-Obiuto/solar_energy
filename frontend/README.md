# Smart Renewable Energy Management System

A responsive, frontend-only Energy Management System (EMS) for monitoring renewable generation, storage, site consumption, infrastructure, administrative controls, reports, audit activity, users, and system settings.

The application is built as an enterprise-style React frontend. It currently uses deterministic placeholder data and local state; it does not issue backend, device, export, restart, switching, or authentication commands.

## Contents

- [Technology](#technology)
- [Features](#features)
- [Quick start](#quick-start)
- [Available scripts](#available-scripts)
- [Routes](#routes)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [State and data flow](#state-and-data-flow)
- [UI library](#ui-library)
- [Charts and tables](#charts-and-tables)
- [Design conventions](#design-conventions)
- [Accessibility](#accessibility)
- [Responsive behavior](#responsive-behavior)
- [Loading, error, and empty states](#loading-error-and-empty-states)
- [Mock-data boundary](#mock-data-boundary)
- [Adding a feature](#adding-a-feature)
- [Backend integration guide](#backend-integration-guide)
- [Quality checks](#quality-checks)
- [Known limitations](#known-limitations)

## Technology

- React 19
- Vite 8
- React Router 7
- Tailwind CSS 4
- Zustand 5
- Axios
- Recharts
- Heroicons
- ESLint

## Features

### Application shell

- Responsive mobile/tablet/desktop layout
- Collapsible desktop sidebar and mobile navigation drawer
- Breadcrumbs, notification indicator, connection status, and user menu
- Shared footer
- Light, dark, and operating-system theme modes
- Route-level code splitting and loading feedback
- Application-wide render error boundary

### Dashboard

- PV power, battery SOC, load, grid, and system KPIs
- Live star-topology flow between PV, inverter, battery, loads, and utility grid
- Direction-aware grid import power, voltage, frequency, and daily energy statistics
- Daily energy statistics
- Recent alerts
- Area consumption
- Quick actions
- System health

### Area Monitoring

- Card and table views
- Search and breaker-status filtering
- Departmental electrical measurements
- Responsive overflow behavior for dense tables

### Devices

- Hybrid inverter, battery, smart breaker, server, and network switch cards
- Connection, IP, firmware, temperature, and health information
- Local-only View, Restart, and Configure action feedback

### Control Center

- Administrator-only mock access
- Emergency shutdown, solar, battery, grid, alarm, inverter, and area controls
- Required action reason and password placeholder
- Audit preview and local confirmation record
- No control command leaves the browser

### Reports

- Daily, weekly, monthly, and custom periods
- Solar production, battery usage, area consumption, and grid import charts
- CSV, PDF, and print placeholders
- Shared Recharts-based visualizations

### Logs

- Authentication, system, device, control, warning, and error categories
- Search and filters
- Timeline and pagination
- Keyboard-accessible details drawer

### User Management

- Administrator, Staff, and Student roles
- Local Add, Edit, Deactivate, and Reset Password flows
- Permission matrix
- Mock authenticated administrator

### Settings

- General, department, network, notifications, system, appearance, security, audit, and about sections
- All setting values are stored in Zustand
- No settings are persisted to a server

## Quick start

Requirements:

- Node.js 20 or newer
- npm 10 or newer

Install and start the development server:

```bash
npm install
npm run dev
```

Vite prints the local development URL, typically `http://localhost:5173`.

Create and inspect a production build:

```bash
npm run build
npm run preview
```

## Available scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start Vite with hot module replacement |
| `npm run build` | Create an optimized production bundle |
| `npm run preview` | Serve the production bundle locally |
| `npm run lint` | Run ESLint across the project |

## Routes

| Route | Module |
| --- | --- |
| `/` | Smart energy dashboard |
| `/energy` | Energy placeholder state |
| `/areas` | Area Monitoring |
| `/devices` | Device Monitoring |
| `/controls` | Administrator Control Center |
| `/reports` | Reports and charts |
| `/logs` | Activity Logs |
| `/users` | User Management |
| `/settings` | Settings |
| `*` | Not Found page |

Route constants are defined in `src/app/router/routes.js`. Route components are lazy-loaded by `src/app/router/AppRouter.jsx`.

## Architecture

The codebase uses a feature-oriented architecture:

```text
route
  -> page (route adapter)
    -> feature component (screen composition)
      -> feature hook (interaction/business state)
        -> feature store or service (state/data source)
      -> shared layout/UI/chart/table primitives
```

Responsibilities are intentionally separated:

- `app/` owns bootstrapping, providers, routing, and global error handling.
- `pages/` contains thin route adapters only.
- `features/` owns domain-specific components, hooks, stores, and placeholder services.
- `components/` contains reusable, domain-independent presentation and interaction primitives.
- `services/` contains shared infrastructure such as the Axios client.
- `hooks/` contains cross-feature behavior such as interval and overlay accessibility hooks.
- `utils/` contains pure constants and formatting functions.
- `styles/` contains the Tailwind entry point and minimal global foundations.

Pages do not contain business logic. Feature hooks own filtering, pagination, dialog state, and local actions. Feature services own placeholder datasets.

## Project structure

```text
src/
├── app/
│   ├── App.jsx
│   ├── AppErrorBoundary.jsx
│   ├── main.jsx
│   ├── providers/
│   └── router/
├── components/
│   ├── charts/
│   ├── data-table/
│   ├── layout/
│   └── ui/
├── features/
│   ├── areas/
│   ├── control/
│   ├── devices/
│   ├── energy/
│   ├── logs/
│   ├── reports/
│   ├── settings/
│   └── users/
├── hooks/
├── pages/
├── services/http/
├── styles/
└── utils/
```

A feature normally follows this structure:

```text
features/example/
├── components/   # Domain UI and screen composition
├── hooks/        # Feature behavior and derived state
├── services/     # Data access or placeholder data
└── store/        # Zustand state when shared feature state is needed
```

## State and data flow

The application uses the smallest appropriate state scope:

- Component state handles short-lived UI state such as open menus and tabs.
- Feature hooks encapsulate search, filters, pagination, and action feedback.
- Zustand manages energy state and the persisted settings model.
- Services expose cloned placeholder data so UI code does not mutate fixtures.

The settings store is located at `src/features/settings/store/settings.store.js`. The energy store is located at `src/features/energy/store/energy.store.js`.

The settings store uses Zustand persistence under the `ems-settings` browser-storage key. `ThemeProvider` reads the Appearance theme, follows `prefers-color-scheme` when set to System, and applies the resolved theme to the document root. The top navigation also provides a quick light/dark toggle.

## UI library

Reusable Tailwind-only UI primitives live in `src/components/ui`. Import individual modules or use the barrel export:

```jsx
import { Alert, Button, Card, EmptyState, Input, StatusChip } from "../components/ui";
```

Available primitives include:

- Accordion
- Alert
- Badge and StatusChip
- Button and Input
- Card and SectionHeading
- Modal, Dialog, and Drawer
- Dropdown, Tabs, and Tooltip
- Loader and Skeleton
- Toast
- Pagination, Table, and EmptyState
- ErrorState

`Modal` and `Drawer` share `useOverlayA11y`, which provides Escape handling, focus containment, focus restoration, and background-scroll locking.

## Charts and tables

Shared Recharts wrappers live in `src/components/charts`:

- LineChart
- AreaChart
- BarChart
- PieChart
- GaugeChart
- PowerFlowDiagram
- BatteryIndicator

All visualization components accept props and share `ChartFrame` for container appearance.

For simple responsive tables, use `components/ui/Table`. For interactive datasets, use `components/data-table/DataTable`, which supports:

- Search
- Configurable filters
- Sorting with announced sort direction
- Pagination
- Column visibility controls
- Export placeholder feedback
- Empty results
- Responsive horizontal scrolling

## Design conventions

The visual system intentionally uses a narrow set of conventions:

- Emerald is the primary brand and interaction color.
- Gray is used for neutral surfaces, borders, and typography.
- Sky represents information, amber warnings, rose errors, and emerald success.
- Light and dark modes use the same semantic color hierarchy; theme changes do not alter layout or component structure.
- Cards use `rounded-xl`, a gray-100 border, white background, and subtle shadow.
- Page sections use a six-unit vertical rhythm (`space-y-6`).
- Dense controls use three-unit gaps; related card grids generally use five- or six-unit gaps.
- Page content is constrained by `PageContainer` to `max-w-7xl`, with a narrow `max-w-5xl` option.
- Page titles use semantic `h1`; widget titles remain `h2` or `h3`.
- Body content uses the shared system sans-serif stack.

When adding UI, prefer existing primitives before introducing new classes or components.

## Accessibility

The audited frontend includes:

- Semantic landmarks for navigation, headers, main content, and footer
- One primary heading per implemented module
- Visible global keyboard focus styling
- Native buttons, links, inputs, selects, and tables
- Accessible names for icon-only controls
- `aria-expanded`, `aria-selected`, `aria-modal`, `aria-sort`, and status roles where relevant
- Arrow, Home, and End keyboard navigation for shared tabs
- Escape-to-close for menus, the mobile sidebar, dialogs, modals, and drawers
- Focus trapping and focus restoration for shared overlays
- Disabled action and pagination states
- Row and column headers in the permission matrix
- Text labels in addition to color for statuses and alerts

New interactive components should remain operable without a pointer and must expose a visible focus state.

## Responsive behavior

- The navigation becomes an off-canvas drawer below the medium breakpoint.
- The desktop/tablet sidebar can collapse to an icon rail.
- Page padding changes from `p-4` to `p-6` at the small breakpoint.
- Dashboard and feature grids progressively expand from one column.
- Toolbars stack before moving to horizontal layouts.
- Dense tables preserve their columns through horizontal scrolling.
- Modals and drawers use full-width mobile layouts with constrained desktop widths.

The supported minimum viewport width is 320px. The interface is optimized for phones, tablets, and desktop displays.

## Loading, error, and empty states

- Lazy routes render the shared Loader while their bundle is fetched.
- The energy dashboard has explicit loading, error/retry, and empty states.
- Searchable modules render EmptyState when filters return no results.
- Tables render an empty result row when no data matches.
- `AppErrorBoundary` handles unexpected render failures and provides a reload action.
- Shared `Loader`, `Skeleton`, `EmptyState`, and `ErrorState` primitives are available for new features.

## Mock-data boundary

This is currently a frontend prototype:

- Feature data comes from files named `*.service.js` under each feature.
- Control actions are validated and recorded only in local state.
- Authentication and roles are placeholders.
- Device actions do not contact physical infrastructure.
- Exports and printing show placeholder feedback but produce no output.
- Settings are stored locally in browser storage through Zustand; they are not synchronized to a server.
- The shared Axios client exists for future integration but is not used by feature services.

Do not treat any displayed measurement or action record as production telemetry.

## Adding a feature

1. Add a path to `src/app/router/routes.js`.
2. Add a lazy page import and route in `AppRouter.jsx`.
3. Create a thin page in `src/pages` that renders one feature entry component.
4. Create the feature under `src/features/<feature>`.
5. Put placeholder/API access in `services`, behavior in `hooks`, shared state in `store`, and composition in `components`.
6. Reuse `PageContainer`, `SectionHeading`, UI primitives, charts, and tables.
7. Add loading, error, and empty states appropriate to the feature.
8. Verify keyboard behavior, accessible labels, small-screen layout, lint, and production build.

## Backend integration guide

When a backend is introduced:

1. Configure `src/services/http/axiosClient.js` with an environment-based `baseURL`, timeout, and request/response interceptors.
2. Replace feature service fixture returns with asynchronous Axios calls while preserving service interfaces.
3. Extend feature hooks/stores with explicit `idle`, `loading`, `success`, and `error` states.
4. Store tokens through an agreed secure authentication strategy; do not hard-code credentials or secrets.
5. Enforce authorization on the server. Client-side role checks are presentation only.
6. Require server-side validation, idempotency, audit records, and authorization for every control command.
7. Add request cancellation and stale-response protection for changing filters or routes.
8. Add automated tests before enabling real infrastructure controls.

Vite client environment variables must start with `VITE_`. Never place private secrets in frontend environment variables.

## Quality checks

Before handing off a change, run:

```bash
npm run lint
npm run build
git diff --check
```

The production router uses lazy imports, keeping Recharts and report code out of the initial application chunk until Reports is opened.

## Known limitations

- No backend or persistence layer is connected.
- Authentication and authorization are mock implementations.
- There is no automated unit, integration, or end-to-end test suite yet.
- Charts are illustrative rather than live telemetry.
- Export, print, restart, configure, switching, and control actions are placeholders.
- The Energy route is currently an intentional empty-state placeholder.

Before production use, add tests, real authentication, server-enforced permissions, API error contracts, observability, and a security review appropriate for infrastructure-control software.
