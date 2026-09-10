/** Human presentation of job evidence — display only, no operational changes. */

export type EvidencePayload = {
  job_id?: string;
  decision?: string;
  evidence?: Array<{
    id?: string;
    source: string;
    result: string;
    relevant_data?: Record<string, unknown>;
    errors?: string[];
    timestamp?: string;
  }>;
  timeline?: Array<{
    event_type: string;
    message: string;
    success: boolean;
    payload?: Record<string, unknown>;
    timestamp?: string;
  }>;
  sources?: Record<string, string>;
  reasons?: string[];
  interpretation?: Record<string, unknown> | null;
  presentation?: Record<string, unknown> | null;
};

export type EvidenceSourceRow = {
  name: string;
  status: string;
  mark: "ok" | "warn" | "error";
};

export type EvidenceTimelineItem = {
  kind: "ok" | "error" | "stop";
  label: string;
};

export type EvidenceViewModel = {
  policyId: string;
  decisionLabel: string;
  sources: EvidenceSourceRow[];
  reason: string;
  actionTitle: string;
  actionDescription: string;
  timeline: EvidenceTimelineItem[];
};

const SOURCE_LABELS: Record<string, string> = {
  crm: "CRM",
  legacy: "Legacy",
  email: "Email",
  portal: "Portal",
};

const SOURCE_ORDER = ["crm", "legacy", "email", "portal"] as const;

/** Real Decision Engine outcomes — never map EXECUTE → SUCCESS. */
export function decisionToLabel(decision: string | null | undefined): string {
  switch ((decision || "").toLowerCase()) {
    case "execute":
      return "EXECUTE";
    case "review":
      return "REVIEW";
    case "fail":
      return "FAIL";
    default:
      return (decision || "UNKNOWN").toUpperCase();
  }
}

function extractPolicyId(payload: EvidencePayload, fallback?: string | null): string {
  if (fallback) return fallback;
  for (const item of payload.evidence || []) {
    const id = item.relevant_data?.policy_id;
    if (typeof id === "string" && id) return id;
  }
  for (const event of payload.timeline || []) {
    const match = event.message.match(/\bPOL-\d+\b/i);
    if (match) return match[0].toUpperCase();
  }
  return "—";
}

export function humanReason(payload: EvidencePayload): string {
  const decision = (payload.decision || "").toLowerCase();
  const reasons = payload.reasons || [];
  const joined = reasons.join(" ").toLowerCase();

  if (reasons.some((r) => r.startsWith("conflict:policy_status"))) {
    return "The evidence was not consistent enough to execute. The workflow stopped for human review.";
  }
  if (reasons.includes("checks_passed")) {
    return "All connected sources reported a consistent policy status.";
  }

  const fail = reasons.find((r) => r.startsWith("integration_failure:"));
  if (fail) {
    const parts = fail.split(":");
    const system = parts[1] || "system";
    const code = parts[2];
    const detail = parts.slice(3).join(":") || "";
    const systemLabel = SOURCE_LABELS[system] || system.toUpperCase();
    const failureDetail = code
      ? `The ${systemLabel} request failed with ${code}${detail ? ` ${detail}` : ""}.`.replace(
          /\s+/g,
          " ",
        )
      : `The ${systemLabel} integration failed.`;
    return `${failureDetail} That condition prevents completing the workflow.`;
  }

  if (joined.includes("401")) {
    return "The CRM request failed with 401 Unauthorized. That condition prevents completing the workflow.";
  }

  if (decision === "review") {
    return "The evidence was not consistent enough to execute. The workflow stopped for human review.";
  }

  if (decision === "fail") {
    return "A condition prevented the workflow from completing. The workflow stopped.";
  }

  if (reasons.length === 0) {
    return "No additional reason codes were recorded.";
  }

  return reasons.map(readableReasonToken).join(" ");
}

function readableReasonToken(reason: string): string {
  if (reason.startsWith("conflict:policy_status")) {
    return "The evidence was not consistent enough to execute.";
  }
  if (reason === "checks_passed") {
    return "All connected sources reported a consistent policy status.";
  }
  if (reason.startsWith("integration_failure:")) {
    return humanReason({ reasons: [reason], decision: "fail" });
  }
  return reason.replace(/_/g, " ");
}

