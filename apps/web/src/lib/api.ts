const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/** Public UUID for CyberNotes Sandbox (portal=real). No secrets. */
export const POLICY_REVIEW_ENVIRONMENT_ID =
  "2f46645e-35ff-4865-b7ed-88285c96d25a";

export type PolicyReviewJob = {
  id: string;
  status: string;
  policy_id: string | null;
  decision: string;
  allow_external_write: boolean;
  avatar_state: string;
  running_avatar_state?: string;
  crm_write: {
    attempted: boolean;
    performed: boolean;
    skipped: boolean;
    reason?: string | null;
    activity?: Record<string, unknown>;
  };
  sources: Record<string, string>;
  timeline: Array<{
    event_type: string;
    message: string;
    success: boolean;
    payload?: Record<string, unknown>;
    timestamp: string;
  }>;
  evidence: Array<{
    id: string;
    source: string;
    result: string;
    relevant_data: Record<string, unknown>;
    errors: string[];
    timestamp: string;
    decision?: string;
  }>;
  progress: string[];
  assistant_summary: string;
  reasons: string[];
  interpretation?: {
    summary?: string;
    explanation?: string;
    semantic_state?: string;
    severity?: string;
    reason?: string;
    expression?: string;
    animation?: string;
    source?: string;
  } | null;
  interpretation_source?: string | null;
  presentation?: Record<string, unknown> | null;
};

export async function runPolicyReview(message: string): Promise<PolicyReviewJob> {
  const response = await fetch(`${API_BASE}/jobs/policy-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      environment_id: POLICY_REVIEW_ENVIRONMENT_ID,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error ${response.status}`);
  }
  return response.json();
}

export async function fetchJobEvidence(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/evidence`);
  if (!response.ok) {
    throw new Error(`Failed to load evidence (${response.status})`);
  }
  return response.json();
}

export async function askAboutJob(jobId: string, question: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error ${response.status}`);
  }
  return response.json() as Promise<{ job_id: string; answer: string; source: string }>;
}
