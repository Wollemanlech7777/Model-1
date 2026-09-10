import assert from "node:assert/strict";

const STATE_TO_ANIMATION = {
  idle: "idle",
  running: "working",
  execute: "proud",
  review: "confused",
  fail: "scared",
};

assert.equal(STATE_TO_ANIMATION.idle, "idle");
assert.equal(STATE_TO_ANIMATION.running, "working");
assert.equal(STATE_TO_ANIMATION.execute, "proud");
assert.equal(STATE_TO_ANIMATION.review, "confused");
assert.equal(STATE_TO_ANIMATION.fail, "scared");
console.log("avatar-state mapping ok");
