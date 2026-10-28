"use client";

import { formatTimecode } from "@/lib/timecode";

export interface SceneItem {
  id: string;
  startSeconds: number;
  endSeconds: number;
  moment: string;
  whyItWorks: string;
  editingDirection: string;
  pacing: "slow" | "medium" | "fast";
  confidence?: number | null;
}

export interface BlueprintData {
  title: string;
  creativeIntent: string;
  summary: string;
  targetDurationSeconds: number;
  aspectRatio: string;
  hook: string;
  scenes: SceneItem[];
  sequenceRationale: string;
  endingSuggestion: string;
  caveats: string[];
}

const SAMPLE_BLUEPRINT: BlueprintData = {
  title: "Kinetic Sprint Teaser Plan",
  creativeIntent:
    "Build tension during preparatory breathing and release explosive kinetic energy in 30 seconds.",
  summary:
    "A 3-act sequence framing pre-race tension, explosive launch momentum, and the emotional post-finish reaction.",
  targetDurationSeconds: 30,
  aspectRatio: "9:16",
  hook: "Open directly with audio intake and macro shot of athlete's eyes at 00:01.2.",
  scenes: [
    {
      id: "scene-01",
      startSeconds: 1.2,
      endSeconds: 4.8,
      moment: "Macro focus on athlete breathing and tightening shoe grip",
      whyItWorks: "Establishes calm before the storm and commands immediate visual focus",
      editingDirection: "Slow push in; hold rhythm, cut sharply on gun smoke",
      pacing: "slow",
      confidence: 0.94,
    },
    {
      id: "scene-02",
      startSeconds: 5.1,
      endSeconds: 11.4,
      moment: "Explosive acceleration out of the blocks with dust kick",
      whyItWorks: "Delivers the core kinetic release the viewer anticipated",
      editingDirection: "Rapid speed ramp; slow down during peak leg extension",
      pacing: "fast",
      confidence: 0.88,
    },
    {
      id: "scene-03",
      startSeconds: 14.0,
      endSeconds: 19.5,
      moment: "Tracking profile shot maintaining stride cadence",
      whyItWorks: "Maintains high velocity rhythm without causing visual fatigue",
      editingDirection: "Match cut with subtle zoom pulse on footsteps",
      pacing: "medium",
      confidence: null,
    },
  ],
  sequenceRationale:
    "Alternating between deliberate slow-burn macro prep and fast tracking shots creates dynamic tension.",
  endingSuggestion: "Freeze on crossing the tape with high-contrast text card overlay.",
  caveats: [
    "AI boundary suggestions are approximate; review sub-second frame cuts in your NLE.",
    "Slight background motion blur detected between 07.2s and 08.5s.",
  ],
};

export function BlueprintPreviewCard() {
  const blueprint = SAMPLE_BLUEPRINT;

  return (
    <div className="rounded-xl border border-[#262b33] bg-[#111418] p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-[#262b33] pb-4">
        <div>
          <span className="font-mono text-[11px] uppercase tracking-wider text-[#e6ff00]">
            Verified Application Contract
          </span>
          <h2 className="text-lg font-bold text-[#f3f4f6]">{blueprint.title}</h2>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded border border-[#262b33] bg-[#181c22] px-2 py-0.5 font-mono text-xs text-[#9ca3af]">
            Target: {blueprint.targetDurationSeconds}s
          </span>
          <span className="rounded border border-[#262b33] bg-[#181c22] px-2 py-0.5 font-mono text-xs text-[#9ca3af]">
            Ratio: {blueprint.aspectRatio}
          </span>
        </div>
      </div>

      <div className="mb-6 space-y-3">
        <div className="rounded-lg border border-[#262b33] bg-[#0a0c0f] p-3 text-xs">
          <span className="font-semibold text-[#f3f4f6]">Creative Intent:</span>{" "}
          <span className="text-[#9ca3af]">{blueprint.creativeIntent}</span>
        </div>

        <div className="rounded-lg border border-[#262b33] bg-[#181c22] p-3 text-xs">
          <span className="font-semibold text-[#e6ff00]">Hook Direction:</span>{" "}
          <span className="text-[#f3f4f6]">{blueprint.hook}</span>
        </div>
      </div>

      <div className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#9ca3af]">
            Recommended Moments Timeline
          </h3>
          <span className="text-[11px] text-[#6b7280]">
            Clicking a moment seeks the player (Phase 4)
          </span>
        </div>

        <div className="space-y-3">
          {blueprint.scenes.map((scene, idx) => (
            <div
              key={scene.id}
              className="group rounded-lg border border-[#262b33] bg-[#0a0c0f] p-4 transition-all hover:border-[#383f4a] hover:bg-[#181c22]"
            >
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded bg-[#181c22] font-mono text-[11px] font-bold text-[#e6ff00]">
                    {idx + 1}
                  </span>
                  <span className="font-mono text-xs font-semibold text-[#f3f4f6]">
                    {formatTimecode(scene.startSeconds)} → {formatTimecode(scene.endSeconds)}
                  </span>
                  <span className="text-[11px] text-[#6b7280]">
                    ({(scene.endSeconds - scene.startSeconds).toFixed(1)}s)
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase ${
                      scene.pacing === "fast"
                        ? "bg-[#ef4444]/15 text-[#ef4444]"
                        : scene.pacing === "slow"
                        ? "bg-[#3b82f6]/15 text-[#60a5fa]"
                        : "bg-[#eab308]/15 text-[#facc15]"
                    }`}
                  >
                    {scene.pacing}
                  </span>
                  {scene.confidence !== null && scene.confidence !== undefined && (
                    <span className="font-mono text-[10px] text-[#6b7280]">
                      conf: {(scene.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>

              <p className="mb-1.5 text-xs font-medium text-[#f3f4f6]">
                {scene.moment}
              </p>

              <div className="grid grid-cols-1 gap-2 pt-2 text-[11px] sm:grid-cols-2 border-t border-[#1c2026]">
                <div>
                  <span className="text-[#6b7280]">Why it works:</span>{" "}
                  <span className="text-[#9ca3af]">{scene.whyItWorks}</span>
                </div>
                <div>
                  <span className="text-[#e6ff00]">Editing action:</span>{" "}
                  <span className="text-[#f3f4f6]">{scene.editingDirection}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-3 border-t border-[#1c2026] pt-4 text-xs">
        <div>
          <span className="font-semibold text-[#f3f4f6]">Sequence Rationale:</span>{" "}
          <span className="text-[#9ca3af]">{blueprint.sequenceRationale}</span>
        </div>
        <div>
          <span className="font-semibold text-[#f3f4f6]">Ending Direction:</span>{" "}
          <span className="text-[#9ca3af]">{blueprint.endingSuggestion}</span>
        </div>
        {blueprint.caveats.length > 0 && (
          <div className="rounded bg-[#181c22] p-2.5 text-[11px] text-[#9ca3af]">
            <span className="font-semibold text-[#f3f4f6]">Review Notes:</span>
            <ul className="mt-1 list-inside list-disc space-y-0.5 text-[#6b7280]">
              {blueprint.caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
