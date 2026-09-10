# Architecture (skeleton)

Site Companion is split into:

1. **Discovery / configuration** — customer environments and connectors (schema ready; flows TBD)
2. **Integrations** — abstract adapters under `/integrations` (CRM, legacy, email, portal)
3. **Deterministic decision engine** — `EXECUTE | REVIEW | FAIL` under `apps/api/app/services/decision`
4. **AI presentation layer** — optional structured semantic UI state (`ai/schemas`); never write authority
5. **Persistence** — PostgreSQL via SQLAlchemy ORM models

Demo workflow is **not defined yet**. Do not hardcode a business scenario into the engine until the 90-second demo path is chosen.

See the root [README.md](../README.md) for product thesis.
