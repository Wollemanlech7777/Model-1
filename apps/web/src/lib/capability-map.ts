import type { PolicyReviewJob } from "@/lib/api";
import type { ProcessStepView } from "@/lib/chat-presentation";

export type CapabilityStatus = "idle" | "pending" | "running" | "done" | "error";

export type CapabilityItem = {
  id: string;
  label: string;
  status: CapabilityStatus;
  kind: "structural" | "dynamic";
};

export type CapabilityGroup = {
  id: string;
  title: string;
  items: CapabilityItem[];
};

export type CapabilityPhase = "idle" | "running" | "completed" | "failed";

export function statusGlyph(status: CapabilityStatus): string {
  switch (status) {
    case "done":
      return "✓";
    case "running":
      return "◌";
    case "error":
      return "!";
    default:
      return "○";
  }
}

export function resolveCapabilityPhase(opts: {
  busy: boolean;
  awaitingJob: boolean;
  liveSteps: ProcessStepView[];
  job: PolicyReviewJob | null;
  transportFailed: boolean;
}): CapabilityPhase {
  if (opts.transportFailed && !opts.job) return "failed";
  if (opts.busy || opts.awaitingJob || opts.liveSteps.length > 0) return "running";
  if (opts.job) return "completed";
  return "idle";
}

function liveStep(liveSteps: ProcessStepView[], key: string) {
  return liveSteps.find((s) => s.key === key) ?? null;
}

function evidence(job: PolicyReviewJob | null, source: string) {
  return (job?.evidence || []).find(
    (item) => (item.source || "").toLowerCase() === source.toLowerCase(),
  );
}

function evidenceFailed(job: PolicyReviewJob | null, source: string): boolean {
  const item = evidence(job, source);
  if (!item) return false;
  if ((item.errors || []).length > 0) return true;
  return (item.result || "").toLowerCase() === "error";
}

function timelineHit(
  job: PolicyReviewJob | null,
  re: RegExp,
  success?: boolean,
): boolean {
  return (job?.timeline || []).some((e) => {
    if (!re.test(e.message || "")) return false;
    if (success === undefined) return true;
    return e.success === success;
  });
}

function progressHas(job: PolicyReviewJob | null, label: string): boolean {
  return (job?.progress || []).includes(label);
}

/**
 * Resolve a check-backed capability from job timeline/evidence/progress + live UI steps.
 * Does not invent success when the check never ran.
 */
function checkCapability(opts: {
  phase: CapabilityPhase;
  job: PolicyReviewJob | null;
  liveSteps: ProcessStepView[];
  progressKey: string;
  successRe: RegExp;
  failRe: RegExp;
  source: string;
}): CapabilityStatus {
  const { phase, job, liveSteps, progressKey, successRe, failRe, source } = opts;
  if (phase === "idle") return "idle";

  const step = liveStep(liveSteps, progressKey);
  if (step?.status === "active") return "running";

  const failed =
    timelineHit(job, failRe, false) ||
    evidenceFailed(job, source) ||
    timelineHit(job, new RegExp(`${source}.*→\\s*(?!200|match)`, "i"), false);

  const succeeded =
    timelineHit(job, successRe, true) ||
    (progressHas(job, progressKey) && !failed) ||
    (Boolean(job?.sources?.[source]) && !failed);

  if (step?.status === "done") {
    if (failed) return "error";
    if (succeeded) return "done";
    return "running";
  }

  if (phase === "running") {
    if (liveSteps.length > 0) {
      // Later checks stay pending until their live step activates.
      const order = [
        "Checking CRM",
        "Checking legacy data",
        "Reading email",
        "Checking portal",
      ];
      const idx = order.indexOf(progressKey);
      const activeIdx = liveSteps.findIndex((s) => s.status === "active");
      const doneCount = liveSteps.filter((s) => s.status === "done").length;
      if (succeeded && idx >= 0 && doneCount > idx) {
        return failed ? "error" : "done";
      }
      if (idx >= 0 && activeIdx >= 0 && idx < activeIdx) {
        return failed ? "error" : succeeded ? "done" : "pending";
      }
      if (idx >= 0 && doneCount > idx) {
        return failed ? "error" : succeeded ? "done" : "pending";
      }
      return "pending";
    }
    // Awaiting API or post-job before animation: show running for in-flight workflow.
    if (!job) return "pending";
    if (failed) return "error";
    if (succeeded) return "done";
    return "pending";
  }

  // Terminal: only mark done/error if this check actually participated.
  if (failed) return "error";
  if (succeeded) return "done";
  return "idle";
}

