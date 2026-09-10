import json

import pytest

from app.models.enums import DecisionOutcome
from app.services.gemini.client import GeminiClient, GeminiClientError
from app.services.gemini.context_pack import build_context_pack
from app.services.gemini.fallback import fallback_interpretation
from app.services.gemini.interpret import answer_job_question, apply_interpretation, interpret_job
from app.services.gemini.validate import (
    InterpretationValidationError,
    parse_and_validate_interpretation,
)
from app.services.job_store import InMemoryJobStore
from app.services.policy_review.orchestrator import PolicyReviewOrchestrator
from integrations.simulated_world import WORLD


def setup_function() -> None:
    WORLD.reset()


def _sample_job() -> dict:
    orch = PolicyReviewOrchestrator(store=InMemoryJobStore(), skip_interpretation=True)
    return orch.run_from_message("Revisa la póliza POL-2831")


def _valid_payload(job: dict) -> dict:
    return {
        "summary": "Hay contradicción entre fuentes para POL-2831. No hice cambios.",
        "explanation": (
            "CRM y legacy reportan ACTIVE, mientras email y portal reportan CANCELLED. "
            "La decisión fue REVIEW y el CRM no fue modificado."
        ),
        "semantic_state": "ambiguous",
        "severity": "medium",
        "reason": "conflicting_source_status",
        "expression": "confused",
        "animation": "confused",
    }


def test_valid_gemini_response() -> None:
    job = _sample_job()
    context = build_context_pack(job)
    model = parse_and_validate_interpretation(_valid_payload(job), context)
    assert model.animation == "confused"
    assert model.semantic_state == "ambiguous"


def test_invalid_json() -> None:
    job = _sample_job()
    with pytest.raises(InterpretationValidationError) as exc:
        parse_and_validate_interpretation("{not-json", build_context_pack(job))
    assert "invalid_json" in exc.value.message


def test_missing_field() -> None:
    job = _sample_job()
    payload = _valid_payload(job)
    del payload["summary"]
    with pytest.raises(InterpretationValidationError) as exc:
        parse_and_validate_interpretation(payload, build_context_pack(job))
    assert "schema_validation" in exc.value.message


def test_invalid_enum() -> None:
    job = _sample_job()
    payload = _valid_payload(job)
    payload["animation"] = "not-a-real-animation"
    with pytest.raises(InterpretationValidationError) as exc:
        parse_and_validate_interpretation(payload, build_context_pack(job))
    assert "schema_validation" in exc.value.message


def test_invented_facts_rejected() -> None:
    job = _sample_job()
    payload = _valid_payload(job)
    payload["explanation"] = "También vi POL-99999 en estado EXPIRED."
    with pytest.raises(InterpretationValidationError) as exc:
        parse_and_validate_interpretation(payload, build_context_pack(job))
    assert "invented_" in exc.value.message


def test_missing_api_key_fallback() -> None:
    job = _sample_job()

    def boom(_system: str, _user: str) -> str:
        raise GeminiClientError("missing_api_key")

    interpretation = interpret_job(job, client=GeminiClient(generate_fn=boom))
    assert interpretation["source"] == "fallback"
    assert interpretation["animation"] == "confused"
    merged = apply_interpretation(job, interpretation)
    assert merged["decision"] == DecisionOutcome.REVIEW.value
    assert merged["crm_write"]["skipped"] is True


def test_timeout_error_fallback() -> None:
    job = _sample_job()

    def boom(_system: str, _user: str) -> str:
        raise GeminiClientError("gemini_error:timeout")

    interpretation = interpret_job(job, client=GeminiClient(generate_fn=boom))
    assert interpretation["source"] == "fallback"


def test_deterministic_fallback_content() -> None:
    job = _sample_job()
    fb = fallback_interpretation(job)
    assert fb["source"] == "fallback"
    assert "contradictoria" in fb["summary"].lower()
    assert "decision_not_execute" not in fb["explanation"]
    assert "{'crm'" not in fb["explanation"]


def test_interpret_does_not_change_decision_or_writes() -> None:
    job = _sample_job()
    payload = _valid_payload(job)

    def ok(_system: str, _user: str) -> str:
        return json.dumps(payload)

    interpretation = interpret_job(job, client=GeminiClient(generate_fn=ok))
    assert interpretation["source"] == "gemini"
    merged = apply_interpretation(job, interpretation)
    assert merged["decision"] == "review"
    assert merged["allow_external_write"] is False
    assert merged["crm_write"]["performed"] is False
    assert WORLD.crm_activities == []


