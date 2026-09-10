"use client";

import {
  buildEvidenceView,
  type EvidencePayload,
} from "@/lib/evidence-presentation";

type EvidencePanelProps = {
  payload: EvidencePayload;
  policyId?: string | null;
  crmWrite?: {
    attempted?: boolean;
    performed?: boolean;
    skipped?: boolean;
    reason?: string | null;
  } | null;
  onClose: () => void;
};

export function EvidencePanel({
  payload,
  policyId,
  crmWrite,
  onClose,
}: EvidencePanelProps) {
  const view = buildEvidenceView(payload, { policyId, crmWrite });

  return (
    <div className="evidence-overlay" role="presentation" onClick={onClose}>
      <div
        className="evidence-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Evidence"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="evidence-modal__header">
          <h2 className="evidence-modal__title">Evidence</h2>
          <button
            type="button"
            className="evidence-modal__close"
            onClick={onClose}
            aria-label="Close evidence"
          >
            ✕
          </button>
        </header>

        <div className="evidence-modal__body">
          <section className="evidence-section">
            <p className="evidence-section__label">Policy</p>
            <p className="evidence-section__value">{view.policyId}</p>
          </section>

          <section className="evidence-section">
            <p className="evidence-section__label">Decision</p>
            <p className="evidence-section__value">{view.decisionLabel}</p>
          </section>

          <section className="evidence-section">
            <p className="evidence-section__label">Sources</p>
            {view.sources.length === 0 ? (
              <p className="evidence-section__muted">No source statuses recorded.</p>
            ) : (
              <ul className="evidence-sources">
                {view.sources.map((source) => (
                  <li key={source.name} className="evidence-sources__row">
                    <span className="evidence-sources__name">{source.name}</span>
                    <span className="evidence-sources__status">{source.status}</span>
                    <span
                      className={`evidence-sources__mark evidence-sources__mark--${source.mark}`}
                      aria-hidden="true"
                    >
                      {source.mark === "ok" ? "✓" : "!"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="evidence-section">
            <p className="evidence-section__label">Reason</p>
            <p className="evidence-section__copy">{view.reason}</p>
          </section>

          <section className="evidence-section">
            <p className="evidence-section__label">Action</p>
            <p className="evidence-section__value">{view.actionTitle}</p>
            <p className="evidence-section__copy evidence-section__copy--follow">
              {view.actionDescription}
            </p>
          </section>

          <section className="evidence-section">
            <p className="evidence-section__label">Timeline</p>
            {view.timeline.length === 0 ? (
              <p className="evidence-section__muted">No integration events recorded.</p>
            ) : (
              <ul className="evidence-timeline">
                {view.timeline.map((item, index) => (
                  <li
                    key={`${item.label}-${index}`}
                    className={`evidence-timeline__item evidence-timeline__item--${item.kind}`}
                  >
                    <span className="evidence-timeline__mark" aria-hidden="true">
                      {item.kind === "ok" ? "✓" : item.kind === "error" ? "!" : "→"}
                    </span>
                    <span className="evidence-timeline__label">{item.label}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
