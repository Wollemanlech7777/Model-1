import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildCapabilityGroups,
  resolveCapabilityPhase,
  statusGlyph,
  type CapabilityPhase,
} from "./capability-map";
import type { PolicyReviewJob } from "./api";
import type { ProcessStepView } from "./chat-presentation";

function job(partial: Partial<PolicyReviewJob>): PolicyReviewJob {
  return {
    id: "job-1",
    status: "completed",
    policy_id: "POL-48291",
    decision: "execute",
    allow_external_write: true,
    avatar_state: "proud",
    crm_write: { attempted: true, performed: true, skipped: false },
    sources: { crm: "ACTIVE", legacy: "ACTIVE", portal: "ACTIVE" },
    timeline: [
      { event_type: "crm", message: "CRM GET → 200", success: true, timestamp: "t" },
      {
        event_type: "legacy",
        message: "Legacy lookup → match",
        success: true,
        timestamp: "t",
      },
      {
        event_type: "portal",
        message: "Portal fetch → 200",
        success: true,
        timestamp: "t",
      },
      {
        event_type: "decision",
        message: "Decision → EXECUTE",
        success: true,
        timestamp: "t",
      },
      {
        event_type: "crm_write",
        message: "CRM write → CREATED",
        success: true,
        timestamp: "t",
      },
    ],
    evidence: [
      {
        id: "e1",
        source: "portal",
        result: "ok",
        relevant_data: {},
        errors: [],
        timestamp: "t",
      },
      {
        id: "e2",
        source: "legacy",
        result: "ok",
        relevant_data: {},
        errors: [],
        timestamp: "t",
      },
    ],
    progress: [
      "Checking CRM",
      "Checking legacy data",
      "Reading email",
      "Checking portal",
    ],
    assistant_summary: "ok",
    reasons: [],
    interpretation: { summary: "Clear to proceed", source: "gemini" },
    interpretation_source: "gemini",
    ...partial,
  };
}

function findStatus(groups: ReturnType<typeof buildCapabilityGroups>, id: string) {
  for (const g of groups) {
    const item = g.items.find((i) => i.id === id);
    if (item) return item.status;
  }
  return undefined;
}

describe("capability-map", () => {
  it("idle keeps structural done and dynamic empty", () => {
    const groups = buildCapabilityGroups({
      phase: "idle",
      job: null,
      liveSteps: [],
    });
    assert.equal(findStatus(groups, "python"), "done");
    assert.equal(findStatus(groups, "timeouts"), "done");
    assert.equal(findStatus(groups, "external-api"), "idle");
    assert.equal(findStatus(groups, "decision-engine"), "idle");
    assert.equal(statusGlyph("idle"), "○");
  });

  it("running before job marks workflow running", () => {
    const phase = resolveCapabilityPhase({
      busy: true,
      awaitingJob: true,
      liveSteps: [],
      job: null,
      transportFailed: false,
    });
    assert.equal(phase, "running");
    const groups = buildCapabilityGroups({ phase, job: null, liveSteps: [] });
    assert.equal(findStatus(groups, "workflow-automation"), "running");
    assert.equal(findStatus(groups, "decision-engine"), "running");
    assert.equal(statusGlyph("running"), "◌");
  });

  it("execute success marks portal, decision, evidence", () => {
    const groups = buildCapabilityGroups({
      phase: "completed",
      job: job({}),
      liveSteps: [],
    });
    assert.equal(findStatus(groups, "external-api"), "done");
    assert.equal(findStatus(groups, "legacy-systems"), "done");
    assert.equal(findStatus(groups, "workflow-automation"), "done");
    assert.equal(findStatus(groups, "decision-engine"), "done");
    assert.equal(findStatus(groups, "ai-interpretation"), "done");
    assert.equal(findStatus(groups, "evidence-execution"), "done");
  });

  it("early fail without portal leaves external api idle", () => {
    const groups = buildCapabilityGroups({
      phase: "completed",
      job: job({
        decision: "fail",
        policy_id: "POL-77102",
        sources: {},
        progress: ["Checking CRM"],
        timeline: [
          {
            event_type: "crm",
            message: "CRM GET → 401",
            success: false,
            timestamp: "t",
          },
          {
            event_type: "decision",
            message: "Decision → FAIL",
            success: true,
            timestamp: "t",
          },
        ],
        evidence: [
          {
            id: "e",
            source: "crm",
            result: "error",
            relevant_data: {},
            errors: ["401: unauthorized"],
            timestamp: "t",
          },
        ],
        crm_write: { attempted: false, performed: false, skipped: true },
        interpretation: null,
        interpretation_source: null,
      }),
      liveSteps: [],
    });
    assert.equal(findStatus(groups, "external-api"), "idle");
    assert.equal(findStatus(groups, "legacy-systems"), "idle");
    assert.equal(findStatus(groups, "decision-engine"), "done");
    assert.equal(findStatus(groups, "workflow-automation"), "done");
    assert.equal(findStatus(groups, "evidence-execution"), "done");
    assert.equal(findStatus(groups, "ai-interpretation"), "idle");
  });

  it("portal failure marks external api error", () => {
    const groups = buildCapabilityGroups({
      phase: "completed" as CapabilityPhase,
      job: job({
        decision: "fail",
        sources: { portal: "ERROR" },
        timeline: [
          {
            event_type: "portal",
            message: "Portal fetch → 500",
            success: false,
            timestamp: "t",
          },
          {
            event_type: "decision",
            message: "Decision → FAIL",
            success: true,
            timestamp: "t",
          },
        ],
        evidence: [
          {
            id: "e",
            source: "portal",
            result: "error",
            relevant_data: {},
            errors: ["500: upstream"],
            timestamp: "t",
          },
        ],
        crm_write: { attempted: false, performed: false, skipped: true },
      }),
      liveSteps: [],
    });
    assert.equal(findStatus(groups, "external-api"), "error");
    assert.equal(statusGlyph("error"), "!");
  });

  it("live portal step active shows running glyph state", () => {
    const liveSteps: ProcessStepView[] = [
      {
        key: "Checking CRM",
        activeLabel: "Checking CRM",
        doneLabel: "CRM checked",
        status: "done",
      },
      {
        key: "Checking legacy data",
        activeLabel: "Checking legacy data",
        doneLabel: "Legacy checked",
        status: "done",
      },
      {
        key: "Reading email",
        activeLabel: "Reading email",
        doneLabel: "Email checked",
        status: "done",
      },
      {
        key: "Checking portal",
        activeLabel: "Checking portal",
        doneLabel: "Portal checked",
        status: "active",
      },
    ];
    const groups = buildCapabilityGroups({
      phase: "running",
      job: job({}),
      liveSteps,
    });
    assert.equal(findStatus(groups, "external-api"), "running");
    assert.equal(findStatus(groups, "legacy-systems"), "done");
  });

  it("transport failure without job is failed phase", () => {
    assert.equal(
      resolveCapabilityPhase({
        busy: false,
        awaitingJob: false,
        liveSteps: [],
        job: null,
        transportFailed: true,
      }),
      "failed",
    );
  });
});
