# Site Companion

**An AI operations assistant for insurance back-office workflows.**

Site Companion helps brokers and insurance operations agents verify policy information across connected systems before taking action. Given a policy number that the operator already has, it checks CRM, legacy data, email, and the insurer portal, reconciles the evidence, and uses a deterministic Decision Engine to decide whether the workflow can proceed safely.

---

## Problem

When handling a request for an existing policy, an operations agent typically already has the policy number. Before processing the request, they must manually confirm that the same policy looks consistent across several systems:

- CRM
- Legacy system
- Email
- Insurer portal

That multi-system check is slow, easy to get wrong, and hard to audit. Site Companion automates the verification and records evidence for every run.

---

## What it does

1. The operator provides a **policy number** (for example `POL-48291`).
2. Site Companion reads the connected systems through the environment’s connectors.
3. Evidence is collected and compared.
4. The **Decision Engine** returns one of:
   - **EXECUTE** — information is consistent; the configured external write is allowed
   - **REVIEW** — sources conflict or are ambiguous; no external write
   - **FAIL** — a blocking condition prevents completing the workflow; no external write
5. On **EXECUTE** only, Site Companion creates a CRM verification activity (idempotent).

Site Companion does **not** search for or discover policies. The policy number is an input the operator already has.

---

## Architecture

```text
Customer
   ↓
Environment
   ↓
Connectors (crm | legacy | email | portal)
   ↓
Adapter Factory
   ↓
Policy Review workflow
   ↓
Evidence + normalization
   ↓
Decision Engine → EXECUTE | REVIEW | FAIL
   ↓
Controlled action (CRM write only on EXECUTE)
   ↓
PostgreSQL (jobs, evidence, timeline, decisions, presentation, CRM activities)
```

### Persistence

Jobs, evidence, execution timeline, decisions, presentation state, customers, environments, connectors, and CRM activities are stored in **PostgreSQL**. The project’s current environment uses **Supabase** as hosted PostgreSQL (`DATABASE_URL`). Schema changes are applied with **Alembic**.

### Adapter Factory

Each environment declares connectors with an adapter kind. The factory resolves:

| Connector | Typical adapter |
| --------- | --------------- |
| CRM | `simulated` |
| Legacy | `simulated` |
| Email | `simulated` |
| Portal | `simulated` or `real` (CyberNotes) |

### CyberNotes (real portal)

The **CyberNotes Sandbox** environment uses a **real** portal adapter against the CyberNotes MTPL API. Credentials are supplied only through environment variables (`CYBERNOTES_CLIENT_ID` / `CYBERNOTES_CLIENT_SECRET`) and are never stored in connector config or returned by the API. Access tokens are held in process memory only for the request lifecycle.

The web app targets the CyberNotes Sandbox environment id:

`2f46645e-35ff-4865-b7ed-88285c96d25a`

### CRM write idempotency

For a given `policy_id` + activity type (`policy_status_review`), PostgreSQL enforces uniqueness. Re-running **EXECUTE** for the same policy does not create a second CRM activity row.

### Presentation vs authority

Gemini may produce a human-readable interpretation of a completed job for the UI. It does **not** override the Decision Engine or authorize writes. Operational authority remains deterministic.

---

## Demo policies

| Policy | Outcome | External write |
| ------ | ------- | -------------- |
| `POL-48291` | **EXECUTE** | CRM verification activity (once) |
| `POL-2831` | **REVIEW** | None |
| `POL-77102` | **FAIL** | None |

In the CyberNotes Sandbox, `POL-48291` is mapped to a real portal policy id for live portal verification.

---

## Security and hardening

- CORS allowlist (no wildcard with credentials)
- Request body validation and size limits
- Rate limiting on `POST /jobs/policy-review`
- Timeouts for CyberNotes and Gemini calls
- `X-Request-ID` correlation on responses
- Log redaction for secrets / bearer tokens
- `GET /health` (liveness) and `GET /ready` (database readiness)
- `POST /crm/reset-demo` disabled in production unless explicitly allowed

There is no end-user authentication layer in the current demo surface; treat network exposure accordingly.

---

## Repository layout

```text
apps/
  api/            # FastAPI — routes, orchestrator, Decision Engine, adapters, persistence
  web/            # Next.js — chat shell, evidence UI, capabilities, startup
integrations/     # Simulated world fixtures and shared integration helpers
ai/               # Presentation schemas / prompts
docs/             # Additional architecture and persistence notes
docker-compose.yml
```

