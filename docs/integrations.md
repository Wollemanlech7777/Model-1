# Integrations (skeleton)

Interfaces only — no simulated systems implemented yet.

| Adapter | Module | Responsibility |
| ------- | ------ | -------------- |
| CRM | `integrations/crm` | REST read + gated write (`create_activity`) |
| Legacy | `integrations/legacy` | Tabular fetch + candidate matching |
| Email | `integrations/email` | Unstructured message access |
| Portal | `integrations/portal` | HTML fetch + structured extraction |

All adapters extend `integrations.base.IntegrationAdapter` with `healthcheck` and `discover`.
