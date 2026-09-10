# Reliability (skeleton)

- Deterministic code owns `allow_external_write`
- Integration failures that block writes → `FAIL`
- Conflicts and ambiguous matches → `REVIEW`
- Auth / hard failures stop before side effects
- Avatar / Claude presentation state cannot override decision outcomes
- Fallback expression map exists when AI is unavailable

Implementation status: decision engine skeleton + schema only.
