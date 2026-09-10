"use client";

import {
  useEffect,
  useState,
  type ReactNode,
  type TransitionEvent,
} from "react";

type StartupPhase =
  | "starting"
  | "preparing"
  | "ready"
  | "exiting"
  | "done";

type ContentPhase = "starting" | "preparing" | "ready";

/** Readable hold per state (motion allowed). Total hold ≈ 2.5s before exit. */
const STARTING_MS = 800;
const PREPARING_MS = 1000;
const READY_MS = 700;
const MIN_TOTAL_MS = STARTING_MS + PREPARING_MS + READY_MS;
const EXIT_FALLBACK_MS = 480;

/** Reduced motion: shorter holds, still sequential and readable. */
const STARTING_MS_REDUCED = 400;
const PREPARING_MS_REDUCED = 450;
const READY_MS_REDUCED = 350;
const MIN_TOTAL_MS_REDUCED =
  STARTING_MS_REDUCED + PREPARING_MS_REDUCED + READY_MS_REDUCED;
const EXIT_FALLBACK_MS_REDUCED = 80;

const PHASE_CONTENT: Record<
  ContentPhase,
  { state: string; lines: string[] }
> = {
  starting: {
    state: "STARTING UP",
    lines: ["Insurance operations workspace"],
  },
  preparing: {
    state: "PREPARING WORKSPACE",
    lines: ["Policy verification", "Evidence & decisions"],
  },
  ready: {
    state: "READY",
    lines: ["Your workspace is ready."],
  },
};

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function sleep(ms: number): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/**
 * Real browser readiness only — no CRM / CyberNotes / Gemini probes.
 * Hydration (effect) → document load → fonts → next paint.
 */
async function waitForAppReady(): Promise<void> {
  if (document.readyState !== "complete") {
    await new Promise<void>((resolve) => {
      window.addEventListener("load", () => resolve(), { once: true });
    });
  }

  if (document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      // Font readiness is best-effort; never block forever.
    }
  }

  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
}

function contentPhase(phase: StartupPhase): ContentPhase {
  if (phase === "preparing") return "preparing";
  if (phase === "ready" || phase === "exiting" || phase === "done") {
    return "ready";
  }
  return "starting";
}

function progressStep(phase: StartupPhase): 1 | 2 | 3 {
  if (phase === "preparing") return 2;
  if (phase === "ready" || phase === "exiting" || phase === "done") return 3;
  return 1;
}

type AppStartupProps = {
  children: ReactNode;
};

export function AppStartup({ children }: AppStartupProps) {
  const [phase, setPhase] = useState<StartupPhase>("starting");

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const reduced = prefersReducedMotion();
      const startingMs = reduced ? STARTING_MS_REDUCED : STARTING_MS;
      const preparingMs = reduced ? PREPARING_MS_REDUCED : PREPARING_MS;
      const readyMs = reduced ? READY_MS_REDUCED : READY_MS;
      const minTotalMs = reduced ? MIN_TOTAL_MS_REDUCED : MIN_TOTAL_MS;
      const startedAt = performance.now();

      const appReady = waitForAppReady();

      await sleep(startingMs);
      if (cancelled) return;
      setPhase("preparing");

      await sleep(preparingMs);
      if (cancelled) return;
      setPhase("ready");

      await sleep(readyMs);
      if (cancelled) return;

      // Exit only when BOTH: app is ready AND minimum visual duration elapsed.
      await appReady;
      if (cancelled) return;

      const elapsed = performance.now() - startedAt;
      await sleep(Math.max(0, minTotalMs - elapsed));
      if (cancelled) return;

      setPhase("exiting");
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (phase !== "exiting") return;
    const fallbackMs = prefersReducedMotion()
      ? EXIT_FALLBACK_MS_REDUCED
      : EXIT_FALLBACK_MS;
    const id = window.setTimeout(() => setPhase("done"), fallbackMs);
    return () => window.clearTimeout(id);
  }, [phase]);

  function onSplashTransitionEnd(event: TransitionEvent<HTMLDivElement>) {
    if (event.propertyName !== "opacity") return;
    if (phase === "exiting") setPhase("done");
  }

  const splashVisible = phase !== "done";
  const content = PHASE_CONTENT[contentPhase(phase)];
  const step = progressStep(phase);
  const markAnimating = phase === "starting" || phase === "preparing";
  const contentKey = `${contentPhase(phase)}-${content.state}`;

  return (
    <>
      {splashVisible ? (
        <div
          className={`startup-splash startup-splash--${phase}`}
          role="status"
          aria-live="polite"
          aria-busy={markAnimating}
          onTransitionEnd={onSplashTransitionEnd}
        >
          <div
            className={
              markAnimating
                ? "startup-splash__mark startup-splash__mark--active"
                : "startup-splash__mark startup-splash__mark--still"
            }
            aria-hidden="true"
          >
            <svg
              className="startup-splash__svg"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 32 32"
            >
              <circle cx="16" cy="16" r="16" fill="#000000" />
              <rect
                className="startup-splash__eye startup-splash__eye--left"
                x="9"
                y="10.5"
                width="4.5"
                height="10"
                rx="2.25"
                fill="#FFFFFF"
              />
              <rect
                className="startup-splash__eye startup-splash__eye--right"
                x="18.5"
                y="10.5"
                width="4.5"
                height="10"
                rx="2.25"
                fill="#FFFFFF"
              />
            </svg>
          </div>

          <p className="startup-splash__brand">Site Companion</p>

          <div key={contentKey} className="startup-splash__copy">
            <p className="startup-splash__state">{content.state}</p>
            <div className="startup-splash__support">
              {content.lines.map((line) => (
                <p key={line} className="startup-splash__support-line">
                  {line}
                </p>
              ))}
            </div>
          </div>

          <div
            className="startup-splash__dots"
            aria-hidden="true"
            data-step={step}
          >
            <span className="startup-splash__dot" data-index="1" />
            <span className="startup-splash__dot" data-index="2" />
            <span className="startup-splash__dot" data-index="3" />
          </div>
        </div>
      ) : null}
      <div
        className={
          splashVisible ? "app-boot app-boot--covered" : "app-boot"
        }
        aria-hidden={splashVisible ? true : undefined}
      >
        {children}
      </div>
    </>
  );
}
