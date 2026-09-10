"use client";

type HomeGuideCardProps = {
  visible: boolean;
};

export function HomeGuideCard({ visible }: HomeGuideCardProps) {
  if (!visible) return null;

  return (
    <aside className="home-guide" aria-label="Insurance operations">
      <header className="home-guide__header">
        <p className="home-guide__label">Insurance operations</p>
        <h2 className="home-guide__title">
          Verify a policy before taking action
        </h2>
      </header>

      <section className="home-guide__section home-guide__section--scenario">
        <h3 className="home-guide__label">Scenario</h3>
        <p className="home-guide__copy home-guide__copy--lead">
          A broker is handling a request for an existing policy and already has
          the policy number. Before processing it, they need to verify that the
          policy information is consistent across the systems they work with.
        </p>
      </section>

      <section className="home-guide__section">
        <h3 className="home-guide__label">What Site Companion does</h3>
        <p className="home-guide__copy">
          Give it the policy number. Site Companion checks the CRM, legacy
          system, email and insurer portal, compares the information, and
          determines whether the request can safely proceed.
        </p>
      </section>

      <section className="home-guide__section">
        <h3 className="home-guide__label">Outcome</h3>
        <ul className="home-guide__outcomes-list">
          <li>
            <span className="home-guide__outcome-key">EXECUTE</span>
            <span className="home-guide__outcome-desc">
              Information matches → proceed
            </span>
          </li>
          <li>
            <span className="home-guide__outcome-key">REVIEW</span>
            <span className="home-guide__outcome-desc">
              Information conflicts → stop and review
            </span>
          </li>
          <li>
            <span className="home-guide__outcome-key">FAIL</span>
            <span className="home-guide__outcome-desc">
              Information cannot be verified → no action
            </span>
          </li>
        </ul>
      </section>

      <section className="home-guide__section">
        <h3 className="home-guide__label">In practice</h3>
        <div className="home-guide__practice" aria-label="Verification flow">
          <span className="home-guide__practice-node home-guide__practice-node--mono">
            POL-48291
          </span>
          <span className="home-guide__practice-arrow" aria-hidden="true">
            ↓
          </span>
          <span className="home-guide__practice-node">4 systems checked</span>
          <span className="home-guide__practice-arrow" aria-hidden="true">
            ↓
          </span>
          <span className="home-guide__practice-node">Evidence reconciled</span>
          <span className="home-guide__practice-arrow" aria-hidden="true">
            ↓
          </span>
          <span className="home-guide__practice-node">Decision</span>
          <span className="home-guide__practice-arrow" aria-hidden="true">
            ↓
          </span>
          <span className="home-guide__practice-node">Action</span>
        </div>
      </section>

      <section className="home-guide__section home-guide__section--footer">
        <p className="home-guide__copy home-guide__copy--emphasis">
          Replace a manual multi-system check with one controlled workflow.
        </p>
      </section>
    </aside>
  );
}
