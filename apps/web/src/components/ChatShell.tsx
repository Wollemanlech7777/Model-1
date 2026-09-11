"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { CompanionAvatar } from "@/components/CompanionAvatar";
import { EvidencePanel } from "@/components/EvidencePanel";
import { HomeGuideCard } from "@/components/HomeGuideCard";
import { SystemCapabilities } from "@/components/SystemCapabilities";
import {
  askAboutJob,
  fetchJobEvidence,
  runPolicyReview,
  type PolicyReviewJob,
} from "@/lib/api";
import {
  resolveFinalPresentation,
  type CompanionState,
} from "@/lib/avatar-state";
import {
  buildCapabilityGroups,
  resolveCapabilityPhase,
} from "@/lib/capability-map";
import {
  buildResultView,
  stepsFromJobProgress,
  type ProcessStepView,
  type ResultView,
} from "@/lib/chat-presentation";
import type { EvidencePayload } from "@/lib/evidence-presentation";

type ChatMessage = {
  id: string;
  role: "user" | "companion";
  text?: string;
  jobId?: string;
  showEvidence?: boolean;
  tone?: "process" | "result" | "error" | "plain";
  processSteps?: ProcessStepView[];
  result?: ResultView;
};

const POLICY_RE = /\bPOL-\d+\b/i;

/** Demo policy used by the existing EXECUTE path (CyberNotes sandbox map). */
const DEMO_POLICY_REVIEW_MESSAGE = "Review policy POL-48291";

type HomeAction = {
  id: string;
  label: string;
  /** Message sent through the existing policy-review chat flow. */
  message: string;
};

const HOME_ACTIONS: HomeAction[] = [
  {
    id: "review-policy",
    label: "Review a policy",
    message: DEMO_POLICY_REVIEW_MESSAGE,
  },
];

/** Intent to start a policy review without an ID yet (UI clarification only). */
function isPolicyReviewIntent(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized || POLICY_RE.test(text)) return false;
  const asksReview =
    /\breview\b/.test(normalized) ||
    /\brevisa(r)?\b/.test(normalized) ||
    /\bcheck\b/.test(normalized);
  const mentionsPolicy =
    /\bpolic(y|ies)\b/.test(normalized) || /\bp[oó]liza(s)?\b/.test(normalized);
  return asksReview && mentionsPolicy;
}


function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isTechnicalErrorMessage(message: ChatMessage): boolean {
  if (message.tone === "error") return true;
  if (message.role !== "companion") return false;
  const text = (message.text || "").toLowerCase();
  return (
    text.includes("failed to load") ||
    text.includes("failed to fetch") ||
    text.includes("no pude completar la solicitud") ||
    text.includes("load failed") ||
    text.includes("networkerror")
  );
}

function ProcessList({
  steps,
  live,
}: {
  steps: ProcessStepView[];
  live?: boolean;
}) {
  if (steps.length === 0) return null;
  return (
    <ul
      className={`process-list${live ? " process-list--live" : " process-list--frozen"}`}
      aria-label="System checks"
    >
      {steps
        .filter((step) => step.status !== "pending")
        .map((step) => (
          <li
            key={step.key}
            className={`process-item process-item--${step.status}`}
          >
            <span className="process-item__mark" aria-hidden="true">
              {step.status === "done" ? "✓" : "◌"}
            </span>
            <span className="process-item__label">
              {step.status === "done" ? step.doneLabel : step.activeLabel}
            </span>
          </li>
        ))}
    </ul>
  );
}

function ResultBlock({
  result,
  jobId,
  onEvidence,
}: {
  result: ResultView;
  jobId?: string;
  onEvidence?: (jobId: string) => void;
}) {
  return (
    <div className="result-block">
      <p className="result-block__label">{result.label}</p>
      <p className="result-block__title">{result.title}</p>
      {result.detail ? <p className="result-block__detail">{result.detail}</p> : null}
      {jobId && onEvidence ? (
        <button
          type="button"
          className="evidence-btn"
          onClick={() => onEvidence(jobId)}
        >
          View evidence
        </button>
      ) : null}
    </div>
  );
}