function workflowStatus(phase: CapabilityPhase, job: PolicyReviewJob | null): CapabilityStatus {
  if (phase === "idle") return "idle";
  if (phase === "running") return "running";
  if (job) return "done";
  if (phase === "failed") return "error";
  return "idle";
}

function interpretationStatus(
  phase: CapabilityPhase,
  job: PolicyReviewJob | null,
): CapabilityStatus {
  if (phase === "idle") return "idle";
  const present =
    Boolean(job?.interpretation?.summary) ||
    Boolean(job?.interpretation?.explanation) ||
    Boolean(job?.interpretation_source);
  if (phase === "running") return present ? "done" : "running";
  return present ? "done" : "idle";
}

function decisionStatus(phase: CapabilityPhase, job: PolicyReviewJob | null): CapabilityStatus {
  if (phase === "idle") return "idle";
  const d = (job?.decision || "").toLowerCase();
  const decided =
    d === "execute" || d === "review" || d === "fail" || timelineHit(job, /Decision\s*→/i);
  if (phase === "running") return decided ? "done" : "running";
  return decided ? "done" : "idle";
}

function evidenceStatus(phase: CapabilityPhase, job: PolicyReviewJob | null): CapabilityStatus {
  if (phase === "idle") return "idle";
  const hasEvidence = (job?.evidence || []).length > 0;
  const wrote = Boolean(job?.crm_write?.performed);
  if (phase === "running") return wrote || hasEvidence ? "done" : "running";
  if (wrote || hasEvidence) return "done";
  return "idle";
}

const STRUCTURAL_DONE = "done" as const;

export function buildCapabilityGroups(opts: {
  phase: CapabilityPhase;
  job: PolicyReviewJob | null;
  liveSteps: ProcessStepView[];
}): CapabilityGroup[] {
  const { phase, job, liveSteps } = opts;

  return [
    {
      id: "integrations",
      title: "INTEGRATIONS",
      items: [
        {
          id: "external-api",
          label: "External API",
          kind: "dynamic",
          status: checkCapability({
            phase,
            job,
            liveSteps,
            progressKey: "Checking portal",
            successRe: /Portal fetch\s*→\s*200/i,
            failRe: /Portal fetch\s*→\s*(?!200)|portal failure/i,
            source: "portal",
          }),
        },
        {
          id: "legacy-systems",
          label: "Legacy systems",
          kind: "dynamic",
          status: checkCapability({
            phase,
            job,
            liveSteps,
            progressKey: "Checking legacy data",
            successRe: /Legacy lookup\s*→\s*match/i,
            failRe: /Legacy lookup\s*→\s*(?!match)|legacy failure/i,
            source: "legacy",
          }),
        },
        {
          id: "workflow-automation",
          label: "Workflow automation",
          kind: "dynamic",
          status: workflowStatus(phase, job),
        },
      ],
    },
    {
      id: "engineering",
      title: "ENGINEERING",
      items: [
        { id: "python", label: "Python", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "typescript", label: "TypeScript", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "rest-apis", label: "REST APIs", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "postgresql", label: "PostgreSQL", status: STRUCTURAL_DONE, kind: "structural" },
        {
          id: "automated-tests",
          label: "Automated tests",
          status: STRUCTURAL_DONE,
          kind: "structural",
        },
      ],
    },
    {
      id: "ai-workflows",
      title: "AI WORKFLOWS",
      items: [
        {
          id: "ai-interpretation",
          label: "AI interpretation",
          kind: "dynamic",
          status: interpretationStatus(phase, job),
        },
        {
          id: "decision-engine",
          label: "Decision engine",
          kind: "dynamic",
          status: decisionStatus(phase, job),
        },
        {
          id: "evidence-execution",
          label: "Evidence-based execution",
          kind: "dynamic",
          status: evidenceStatus(phase, job),
        },
      ],
    },
    {
      id: "production",
      title: "PRODUCTION",
      items: [
        { id: "error-handling", label: "Error handling", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "timeouts", label: "Timeouts", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "rate-limiting", label: "Rate limiting", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "idempotency", label: "Idempotency", status: STRUCTURAL_DONE, kind: "structural" },
        { id: "health-checks", label: "Health checks", status: STRUCTURAL_DONE, kind: "structural" },
      ],
    },
  ];
}
