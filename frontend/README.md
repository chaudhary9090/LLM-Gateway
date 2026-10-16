# LLM Gateway Web Dashboard & Playground

A modern, high-performance developer dashboard and playground for the LLM Gateway.

## Features
- **Overview & Telemetry**: Real-time KPI cards (total requests, success rate, cache hit rate, fallback count, p50/p95/p99 latency, total tokens, estimated cost) with Recharts visualizations and auto-refresh (5s polling with pause toggle).
- **Interactive Playground**: Chat interface with model alias routing (`cheap`, `balanced`, `powerful`), temperature, max tokens, task hints, and cache toggle (`cache: true` / `cache: false`). Full metadata strip per response with request ID copy and friendly error states.
- **Provider Circuit Breakers**: Live status card per provider showing health and circuit breaker states (`CLOSED` in green, `HALF_OPEN` in amber, `OPEN` in red) with failure counts.
- **Model Catalog**: Searchable and sortable catalog displaying tiers, capabilities, primary & fallback providers, and token pricing.
- **Server Audit Logs**: Server-side paginated request logs with status filter, search, detail slide-over drawer, and one-click CSV export.
- **Health & Prometheus Metrics**: Subsystem readiness probes (database, cache, providers) and parsed Prometheus metrics view.
- **Linear/Vercel Design**: Dark mode default with light mode toggle, collapsible navigation sidebar, accessible focus states, and zero layout shift.

## Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment
```bash
cp .env.example .env
```
By default, the Vite dev server proxies `/api` and `/v1` requests to `http://localhost:8000`.

### 3. Start Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Build for Production
```bash
npm run build
npm run preview
```

### 5. Lint
```bash
npm run lint
```
