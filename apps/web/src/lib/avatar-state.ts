/**
 * Job / companion UI states → Grok bot animation keys.
 * Driven by backend job results — frontend never decides EXECUTE/REVIEW/FAIL.
 */

export type CompanionState = "idle" | "running" | "execute" | "review" | "fail";

export type GrokAnimation =
  | "idle"
  | "working"
  | "proud"
  | "confused"
  | "scared"
  | "listening"
  | "thinking"
  | "searching"
  | "happy"
  | "sad"
  | "suspicious"
  | "celebrate";

/** Transient presentation keys that must not survive after a job finishes. */
export const TRANSIENT_ANIMATIONS = new Set([
  "working",
  "listening",
  "thinking",
  "searching",
]);

export const STATE_TO_ANIMATION: Record<CompanionState, GrokAnimation> = {
  idle: "idle",
  // Presentation-only: "working" clip reads angry; use existing neutral focus clip.
  running: "thinking",
  execute: "proud",
  review: "confused",
  fail: "scared",
};

export function companionStateFromDecision(decision: string | null | undefined): CompanionState {
  switch ((decision || "").toLowerCase()) {
    case "execute":
      return "execute";
    case "review":
      return "review";
    case "fail":
      return "fail";
    default:
      return "idle";
  }
}

export function companionStateFromAvatarState(avatarState: string | null | undefined): CompanionState {
  switch ((avatarState || "").toLowerCase()) {
    case "working":
    case "listening":
    case "thinking":
    case "searching":
      return "running";
    case "proud":
    case "celebrate":
    case "happy":
      return "execute";
    case "confused":
      return "review";
    case "scared":
    case "sad":
      return "fail";
    case "idle":
    default:
      return "idle";
  }
}

type PresentationFields = {
  decision?: string | null;
  avatar_state?: string | null;
  interpretation?: {
    animation?: string;
    semantic_state?: string;
  } | null;
  presentation?: {
    animation?: string;
    semantic_state?: string;
  } | null;
};

/**
 * Resolve the lasting post-job presentation.
 * Operational companion state follows decision; animation prefers backend
 * presentation when it is non-transient and coherent with that decision.
 */
export function resolveFinalPresentation(job: PresentationFields): {
  companionState: CompanionState;
  animation: GrokAnimation;
  statusLabel: string;
} {
  const companionState = companionStateFromDecision(job.decision);
  const fallback = STATE_TO_ANIMATION[companionState];

  const candidates = [
    job.presentation?.animation,
    job.interpretation?.animation,
    job.avatar_state,
  ];

  let animation = fallback;
  for (const raw of candidates) {
    const key = (raw || "").toLowerCase();
    if (!key || TRANSIENT_ANIMATIONS.has(key)) continue;
    const mapped = companionStateFromAvatarState(key);
    if (mapped === companionState) {
      animation = key as GrokAnimation;
      break;
    }
  }

  const semantic = (
    job.presentation?.semantic_state ||
    job.interpretation?.semantic_state ||
    ""
  ).toLowerCase();

  // Surface real Decision Engine outcomes — never substitute SUCCESS for EXECUTE.
  const statusLabel =
    companionState === "review"
      ? "REVIEW"
      : companionState === "execute"
        ? "EXECUTE"
        : companionState === "fail"
          ? "FAIL"
          : semantic === "ambiguous"
            ? "REVIEW"
            : semantic === "success"
              ? "EXECUTE"
              : semantic === "failed" || semantic === "blocked"
                ? "FAIL"
                : animation.toUpperCase();

  return { companionState, animation, statusLabel };
}
