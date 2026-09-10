"use client";

import { createAvatar } from "@bible-strong/avatar-react";
import "@bible-strong/avatar-react/styles.css";
import grokBotDefinition from "@/assets/grok-bot.avatar.json";
import {
  STATE_TO_ANIMATION,
  type CompanionState,
  type GrokAnimation,
} from "@/lib/avatar-state";

const GrokBotAvatar = createAvatar(grokBotDefinition);

const KNOWN_ANIMATIONS = new Set<string>([
  "sleeping",
  "waking",
  "idle",
  "listening",
  "thinking",
  "searching",
  "working",
  "excited",
  "bored",
  "suspicious",
  "angry",
  "drowsy",
  "happy",
  "curious",
  "confused",
  "surprised",
  "proud",
  "shy",
  "sad",
  "laughing",
  "scared",
  "playful",
  "celebrate",
  "mad",
]);

type CompanionAvatarProps = {
  state: CompanionState;
  /** When backend sends a concrete Grok animation key, prefer it for presentation. */
  animationOverride?: string | null;
  size?: number;
};

export function CompanionAvatar({
  state,
  animationOverride,
  size = 220,
}: CompanionAvatarProps) {
  const override = (animationOverride || "").toLowerCase();
  const animation = (
    KNOWN_ANIMATIONS.has(override) ? override : STATE_TO_ANIMATION[state]
  ) as GrokAnimation;

  return (
    <div className="companion-avatar" aria-live="polite">
      <GrokBotAvatar
        animation={animation}
        size={size}
        ariaLabel={`Site Companion — ${animation}`}
        className="companion-avatar__face"
      />
      <p className="companion-avatar__caption">{animation}</p>
    </div>
  );
}