---

## Local setup

### 1. Database

Point `DATABASE_URL` at the project’s **Supabase** PostgreSQL instance (primary setup).

Optional alternative for fully local development: Docker Compose Postgres (`docker compose up -d db`) with a matching local `DATABASE_URL`.

### 2. Environment

Copy `.env.example` to `.env` at the repo root and fill values locally. Never commit real secrets.

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | PostgreSQL connection string |
| `GEMINI_API_KEY` | Gemini API key (presentation / ask); optional for core decisioning |
| `ENVIRONMENT` | `development` / `staging` / `production` |
| `LOG_LEVEL` | Logging verbosity |
| `CYBERNOTES_CLIENT_ID` | CyberNotes OAuth client id |
| `CYBERNOTES_CLIENT_SECRET` | CyberNotes OAuth client secret |
| `CYBERNOTES_BASE_URL` | CyberNotes MTPL API base URL |
| `CYBERNOTES_TIMEOUT_SECONDS` | Portal HTTP timeout |
| `GEMINI_TIMEOUT_SECONDS` | Gemini call timeout |
| `CORS_ORIGINS` | Allowed browser origins (comma-separated) |
| `CORS_ALLOW_CREDENTIALS` | CORS credentials flag |
| `RATE_LIMIT_POLICY_REVIEW_PER_MINUTE` | Policy-review rate limit (`0` disables) |
| `ENABLE_DEMO_RESET` | Allow demo reset endpoint (auto-off in production unless forced) |

Optional web override:

| Variable | Purpose |
| -------- | ------- |
| `NEXT_PUBLIC_API_URL` | API base URL (defaults to `` `http://127.0.0.1:8000` ``) |

### 3. API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Seed environments (idempotent)
PYTHONPATH="$(pwd):$(pwd)/../.." python -m app.services.seed_demo_environment
PYTHONPATH="$(pwd):$(pwd)/../.." python -m app.services.seed_cybernotes_sandbox

PYTHONPATH="$(pwd):$(pwd)/../.." uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. Web

```bash
cd apps/web
npm install
npm run dev -- -p 3000
```

Open `http://localhost:3000`.

---

## Running the demo

1. Start API + web with CyberNotes credentials configured for the real portal path.
2. Confirm seeds created **Demo Environment** and **CyberNotes Sandbox** (`2f46645e-35ff-4865-b7ed-88285c96d25a`).
3. In the UI, use **Review a policy** or send `Review policy POL-48291`.
4. Inspect the result card and **View evidence** for sources, decision, timeline, and CRM action.
5. Repeat with `POL-2831` (REVIEW) and `POL-77102` (FAIL).
6. Re-run `POL-48291` and confirm CRM activities remain a single row for that policy/type.

API equivalent:

```bash
curl -s -X POST http://127.0.0.1:8000/jobs/policy-review \
  -H 'Content-Type: application/json' \
  -d '{"message":"Review policy POL-48291","environment_id":"2f46645e-35ff-4865-b7ed-88285c96d25a"}'
```

Useful endpoints: `GET /health`, `GET /ready`, `GET /jobs/{id}/evidence`, `POST /jobs/{id}/ask`, `GET /crm/activities`.

---

## Tests

```bash
# Backend
cd apps/api
source .venv/bin/activate
pytest -q

# Frontend
cd apps/web
npm test
npm run typecheck
```

Coverage includes Decision Engine outcomes, policy review flows, adapter factory / portal adapter (mocked HTTP), persistence and CRM uniqueness, API hardening (CORS, validation, rate limits), observability helpers, and frontend API client / capability-map checks.

---

## Architecture decisions

**Why only the portal is a real integration today**

Insurance operations usually span several systems with uneven API quality. CRM, legacy, and email are represented with **simulated adapters** so the workflow, Decision Engine, evidence model, and UI can be developed and demonstrated without depending on every customer system being available. The **insurer portal** is the system that most often lacks a clean internal API; CyberNotes provides a real MTPL portal surface, so Site Companion implements a production-shaped **real portal adapter** (auth, timeouts, error mapping, no credential persistence) behind the same Adapter Factory interface.

That split keeps the architecture honest: one controlled path to a live external system, with the rest of the multi-source reconciliation model intact and swappable when additional real connectors are introduced.

---

## License

See [LICENSE](./LICENSE).
