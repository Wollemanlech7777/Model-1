# Avatar / presentation state (skeleton)

Two pipelines:

1. **Operational** — decision engine → `EXECUTE | REVIEW | FAIL`
2. **Presentation** — optional Claude → validated `PresentationStateSchema` → compact UI character

Fallback without Claude maps:

- `EXECUTE` → `proud`
- `REVIEW` → `quizzical`
- `FAIL` → `stressed`

Schema: `ai/schemas/presentation_state.py`

If using Bible Strong Avatar Lab runtime, review **AGPL-3.0** obligations; otherwise ship owned SVG/PNG expressions.