def test_contextual_question_about_job() -> None:
    job = _sample_job()

    def ask_fn(system: str, user: str) -> str:
        assert "Context pack" in user
        return json.dumps(
            {
                "answer": (
                    "No actualicé el CRM porque hubo conflicto ACTIVE vs CANCELLED "
                    "y la decisión fue REVIEW."
                )
            }
        )

    result = answer_job_question(
        job,
        "¿Por qué no actualizaste el CRM?",
        client=GeminiClient(generate_fn=ask_fn),
    )
    assert result["source"] == "gemini"
    assert "REVIEW" in result["answer"] or "CRM" in result["answer"]


def test_contextual_question_fallback() -> None:
    job = _sample_job()

    def boom(_system: str, _user: str) -> str:
        raise GeminiClientError("gemini_error:down")

    result = answer_job_question(
        job,
        "¿Qué fuente causó el conflicto?",
        client=GeminiClient(generate_fn=boom),
    )
    assert result["source"] == "fallback"
    answer = result["answer"]
    assert "ACTIVA" in answer or "ACTIVE" in answer
    assert "CANCELADA" in answer or "CANCELLED" in answer
    assert "decision_not_execute" not in answer
    assert "conflict:policy_status" not in answer
    assert "{'crm'" not in answer
    assert '{"crm"' not in answer


def test_ask_fallback_natural_language_for_three_cases() -> None:
    from app.services.gemini.interpret import _deterministic_ask_fallback

    review = PolicyReviewOrchestrator(
        store=InMemoryJobStore(), skip_interpretation=True
    ).run_from_message("Revisa la póliza POL-2831")
    a1 = _deterministic_ask_fallback(review, "¿Qué fuentes están en conflicto?")
    assert "CRM" in a1 and "Portal" in a1
    assert "decision_not_execute" not in a1
    assert "conflict:policy_status" not in a1

    a2 = _deterministic_ask_fallback(review, "¿Por qué no actualizaste el CRM?")
    assert "contradictoria" in a2.lower() or "revisión manual" in a2.lower()
    assert "decision_not_execute" not in a2

    WORLD.reset()
    execute = PolicyReviewOrchestrator(
        store=InMemoryJobStore(), skip_interpretation=True
    ).run_from_message("Revisa la póliza POL-48291")
    a3 = _deterministic_ask_fallback(execute, "¿Qué pasó?")
    assert "CRM" in a3
    assert "decision_not_execute" not in a3

    WORLD.reset()
    fail = PolicyReviewOrchestrator(
        store=InMemoryJobStore(), skip_interpretation=True
    ).run_from_message("Revisa la póliza POL-77102")
    a4 = _deterministic_ask_fallback(fail, "¿Qué pasó?")
    assert "401" in a4
    assert "decision_not_execute" not in a4


def test_gemini_answer_with_internal_leak_is_sanitized() -> None:
    job = _sample_job()

    def leak(_system: str, _user: str) -> str:
        return json.dumps(
            {
                "answer": "Motivos: conflict:policy_status:crm='ACTIVE' decision_not_execute"
            }
        )

    result = answer_job_question(
        job,
        "¿Por qué no actualizaste el CRM?",
        client=GeminiClient(generate_fn=leak),
    )
    assert result["source"] == "fallback"
    assert "decision_not_execute" not in result["answer"]
    assert "conflict:policy_status" not in result["answer"]


def test_three_cases_still_operationally_identical_with_interpretation_layer() -> None:
    def invalid(_system: str, _user: str) -> str:
        return "not-json"

    client = GeminiClient(generate_fn=invalid)
    orch = PolicyReviewOrchestrator(store=InMemoryJobStore(), gemini_client=client)

    r1 = orch.run_from_message("Revisa la póliza POL-2831")
    assert r1["decision"] == "review"
    assert r1["crm_write"]["performed"] is False
    assert r1["interpretation_source"] == "fallback"

    WORLD.reset()
    orch = PolicyReviewOrchestrator(store=InMemoryJobStore(), gemini_client=client)
    r2 = orch.run_from_message("Revisa la póliza POL-48291")
    assert r2["decision"] == "execute"
    assert r2["crm_write"]["performed"] is True
    assert len(WORLD.crm_activities) == 1

    WORLD.reset()
    orch = PolicyReviewOrchestrator(store=InMemoryJobStore(), gemini_client=client)
    r3 = orch.run_from_message("Revisa la póliza POL-77102")
    assert r3["decision"] == "fail"
    assert r3["crm_write"]["performed"] is False
    assert WORLD.crm_activities == []