export function humanAction(
  payload: EvidencePayload,
  crmWrite?: {
    attempted?: boolean;
    performed?: boolean;
    skipped?: boolean;
    reason?: string | null;
  } | null,
): { title: string; description: string } {
  const decision = (payload.decision || "").toLowerCase();
  const timeline = payload.timeline || [];
  const writeCreated = timeline.some(
    (event) =>
      event.event_type === "action" &&
      /CRM write → CREATED/i.test(event.message),
  );

  if (decision === "execute" || writeCreated || crmWrite?.performed) {
    return {
      title: "CRM verification activity created",
      description:
        "The policy passed verification, so the workflow executed the configured CRM action.",
    };
  }

  if (decision === "review") {
    return {
      title: "No external action taken",
      description:
        "The evidence was not consistent enough to execute. The workflow stopped for human review and no external action was executed.",
    };
  }

  if (decision === "fail") {
    return {
      title: "No external action taken",
      description:
        "A condition prevented completing the workflow. The workflow stopped and no external action was executed.",
    };
  }

  return {
    title: "No external action recorded",
    description: "No CRM changes were recorded for this run.",
  };
}

function sourceRows(payload: EvidencePayload): EvidenceSourceRow[] {
  const sources = payload.sources || {};
  const keys = SOURCE_ORDER.filter((key) => key in sources);

  if (keys.length === 0) {
    return (payload.evidence || [])
      .filter((item) => item.source !== "crm_write")
      .map((item) => {
        const name = SOURCE_LABELS[item.source] || item.source;
        const status =
          typeof item.relevant_data?.status === "string"
            ? String(item.relevant_data.status)
            : item.errors?.[0] || item.result.toUpperCase();
        const mark: EvidenceSourceRow["mark"] =
          item.result === "ok" ? "ok" : "error";
        return { name, status, mark };
      });
  }

  const crmStatus = sources.crm;
  return keys.map((key) => {
    const status = sources[key];
    let mark: EvidenceSourceRow["mark"] = "ok";
    if (crmStatus && status !== crmStatus) mark = "warn";
    return {
      name: SOURCE_LABELS[key] || key,
      status,
      mark,
    };
  });
}

function timelineItems(payload: EvidencePayload): EvidenceTimelineItem[] {
  const items: EvidenceTimelineItem[] = [];
  const timeline = payload.timeline || [];
  const reasons = payload.reasons || [];
  const checksPassed = reasons.includes("checks_passed");

  for (const event of timeline) {
    const message = event.message;

    if (event.event_type === "integration") {
      if (/CRM GET → 200/i.test(message)) {
        items.push({ kind: "ok", label: "CRM checked" });
      } else if (/CRM GET → 401/i.test(message)) {
        items.push({
          kind: "error",
          label: "CRM request failed — 401 Unauthorized",
        });
        items.push({ kind: "stop", label: "Process stopped" });
      } else if (/CRM GET →/i.test(message) && !event.success) {
        const code = message.match(/CRM GET →\s*(\S+)/i)?.[1] || "error";
        items.push({ kind: "error", label: `CRM request failed — ${code}` });
        items.push({ kind: "stop", label: "Process stopped" });
      } else if (/Legacy lookup →/i.test(message) && event.success) {
        items.push({ kind: "ok", label: "Legacy checked" });
      } else if (/Email read →/i.test(message) && event.success) {
        items.push({ kind: "ok", label: "Email checked" });
      } else if (/Portal fetch →/i.test(message) && event.success) {
        items.push({ kind: "ok", label: "Portal checked" });
      }
      continue;
    }

    if (event.event_type === "validation") {
      if (/Conflict detected/i.test(message)) {
        items.push({ kind: "stop", label: "Evidence compared — conflict found" });
      }
      continue;
    }

    if (event.event_type === "decision") {
      const match = message.match(/Decision\s*→\s*(\w+)/i);
      if (match) {
        // Present the real DecisionEngine reason "checks_passed" as reconciliation.
        if (
          checksPassed &&
          !items.some((i) => /Evidence compared|Evidence reconciled/i.test(i.label))
        ) {
          items.push({ kind: "ok", label: "Evidence reconciled" });
        }
        items.push({
          kind: "ok",
          label: `Decision: ${match[1].toUpperCase()}`,
        });
      }
      continue;
    }

    if (event.event_type === "action") {
      if (/CRM write → CREATED/i.test(message)) {
        items.push({ kind: "ok", label: "CRM activity created" });
      } else if (/CRM write → SKIPPED/i.test(message)) {
        items.push({ kind: "stop", label: "No external action taken" });
      }
    }
  }

  return items;
}

export function buildEvidenceView(
  payload: EvidencePayload,
  options?: {
    policyId?: string | null;
    crmWrite?: {
      attempted?: boolean;
      performed?: boolean;
      skipped?: boolean;
      reason?: string | null;
    } | null;
  },
): EvidenceViewModel {
  const action = humanAction(payload, options?.crmWrite);
  return {
    policyId: extractPolicyId(payload, options?.policyId),
    decisionLabel: decisionToLabel(payload.decision),
    sources: sourceRows(payload),
    reason: humanReason(payload),
    actionTitle: action.title,
    actionDescription: action.description,
    timeline: timelineItems(payload),
  };
}
