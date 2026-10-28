"use client";

import { useState } from "react";

const BRIEF_PRESETS = [
  {
    label: "Cinematic Teaser",
    text: "Create a tense 30-second cinematic teaser; prioritize movement, intense macro close-ups, and emotional reactions.",
  },
  {
    label: "High-Energy Hype",
    text: "Cut a high-tempo 15-second teaser with rapid jump cuts on kinetic motion; maximize impact in the first 2 seconds.",
  },
  {
    label: "Story & Narrative",
    text: "Craft a clear 3-act story arc: establish setting, introduce conflict or effort, and conclude with triumphant resolution.",
  },
  {
    label: "Product Focus",
    text: "Showcase physical textures, precision details, and utility; emphasize tactile interactions with steady pacing.",
  },
  {
    label: "Interview Cut",
    text: "Highlight the most authentic spoken insight; cut on conversational breath pauses and emphasize speaker conviction.",
  },
];

interface CreativeBriefFormProps {
  brief: string;
  setBrief: (val: string) => void;
}

export function CreativeBriefForm({ brief, setBrief }: CreativeBriefFormProps) {
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [targetDuration, setTargetDuration] = useState(30);

  return (
    <div className="rounded-xl border border-[#262b33] bg-[#111418] p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[#9ca3af]">
          2. Creative Brief & Constraints
        </h2>
        <span className="font-mono text-xs text-[#6b7280]">
          Guides moment selection
        </span>
      </div>

      <div className="mb-4">
        <label
          htmlFor="creative-brief"
          className="mb-1.5 block text-xs font-medium text-[#f3f4f6]"
        >
          Creative Vision / Editing Direction
        </label>
        <textarea
          id="creative-brief"
          rows={3}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Describe the emotion, pacing, narrative goal, or preferred focus for this cut..."
          className="w-full resize-none rounded-lg border border-[#262b33] bg-[#0a0c0f] p-3 text-sm text-[#f3f4f6] placeholder-[#6b7280] transition-colors focus:border-[#e6ff00]/60 focus:outline-none"
        />
      </div>

      <div className="mb-4">
        <div className="mb-1.5 text-xs font-medium text-[#9ca3af]">
          Quick Presets:
        </div>
        <div className="flex flex-wrap gap-2">
          {BRIEF_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => setBrief(preset.text)}
              className="rounded-md border border-[#262b33] bg-[#181c22] px-2.5 py-1 text-xs text-[#9ca3af] transition-colors hover:border-[#e6ff00]/50 hover:text-[#f3f4f6]"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-3 border-t border-[#1c2026]">
        <div>
          <label
            htmlFor="aspect-ratio-select"
            className="mb-1 block text-xs font-medium text-[#9ca3af]"
          >
            Target Aspect Ratio
          </label>
          <select
            id="aspect-ratio-select"
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value)}
            className="w-full rounded-md border border-[#262b33] bg-[#0a0c0f] px-3 py-1.5 text-xs text-[#f3f4f6] focus:border-[#e6ff00]/60 focus:outline-none"
          >
            <option value="9:16">9:16 (Reels / Shorts / TikTok)</option>
            <option value="16:9">16:9 (Landscape Cinematic)</option>
            <option value="1:1">1:1 (Square Social)</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="duration-select"
            className="mb-1 block text-xs font-medium text-[#9ca3af]"
          >
            Target Duration ({targetDuration}s)
          </label>
          <select
            id="duration-select"
            value={targetDuration}
            onChange={(e) => setTargetDuration(Number(e.target.value))}
            className="w-full rounded-md border border-[#262b33] bg-[#0a0c0f] px-3 py-1.5 text-xs text-[#f3f4f6] focus:border-[#e6ff00]/60 focus:outline-none font-mono"
          >
            <option value={15}>15 seconds (Micro Cut)</option>
            <option value={30}>30 seconds (Standard Teaser)</option>
            <option value={60}>60 seconds (Full Clip)</option>
          </select>
        </div>
      </div>

      <div className="mt-5">
        <button
          type="button"
          disabled
          className="w-full rounded-lg bg-[#e6ff00] px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-[#d2e800] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Generate Editing Blueprint (Phase 3 Integration)
        </button>
      </div>
    </div>
  );
}
