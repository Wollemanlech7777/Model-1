import assert from "node:assert/strict";
import { afterEach, describe, it, mock } from "node:test";

import {
  POLICY_REVIEW_ENVIRONMENT_ID,
  runPolicyReview,
} from "./api";

describe("runPolicyReview", () => {
  afterEach(() => {
    mock.restoreAll();
  });

  it("POSTs message and CyberNotes Sandbox environment_id", async () => {
    let capturedUrl = "";
    let capturedInit: RequestInit | undefined;

    mock.method(globalThis, "fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      capturedUrl = String(input);
      capturedInit = init;
      return new Response(
        JSON.stringify({
          id: "job-1",
          status: "completed",
          policy_id: "POL-48291",
          decision: "EXECUTE",
          allow_external_write: true,
          avatar_state: "idle",
          crm_write: { attempted: false, performed: false, skipped: true },
          sources: {},
          timeline: [],
          evidence: [],
          progress: [],
          assistant_summary: "ok",
          reasons: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });

    const message = "Revisa la póliza POL-48291";
    await runPolicyReview(message);

    assert.match(capturedUrl, /\/jobs\/policy-review$/);
    assert.equal(capturedInit?.method, "POST");

    const body = JSON.parse(String(capturedInit?.body));
    assert.deepEqual(body, {
      message,
      environment_id: "2f46645e-35ff-4865-b7ed-88285c96d25a",
    });
    assert.equal(body.environment_id, POLICY_REVIEW_ENVIRONMENT_ID);
  });
});
