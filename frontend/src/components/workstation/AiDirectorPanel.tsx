"use client";

import { useState } from "react";
import { CreativeBriefState, KeyMoment } from "@/types/workstation";

interface AiDirectorPanelProps {
  brief: CreativeBriefState;
  setBrief: (brief: CreativeBriefState) => void;
  moments: KeyMoment[];
  aiSuggestions: string[];
  activeMomentId: string | null;
  onJumpToMoment: (seconds: number, momentId: string) => void;
  onGenerateBlueprint: (confirmedConsent: boolean) => void;
  isGenerating: boolean;
  generationStage?: string | null;
  analysisError?: string | null;
  onDismissError?: () => void;
}

export function AiDirectorPanel({
  brief,
  setBrief,
  moments,
  aiSuggestions,
  activeMomentId,
  onJumpToMoment,
  onGenerateBlueprint,
  isGenerating,
  generationStage,
  analysisError,
  onDismissError,
}: AiDirectorPanelProps) {
  const [isEditingBrief, setIsEditingBrief] = useState(false);
  const [editedTitle, setEditedTitle] = useState(brief.title);
  const [editedDesc, setEditedDesc] = useState(brief.description);
  const [hasAuthorizedBaseten, setHasAuthorizedBaseten] = useState(false);
  const [showConsentPrompt, setShowConsentPrompt] = useState(false);

  const handleSaveBrief = () => {
    setBrief({
      ...brief,
      title: editedTitle.trim() || brief.title,
      description: editedDesc.trim() || brief.description,
    });
    setIsEditingBrief(false);
  };

  const handleTriggerGenerate = () => {
    if (!hasAuthorizedBaseten) {
      setShowConsentPrompt(true);
      return;
    }
    setShowConsentPrompt(false);
    onGenerateBlueprint(true);
  };

  const getTagBadgeStyle = (tag: KeyMoment["tag"]) => {
    switch (tag) {
      case "HOOK":
        return "bg-[#38bdf8]/15 text-[#38bdf8] border-[#38bdf8]/30";
      case "BUILD":
        return "bg-[#fbbf24]/15 text-[#fbbf24] border-[#fbbf24]/30";
      case "CLIMAX":
        return "bg-[#f87171]/15 text-[#f87171] border-[#f87171]/30";
      case "RESOLVE":
        return "bg-[#4ade80]/15 text-[#4ade80] border-[#4ade80]/30";
      default:
        return "bg-[#ffe600]/15 text-[#ffe600] border-[#ffe600]/30";
    }
  };

  return (
    <div className="flex h-full w-[360px] shrink-0 flex-col border-l border-[#1f2433] bg-[#0d1016] select-none">
      {/* Top Header */}
      <div className="border-b border-[#1f2433] px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.8)]" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#ffffff]">
              AI DIRECTOR
            </h2>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="rounded bg-[#ffe600]/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-[#ffe600] border border-[#ffe600]/30">
              Baseten · muse-spark
            </span>
          </div>
        </div>

        <p className="mt-0.5 text-[11px] text-[#9ca3af]">
          Your creative copilot for better edits.
        </p>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Error notification if analysis fails */}
        {analysisError && (
          <div className="rounded-lg border border-[#f87171]/30 bg-[#f87171]/10 p-3 text-xs text-[#f87171]">
            <div className="flex items-center justify-between">
              <span className="font-bold">Analysis Notice</span>
              {onDismissError && (
                <button
                  type="button"
                  onClick={onDismissError}
                  className="text-xs hover:text-[#ffffff]"
                  aria-label="Dismiss error"
                >
                  ✕
                </button>
              )}
            </div>
            <p className="mt-1 text-[11px] leading-tight text-[#fca5a5]">
              {analysisError}
            </p>
          </div>
        )}

        {/* Creative Brief Card */}
        <div className="rounded-lg border border-[#1f2433] bg-[#11141e] p-3.5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-bold text-[#ffffff]">Creative Brief</h3>
            <button
              type="button"
              onClick={() => {
                if (isEditingBrief) {
                  handleSaveBrief();
                } else {
                  setIsEditingBrief(true);
                }
              }}
              className="flex items-center gap-1 text-[11px] font-semibold text-[#9ca3af] hover:text-[#ffe600]"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
              <span>{isEditingBrief ? "Save" : "Edit"}</span>
            </button>
          </div>

          {isEditingBrief ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                placeholder="Brief Hook Title..."
                className="w-full rounded border border-[#1f2433] bg-[#08090c] p-1.5 text-xs text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
              />
              <textarea
                rows={2}
                value={editedDesc}
                onChange={(e) => setEditedDesc(e.target.value)}
                placeholder="Editing intent description..."
                className="w-full resize-none rounded border border-[#1f2433] bg-[#08090c] p-1.5 text-xs text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
              />
            </div>
          ) : (
            <>
              <h4 className="text-xs font-bold text-[#ffffff]">{brief.title}</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-[#9ca3af]">
                {brief.description}
              </p>
            </>
          )}

          {/* Metadata Specs Tags */}
          <div className="mt-3 grid grid-cols-4 gap-1.5 border-t border-[#1a1f2c] pt-2.5 text-center">
            <div className="rounded bg-[#08090c] p-1">
              <span className="block text-[9px] text-[#64748b]">Style</span>
              <span className="font-semibold text-[10px] text-[#f3f4f6]">
                {brief.style}
              </span>
            </div>
            <div className="rounded bg-[#08090c] p-1">
              <span className="block text-[9px] text-[#64748b]">Pacing</span>
              <span className="font-semibold text-[10px] text-[#f3f4f6]">
                {brief.pacing}
              </span>
            </div>
            <div className="rounded bg-[#08090c] p-1">
              <span className="block text-[9px] text-[#64748b]">Aspect</span>
              <span className="font-semibold text-[10px] text-[#f3f4f6]">
                {brief.aspectRatio}
              </span>
            </div>
            <div className="rounded bg-[#08090c] p-1">
              <span className="block text-[9px] text-[#64748b]">Duration</span>
              <span className="font-semibold text-[10px] text-[#f3f4f6]">
                {brief.targetDuration}s
              </span>
            </div>
          </div>

          {/* Explicit Baseten Inference Authorization Checkbox */}
          <div
            className={`mt-3 rounded border p-2.5 transition-colors ${
              showConsentPrompt && !hasAuthorizedBaseten
                ? "border-[#ffe600] bg-[#ffe600]/10 ring-1 ring-[#ffe600]/40"
                : "border-[#1f2433] bg-[#08090c]"
            }`}
          >
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={hasAuthorizedBaseten}
                onChange={(e) => {
                  setHasAuthorizedBaseten(e.target.checked);
                  if (e.target.checked) setShowConsentPrompt(false);
                }}
                className="mt-0.5 h-3.5 w-3.5 rounded border-[#1f2433] bg-[#11141e] text-[#ffe600] focus:ring-0 accent-[#ffe600]"
              />
              <span className="text-[10px] leading-tight text-[#9ca3af]">
                Authorize <strong className="text-[#ffffff]">Baseten</strong> (<span className="text-[#ffe600] font-mono text-[9px]">muse-spark-open-1026</span>) to analyze video via short-lived private S3 URL.
              </span>
            </label>
            {showConsentPrompt && !hasAuthorizedBaseten && (
              <p className="mt-1.5 text-[10px] font-semibold text-[#ffe600]">
                ⚠ Please check the box above to authorize Baseten analysis before proceeding.
              </p>
            )}
          </div>

          {/* Primary Blueprint Generation CTA */}
          <button
            type="button"
            onClick={handleTriggerGenerate}
            disabled={isGenerating}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-md bg-[#ffe600] py-2 text-xs font-bold text-[#000000] shadow-[0_0_12px_rgba(255,230,0,0.25)] transition-all hover:bg-[#fff04d] active:scale-98 disabled:opacity-50"
          >
            <span className="text-xs">✦</span>
            <span>
              {isGenerating
                ? generationStage || "Analyzing Footage with Baseten..."
                : "Generate Editing Blueprint"}
            </span>
            <span className="text-xs">→</span>
          </button>
        </div>

        {/* KEY MOMENTS Section */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[#ffe600]">✦</span>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#ffffff]">
                Key Moments
              </h3>
            </div>
            <span className="font-mono text-[10px] text-[#64748b]">
              {moments.length} moments
            </span>
          </div>

          {/* Moment Cards */}
          <div className="space-y-2">
            {moments.map((moment) => {
              const isSelected = activeMomentId === moment.id;
              return (
                <div
                  key={moment.id}
                  className={`group relative flex items-start gap-2.5 rounded-lg border p-2.5 transition-all ${
                    isSelected
                      ? "border-[#ffe600] bg-[#161a26] ring-1 ring-[#ffe600]/30"
                      : "border-[#1f2433] bg-[#0c0e15] hover:border-[#333a4c] hover:bg-[#11141e]"
                  }`}
                >
                  {/* Moment Index Number */}
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[#181c28] font-mono text-[10px] font-bold text-[#9ca3af]">
                    {moment.index}
                  </span>

                  {/* Thumbnail / Visual Graphic */}
                  <div className="relative h-12 w-14 shrink-0 overflow-hidden rounded bg-[#1a1f2c] flex items-center justify-center">
                    <div className="absolute inset-0 bg-gradient-to-br from-[#ffe600]/15 to-transparent opacity-40" />
                    <svg className="h-4 w-4 text-[#ffe600]" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>

                  {/* Moment Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] font-bold text-[#ffe600]">
                        {moment.timecode}
                      </span>
                      <span
                        className={`rounded border px-1.5 py-0.2 font-mono text-[9px] font-bold uppercase ${getTagBadgeStyle(
                          moment.tag
                        )}`}
                      >
                        {moment.tag}
                      </span>
                    </div>

                    <h4 className="mt-0.5 truncate text-[11px] font-bold text-[#ffffff]">
                      {moment.title}
                    </h4>

                    <p className="line-clamp-2 text-[10px] leading-tight text-[#9ca3af]">
                      {moment.description}
                    </p>
                  </div>

                  {/* Jump / Seek Button */}
                  <button
                    type="button"
                    onClick={() => onJumpToMoment(moment.seconds, moment.id)}
                    title={`Seek player to ${moment.timecode}`}
                    className="shrink-0 self-center rounded border border-[#ffe600]/50 bg-[#ffe600]/10 px-2 py-1 text-[10px] font-bold text-[#ffe600] transition-colors hover:bg-[#ffe600] hover:text-[#000000]"
                  >
                    Jump
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* AI Suggestions Section */}
        <div className="rounded-lg border border-[#1f2433] bg-[#0c0e15] p-3">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-xs text-[#ffe600]">💡</span>
            <h3 className="text-xs font-bold text-[#ffffff]">AI Suggestions</h3>
          </div>

          <ul className="space-y-2 text-[11px] text-[#9ca3af]">
            {aiSuggestions.map((suggestion, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-0.5 text-[#ffe600] font-bold">✔</span>
                <span className="leading-snug">{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
