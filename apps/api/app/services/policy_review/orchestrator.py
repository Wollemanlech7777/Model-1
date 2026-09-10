"""Orchestrate the policy-review workflow across simulated systems."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.enums import DecisionOutcome
from app.services.decision import DecisionEngine, IntegrationFailure
from app.services.job_store import JOB_STORE, JobStore
from app.services.policy_review.avatar_map import (
    avatar_state_for_outcome,
    avatar_state_for_running,
)
from app.services.gemini.interpret import apply_interpretation, interpret_job
from app.services.gemini.client import GeminiClient
from app.services.policy_review.extract import extract_policy_id
from app.services.policy_review.normalize import build_decision_context
from integrations.crm.interface import CRMAdapter
from integrations.crm.simulated import SimulatedCRMAdapter
from integrations.email.interface import EmailAdapter
from integrations.email.simulated import SimulatedEmailAdapter
from integrations.legacy.interface import LegacyAdapter
from integrations.legacy.simulated import SimulatedLegacyAdapter
from integrations.portal.interface import PortalAdapter
from integrations.portal.simulated import SimulatedPortalAdapter
from integrations.simulated_world import WORLD, SimulatedWorld


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(
    events: list[dict[str, Any]],
    *,
    event_type: str,
    message: str,
    success: bool = True,
    payload: dict[str, Any] | None = None,
) -> None:
    events.append(
        {
            "event_type": event_type,
            "message": message,
            "success": success,
            "payload": payload or {},
            "timestamp": _utc_now(),
        }
    )


def _evidence(
    items: list[dict[str, Any]],
    *,
    source: str,
    result: str,
    relevant_data: dict[str, Any],
    errors: list[str] | None = None,
) -> None:
    items.append(
        {
            "id": str(uuid4()),
            "source": source,
            "result": result,
            "relevant_data": relevant_data,
            "errors": errors or [],
            "timestamp": _utc_now(),
        }
    )


class PolicyReviewOrchestrator:
    def __init__(
        self,
        *,
        world: SimulatedWorld | None = None,
        store: JobStore | None = None,
        engine: DecisionEngine | None = None,
        gemini_client: GeminiClient | None = None,
        skip_interpretation: bool = False,
        crm: CRMAdapter | None = None,
        legacy: LegacyAdapter | None = None,
        email: EmailAdapter | None = None,
        portal: PortalAdapter | None = None,
        environment_id: str | None = None,
    ) -> None:
        self.world = world or WORLD
        self.store = store or JOB_STORE
        self.engine = engine or DecisionEngine()
        self.gemini_client = gemini_client
        self.skip_interpretation = skip_interpretation
        self.environment_id = environment_id
        self.crm = crm or SimulatedCRMAdapter(self.world)
        self.legacy = legacy or SimulatedLegacyAdapter(self.world)
        self.email = email or SimulatedEmailAdapter(self.world)
        self.portal = portal or SimulatedPortalAdapter(self.world)

    def _with_environment(self, result: dict[str, Any]) -> dict[str, Any]:
        if self.environment_id:
            result["environment_id"] = self.environment_id
        return result

    def run_from_message(self, message: str) -> dict[str, Any]:
        job_id = str(uuid4())
        events: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        progress: list[str] = []

        policy_id = extract_policy_id(message)
        if not policy_id:
            result = {
                "id": job_id,
                "status": "failed",
                "workflow_key": "policy_review",
                "policy_id": None,
                "input_message": message,
                "decision": DecisionOutcome.FAIL.value,
                "allow_external_write": False,
                "avatar_state": avatar_state_for_outcome(DecisionOutcome.FAIL),
                "crm_write": {
                    "attempted": False,
                    "performed": False,
                    "skipped": True,
                    "reason": "missing_policy_id",
                },
                "sources": {},
                "timeline": [
                    {
                        "event_type": "validation",
                        "message": "Policy ID not found in message",
                        "success": False,
                        "payload": {},
                        "timestamp": _utc_now(),
                    }
                ],
                "evidence": [],
                "progress": [],
                "assistant_summary": "No pude encontrar un ID de póliza (formato POL-#####).",
                "reasons": ["missing_policy_id"],
                "facts": {},
            }
            return self.store.save(self._with_interpretation(self._with_environment(result)))

        progress.append("Voy a revisar CRM, legacy data, email y portal.")
        _event(
            events,
            event_type="config",
            message=f"Created policy_review job for {policy_id}",
            payload={"policy_id": policy_id},
        )

        source_statuses: dict[str, str | None] = {}
        failures: list[IntegrationFailure] = []

        # --- CRM ---
        progress.append("Checking CRM")
        crm_result = self.crm.get_record("policy", policy_id)
        if not crm_result.success:
            code = crm_result.error_code or "error"
            _event(
                events,
                event_type="integration",
                message=f"CRM GET → {code}",
                success=False,
                payload={"error": crm_result.error_message, "code": code},
            )
            _evidence(
                evidence,
                source="crm",
                result="error",
                relevant_data={"policy_id": policy_id},
                errors=[f"{code}: {crm_result.error_message}"],
            )
            failures.append(
                IntegrationFailure(
                    connector="crm",
                    error_code=code,
                    message=crm_result.error_message or "CRM failure",
                    blocks_writes=True,
                )
            )

            # Auth / hard CRM failure: stop early.
            context = build_decision_context(
                policy_id=policy_id,
                source_statuses={},
                integration_failures=failures,
            )
            decision = self.engine.decide(context)
            return self._finalize(
                job_id=job_id,
                message=message,
                policy_id=policy_id,
                events=events,
                evidence=evidence,
                progress=progress,
                source_statuses={},
                decision_outcome=decision.outcome,
                reasons=decision.reasons,
                facts=decision.facts,
                early_stop=True,
            )

        crm_status = str(crm_result.data.get("status"))
        source_statuses["crm"] = crm_status
        _event(
            events,
            event_type="integration",
            message="CRM GET → 200",
            payload={"status": crm_status},
        )
        _evidence(
            evidence,
            source="crm",
            result="ok",
            relevant_data={"policy_id": policy_id, "status": crm_status},
        )

        # --- Legacy ---
        progress.append("Checking legacy data")
        legacy_result = self.legacy.fetch_rows({"policy_id": policy_id})
        if not legacy_result.success:
            _event(
                events,
                event_type="integration",
                message=f"Legacy lookup → {legacy_result.error_code}",
                success=False,
                payload={"error": legacy_result.error_message},
            )
            _evidence(
                evidence,
                source="legacy",
                result="error",
                relevant_data={"policy_id": policy_id},
                errors=[legacy_result.error_message or "legacy error"],
            )
            failures.append(
                IntegrationFailure(
                    connector="legacy",
                    error_code=legacy_result.error_code,
                    message=legacy_result.error_message or "legacy failure",
                    blocks_writes=True,
                )
            )
        else:
            row = legacy_result.data["rows"][0]
            legacy_status = str(row["status"])
            source_statuses["legacy"] = legacy_status
            _event(
                events,
                event_type="integration",
                message="Legacy lookup → match",
                payload={"status": legacy_status, "match": legacy_result.data.get("match")},
            )
            _evidence(
                evidence,
                source="legacy",
                result="ok",
                relevant_data={"policy_id": policy_id, "status": legacy_status, "row": row},
            )

        # --- Email ---
        progress.append("Reading email")
        listed = self.email.list_messages({"policy_id": policy_id})
        if not listed.success:
            _event(
                events,
                event_type="integration",
                message=f"Email read → {listed.error_code}",
                success=False,
                payload={"error": listed.error_message},
            )
            _evidence(
                evidence,
                source="email",
                result="error",
                relevant_data={"policy_id": policy_id},
                errors=[listed.error_message or "email error"],
            )
            failures.append(
                IntegrationFailure(
                    connector="email",
                    error_code=listed.error_code,
                    message=listed.error_message or "email failure",
                    blocks_writes=False,
                )
            )
        else:
            message_id = listed.data["messages"][0]["id"]
            email_result = self.email.get_message(message_id)
            email_status = str(email_result.data.get("status"))
            source_statuses["email"] = email_status
            _event(
                events,
                event_type="integration",
                message="Email read → success",
                payload={"status": email_status},
            )
            _evidence(
                evidence,
                source="email",
                result="ok",
                relevant_data={
                    "policy_id": policy_id,
                    "status": email_status,
                    "body": email_result.data.get("body"),
                },
            )

        # --- Portal ---
        progress.append("Checking portal")
        page = self.portal.fetch_page(f"/policies/{policy_id}")
        if not page.success:
            _event(
                events,
                event_type="integration",
                message=f"Portal fetch → {page.error_code}",
                success=False,
                payload={"error": page.error_message},
            )
            _evidence(
                evidence,
                source="portal",
                result="error",
                relevant_data={"policy_id": policy_id},
                errors=[page.error_message or "portal error"],
            )
            failures.append(
                IntegrationFailure(
                    connector="portal",
                    error_code=page.error_code,
                    message=page.error_message or "portal failure",
                    blocks_writes=False,
                )
            )
        else:
            extracted = self.portal.extract_structured(page.data["html"])
            portal_status = str(extracted.data.get("status"))
            source_statuses["portal"] = portal_status
            _event(
                events,
                event_type="integration",
                message="Portal fetch → 200",
                payload={"status": portal_status},
            )
            _evidence(
                evidence,
                source="portal",
                result="ok",
                relevant_data={"policy_id": policy_id, "status": portal_status},
            )

        context = build_decision_context(
            policy_id=policy_id,
            source_statuses=source_statuses,
            integration_failures=failures,
        )
        if context.conflicts:
            _event(
                events,
                event_type="validation",
                message="Conflict detected",
                success=True,
                payload={"conflicts": [c.__dict__ for c in context.conflicts]},
            )

        decision = self.engine.decide(context)
        return self._finalize(
            job_id=job_id,
            message=message,
            policy_id=policy_id,
            events=events,
            evidence=evidence,
            progress=progress,
            source_statuses=source_statuses,
            decision_outcome=decision.outcome,
            reasons=decision.reasons,
            facts=decision.facts,
            early_stop=False,
        )

    def _finalize(
        self,
        *,
        job_id: str,
        message: str,
        policy_id: str,
        events: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        progress: list[str],
        source_statuses: dict[str, str | None],
        decision_outcome: DecisionOutcome,
        reasons: list[str],
        facts: dict[str, Any],
        early_stop: bool,
    ) -> dict[str, Any]:
        allow_write = decision_outcome == DecisionOutcome.EXECUTE
        _event(
            events,
            event_type="decision",
            message=f"Decision → {decision_outcome.value.upper()}",
            payload={"reasons": reasons, "facts": facts},
        )

        crm_write: dict[str, Any]
        if allow_write:
            activity_payload = {
                "policy_id": policy_id,
                "type": "policy_status_review",
                "note": f"Site Companion verified consistent ACTIVE status for {policy_id}",
                "decision": decision_outcome.value,
            }
            write_result = self.crm.create_activity(activity_payload)
            crm_write = {
                "attempted": True,
                "performed": write_result.success,
                "skipped": False,
                "reason": None,
                "activity": write_result.data,
            }
            _event(
                events,
                event_type="action",
                message="CRM write → CREATED",
                payload=write_result.data,
            )
            _evidence(
                evidence,
                source="crm_write",
                result="created",
                relevant_data=write_result.data,
            )
            assistant_summary = (
                f"Fuentes alineadas para {policy_id}. Decisión EXECUTE. "
                "Creé una actividad en el CRM simulado."
            )
        else:
            reason = "decision_not_execute"
            if decision_outcome == DecisionOutcome.REVIEW:
                assistant_summary = (
                    f"Encontré información contradictoria sobre {policy_id}. No hice cambios."
                )
            elif early_stop:
                assistant_summary = (
                    f"Falló la autenticación/consulta CRM para {policy_id}. "
                    "Detuve la ejecución. No hice cambios."
                )
            else:
                assistant_summary = f"No pude completar la revisión de {policy_id}. No hice cambios."

            crm_write = {
                "attempted": False,
                "performed": False,
                "skipped": True,
                "reason": reason,
            }
            _event(
                events,
                event_type="action",
                message="CRM write → SKIPPED",
                success=True,
                payload={"reason": reason, "decision": decision_outcome.value},
            )

        for item in evidence:
            item["decision"] = decision_outcome.value

        result = {
            "id": job_id,
            "status": "completed",
            "workflow_key": "policy_review",
            "policy_id": policy_id,
            "input_message": message,
            "decision": decision_outcome.value,
            "allow_external_write": allow_write,
            "avatar_state": avatar_state_for_outcome(decision_outcome),
            "running_avatar_state": avatar_state_for_running(),
            "crm_write": crm_write,
            "sources": source_statuses,
            "timeline": events,
            "evidence": evidence,
            "progress": progress,
            "assistant_summary": assistant_summary,
            "reasons": reasons,
            "facts": facts,
        }
        return self.store.save(self._with_interpretation(self._with_environment(result)))

    def _with_interpretation(self, result: dict[str, Any]) -> dict[str, Any]:
        if self.skip_interpretation:
            return result
        interpretation = interpret_job(result, client=self.gemini_client)
        # Operational fields are frozen inside apply_interpretation.
        decision_before = result.get("decision")
        allow_before = result.get("allow_external_write")
        write_before = result.get("crm_write")
        env_before = result.get("environment_id")
        merged = apply_interpretation(result, interpretation)
        merged["decision"] = decision_before
        merged["allow_external_write"] = allow_before
        merged["crm_write"] = write_before
        if env_before is not None:
            merged["environment_id"] = env_before
        _event(
            merged.setdefault("timeline", []),
            event_type="ai",
            message=f"Interpretation → {merged.get('interpretation_source', 'fallback')}",
            payload={
                "source": merged.get("interpretation_source"),
                "semantic_state": (merged.get("presentation") or {}).get("semantic_state"),
            },
        )
        return merged