export function ChatShell() {
  const [state, setState] = useState<CompanionState>("idle");
  const [animationOverride, setAnimationOverride] = useState<string | null>(null);
  const [statusLabel, setStatusLabel] = useState("SYSTEM READY");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [awaitingJob, setAwaitingJob] = useState(false);
  const [liveSteps, setLiveSteps] = useState<ProcessStepView[]>([]);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidencePayload, setEvidencePayload] = useState<EvidencePayload | null>(null);
  const [lastJob, setLastJob] = useState<PolicyReviewJob | null>(null);
  const [transportFailed, setTransportFailed] = useState(false);
  const [awaitingPolicyId, setAwaitingPolicyId] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const isHome = messages.length === 0 && liveSteps.length === 0 && !awaitingJob;

  const capabilityGroups = useMemo(() => {
    const phase = resolveCapabilityPhase({
      busy,
      awaitingJob,
      liveSteps,
      job: lastJob,
      transportFailed,
    });
    return buildCapabilityGroups({
      phase,
      job: lastJob,
      liveSteps,
    });
  }, [busy, awaitingJob, liveSteps, lastJob, transportFailed]);

  useEffect(() => {
    if (!isHome) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, evidenceOpen, isHome, busy, liveSteps, awaitingJob]);

  function enterWorking() {
    setState("running");
    setAnimationOverride("thinking");
    setStatusLabel("WORKING");
  }

  function applyFinalPresentation(job: PolicyReviewJob) {
    const final = resolveFinalPresentation(job);
    setState(final.companionState);
    setAnimationOverride(final.animation);
    setStatusLabel(final.statusLabel);
  }

  async function runReview(text: string) {
    enterWorking();
    setAwaitingJob(true);
    setLiveSteps([]);

    const job = await runPolicyReview(text);
    setAwaitingJob(false);
    setLastJob(job);

    // Keep WORKING while presenting real checks — no final result yet.
    enterWorking();

    const baseSteps = stepsFromJobProgress(job.progress);
    setLiveSteps(baseSteps);

    let current = baseSteps;
    for (let i = 0; i < baseSteps.length; i += 1) {
      current = current.map((step, index) => {
        if (index < i) return { ...step, status: "done" };
        if (index === i) return { ...step, status: "active" };
        return { ...step, status: "pending" };
      });
      setLiveSteps(current);
      await sleep(640);
      current = current.map((step, index) =>
        index === i ? { ...step, status: "done" } : step,
      );
      setLiveSteps(current);
      await sleep(280);
    }

    await sleep(320);

    const frozen = current.map((step) => ({ ...step, status: "done" as const }));
    setLiveSteps([]);
    setMessages((prev) => [
      ...prev,
      {
        id: `proc-${Date.now()}`,
        role: "companion",
        tone: "process",
        processSteps: frozen,
      },
    ]);

    applyFinalPresentation(job);
    await sleep(260);

    const result = buildResultView(job);
    setMessages((prev) => [
      ...prev,
      {
        id: `s-${Date.now()}`,
        role: "companion",
        tone: "result",
        jobId: job.id,
        showEvidence: true,
        result,
      },
    ]);
  }

  async function runAsk(text: string, job: PolicyReviewJob) {
    enterWorking();
    const result = await askAboutJob(job.id, text);
    setMessages((prev) => [
      ...prev,
      {
        id: `a-${Date.now()}`,
        role: "companion",
        tone: "plain",
        text: result.answer,
      },
    ]);
    applyFinalPresentation(job);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    setBusy(true);
    setEvidenceOpen(false);
    setInput("");
    setLiveSteps([]);
    setAwaitingJob(false);
    setTransportFailed(false);

    const isPolicy = POLICY_RE.test(trimmed);

    setMessages((prev) => {
      const kept = isPolicy ? prev.filter((m) => !isTechnicalErrorMessage(m)) : prev;
      return [...kept, { id: `u-${Date.now()}`, role: "user", text: trimmed }];
    });

    enterWorking();

    try {
      if (isPolicy) {
        setAwaitingPolicyId(false);
        await runReview(trimmed);
      } else if (awaitingPolicyId) {
        setMessages((prev) => [
          ...prev,
          {
            id: `h-${Date.now()}`,
            role: "companion",
            tone: "plain",
            text: "I need the policy number to start the review.\n\nExample: POL-48291",
          },
        ]);
        setState("idle");
        setAnimationOverride("idle");
        setStatusLabel("SYSTEM READY");
      } else if (isPolicyReviewIntent(trimmed)) {
        setAwaitingPolicyId(true);
        setMessages((prev) => [
          ...prev,
          {
            id: `h-${Date.now()}`,
            role: "companion",
            tone: "plain",
            text: "Sure. I need the policy number to start the review.",
          },
        ]);
        setState("idle");
        setAnimationOverride("idle");
        setStatusLabel("SYSTEM READY");
      } else if (lastJob) {
        await runAsk(trimmed, lastJob);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `h-${Date.now()}`,
            role: "companion",
            tone: "plain",
            text: "I need a policy number to start a verification.\n\nExample: POL-48291 — or use “Review a policy”.",
          },
        ]);
        setState("idle");
        setAnimationOverride("idle");
        setStatusLabel("SYSTEM READY");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error calling API";
      setAwaitingJob(false);
      setLiveSteps([]);
      setTransportFailed(true);
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "companion",
          text: `No pude completar la solicitud: ${message}`,
          tone: "error",
        },
      ]);
      setState("fail");
      setAnimationOverride("scared");
      setStatusLabel("FAILED");
    } finally {
      setBusy(false);
      setAwaitingJob(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await sendMessage(input);
  }

  async function onViewEvidence(jobId: string) {
    try {
      const payload = (await fetchJobEvidence(jobId)) as EvidencePayload;
      setEvidencePayload(payload);
      setEvidenceOpen(true);
    } catch {
      if (lastJob && lastJob.id === jobId) {
        setEvidencePayload({
          job_id: lastJob.id,
          decision: lastJob.decision,
          evidence: lastJob.evidence,
          timeline: lastJob.timeline,
          sources: lastJob.sources,
          reasons: lastJob.reasons,
          interpretation: lastJob.interpretation,
          presentation: lastJob.presentation,
        });
        setEvidenceOpen(true);
      }
    }
  }

  return (
    <div className="page">
      <div className={`shell ${isHome ? "shell--home" : "shell--chat"}`}>
        <header className="shell__stage">
          {isHome ? (
            <div className="shell__stage-meta shell__stage-meta--home">
              <p className="shell__brand">Site Companion</p>
              <p className="shell__status shell__status--ready" aria-live="polite">
                System ready
              </p>
            </div>
          ) : null}
          <div className="shell__avatar-slot">
            <CompanionAvatar
              state={state}
              animationOverride={animationOverride}
              size={192}
            />
          </div>
          {!isHome ? (
            <div className="shell__stage-meta">
              <p className="shell__brand">Site Companion</p>
              <p
                className={`shell__status${busy ? " shell__status--working" : ""}`}
                aria-live="polite"
              >
                {statusLabel}
              </p>
            </div>
          ) : null}
        </header>

        <main className="shell__chat">
          <div className="shell__panels">
            <div
              className="home"
              aria-label="Home"
              aria-hidden={!isHome}
              inert={!isHome ? true : undefined}
            >
              <h1 className="home__title">What can I help you with?</h1>
              <p className="home__subtitle">
                Give me a policy number and I&apos;ll verify it across connected
                systems before any action is taken.
              </p>
              <p className="home__sources" aria-label="Connected systems">
                CRM · Legacy · Email · Portal
              </p>
              <div className="home__suggestions">
                {HOME_ACTIONS.map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    className="home__pill"
                    disabled={busy || !isHome}
                    tabIndex={isHome ? 0 : -1}
                    onClick={() => sendMessage(action.message)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>

            <div
              className="messages"
              role="log"
              aria-label="Conversation"
              aria-hidden={isHome}
            >
              {messages.map((message) => {
                if (message.role === "user") {
                  return (
                    <div key={message.id} className="bubble bubble--user">
                      <p className="bubble__text">{message.text}</p>
                    </div>
                  );
                }

                if (message.tone === "process" && message.processSteps) {
                  return (
                    <div key={message.id} className="process-block">
                      <ProcessList steps={message.processSteps} />
                    </div>
                  );
                }

                if (message.tone === "result" && message.result) {
                  return (
                    <div key={message.id} className="result-wrap">
                      <ResultBlock
                        result={message.result}
                        jobId={message.jobId}
                        onEvidence={onViewEvidence}
                      />
                    </div>
                  );
                }

                return (
                  <div
                    key={message.id}
                    className={[
                      "bubble bubble--companion",
                      message.tone === "error" ? "bubble--error" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <p className="bubble__text">{message.text}</p>
                  </div>
                );
              })}

              {awaitingJob ? (
                <div className="busy-hint busy-hint--active" aria-live="polite">
                  Checking connected systems…
                </div>
              ) : null}

              {liveSteps.length > 0 ? (
                <div className="process-block process-block--live">
                  <ProcessList steps={liveSteps} live />
                </div>
              ) : null}

              <div ref={bottomRef} />
            </div>
          </div>

          {evidenceOpen && evidencePayload ? (
            <EvidencePanel
              payload={evidencePayload}
              policyId={lastJob?.policy_id}
              crmWrite={lastJob?.crm_write}
              onClose={() => setEvidenceOpen(false)}
            />
          ) : null}
        </main>

        <form className="composer" onSubmit={onSubmit}>
          <input
            className="composer__input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask something..."
            disabled={busy}
            aria-label="Message"
          />
          <button
            className="composer__send"
            type="submit"
            disabled={busy || !input.trim()}
            aria-label="Send"
          >
            ↑
          </button>
        </form>
      </div>

      <HomeGuideCard visible />
      <SystemCapabilities groups={capabilityGroups} />
    </div>
  );
}
