# Local persistence (PostgreSQL)

Jobs, evidence, timeline, decisions, presentation state, and CRM activities are stored in PostgreSQL. Simulated external systems (`WORLD` fixtures for POL-2831 / POL-48291 / POL-77102) remain in-memory only.

## 1. Start PostgreSQL

From the repo root:

```bash
docker compose up -d db
```

Defaults (also in `.env` / `apps/api/.env.example`):

```text
DATABASE_URL=postgresql+psycopg://site:site@localhost:5432/site_companion
```

## 2. Install API deps + run migrations

```bash
cd apps/api
source .venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Do **not** use `create_all` as a substitute for Alembic.

## 3. Seed / demo data

No SQL seed is required for the three demo policies. Fixtures live in:

`integrations/simulated_world.py` → `POLICY_FIXTURES`

- `POL-2831` → REVIEW (no CRM write)
- `POL-48291` → EXECUTE (exactly one CRM activity, idempotent per job)
- `POL-77102` → FAIL (no CRM write)

Optional CRM reset (clears persisted CRM activities + resets simulated world):

```bash
curl -X POST http://127.0.0.1:8000/crm/reset-demo
```

## 4. Start API

```bash
cd apps/api
source .venv/bin/activate
PYTHONPATH="$(pwd):$(pwd)/../.." uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From repo root equivalent:

```bash
cd apps/api && source .venv/bin/activate
PYTHONPATH="/path/to/Model-1-main/apps/api:/path/to/Model-1-main" \
  uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 5. Start Web

```bash
cd apps/web
npm install
npm run dev -- -p 3000
```

Open `http://localhost:3000`.

## 6. Verify persistence after restart

```bash
# Create a job
curl -s -X POST http://127.0.0.1:8000/jobs/policy-review \
  -H 'Content-Type: application/json' \
  -d '{"message":"Revisa la póliza POL-48291"}'

# Note the returned id, restart the API process, then:
curl -s http://127.0.0.1:8000/jobs/<job_id>
curl -s http://127.0.0.1:8000/crm/activities
```

## 7. Tests

```bash
cd apps/api && source .venv/bin/activate
PYTHONPATH="$(pwd):$(pwd)/../.." pytest -q
```

Persistence tests require Postgres up and migrations applied; they skip automatically if the DB is unreachable.
