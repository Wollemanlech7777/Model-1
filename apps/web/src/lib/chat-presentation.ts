import type { PolicyReviewJob } from "@/lib/api";
import { resolveFinalPresentation } from "@/lib/avatar-state";

/** Exact orchestrator progress strings → active / done presentation labels. */
export const CHECK_STEP_META: Record<
  string,
  { activeLabel: string; doneLabel: string }
> = {
  "Checking CRM": {
    activeLabel: "Checking CRM",
    doneLabel: "CRM checked",
  },
  "Checking legacy data": {
    activeLabel: "Checking legacy data",
    doneLabel: "Legacy checked",
  },
  "Reading email": {
    activeLabel: "Reading email",
    doneLabel: "Email checked",
  },
  "Checking portal": {
    activeLabel: "Checking portal",
    doneLabel: "Portal checked",
  },
};

export const KNOWN_CHECK_ORDER = [
  "Checking CRM",
  "Checking legacy data",
  "Reading email",
  "Checking portal",
] as const;

export type ProcessStepView = {
  key: string;
  activeLabel: string;
  doneLabel: string;
  status: "pending" | "active" | "done";
};

export type ResultView = {
  label: string;
  title: string;
  detail?: string;
};

export function stepsFromJobProgress(progress: string[] | undefined): ProcessStepView[] {
  const found = new Set(
    (progress || []).filter((step) => step in CHECK_STEP_META),
  );
  const ordered = KNOWN_CHECK_ORDER.filter((step) => found.has(step));
  const keys = ordered.length > 0 ? ordered : (progress || []).filter((step) => step in CHECK_STEP_META);

  return keys.map((key) => {
    const meta = CHECK_STEP_META[key];
    return {
      key,
      activeLabel: meta.activeLabel,
      doneLabel: meta.doneLabel,
      status: "pending" as const,
    };
  });
}

/**
 * Hierarchy for the result block — decision label + clear operational outcome.
 * Does not invent writes or checks beyond the job payload.
 */
export function buildResultView(job: PolicyReviewJob): ResultView {
  const { statusLabel } = resolveFinalPresentation(job);
  const decision = (job.decision || "").toLowerCase();
  const sourceCount = Object.keys(job.sources || {}).length;
  const writePerformed = Boolean(job.crm_write?.performed);

  let title: string;
  if (decision === "execute") {
    const verified =
      sourceCount > 0
        ? `Verified across ${sourceCount} sources.`
        : "Verified across connected sources.";
    title = writePerformed
      ? `${verified} CRM activity created.`
      : verified;
  } else if (decision === "review") {
    title = "Verification requires review. No action was taken.";
  } else if (decision === "fail") {
    title = "Verification failed. No action was taken.";
  } else {
    title =
      (job.interpretation?.summary || job.assistant_summary || statusLabel).trim() ||
      statusLabel;
  }

  const detail = (job.interpretation?.explanation || "").trim();
  const showDetail = Boolean(detail) && !isNearDuplicate(title, detail);

  return {
    label: statusLabel,
    title,
    detail: showDetail ? detail : undefined,
  };
}

function isNearDuplicate(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  const n = Math.min(48, a.length, b.length);
  if (n >= 24 && a.slice(0, n) === b.slice(0, n)) return true;
  if (a.includes(b.slice(0, Math.min(40, b.length)))) return true;
  if (b.includes(a.slice(0, Math.min(40, a.length)))) return true;
  return false;
}
