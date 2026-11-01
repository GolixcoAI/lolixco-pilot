"use client";

import { useState } from "react";
import {
  AIProviderName,
  AudioIntelligenceData,
  CreativeBriefState,
  KeyMoment,
  SourceIdentificationData,
  UsageMetadataData,
  UserFeedbackData,
} from "@/types/workstation";

interface AiDirectorPanelProps {
  brief: CreativeBriefState;
  setBrief: (brief: CreativeBriefState) => void;
  moments: KeyMoment[];
  aiSuggestions: string[];
  activeMomentId: string | null;
  onJumpToMoment: (seconds: number, momentId: string) => void;
  onGenerateBlueprint: (confirmedConsent: boolean, provider?: AIProviderName) => void;
  isGenerating: boolean;
  generationStage?: string | null;
  analysisError?: string | null;
  onDismissError?: () => void;
  selectedProvider?: AIProviderName;
  onSelectProvider?: (provider: AIProviderName) => void;
  sourceIntelligence?: SourceIdentificationData | null;
  audioIntelligence?: AudioIntelligenceData | null;
  usageMetadata?: UsageMetadataData | null;
  userFeedback?: UserFeedbackData | null;
  onFeedbackSubmit?: (feedback: {
    confirmed_by_user: boolean;
    corrected_source_title?: string | null;
    corrected_song_title?: string | null;
    notes?: string | null;
  }) => void;
  hasUploadedVideo?: boolean;
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
  selectedProvider = "baseten",
  onSelectProvider,
  sourceIntelligence,
  audioIntelligence,
  usageMetadata,
  userFeedback,
  onFeedbackSubmit,
  hasUploadedVideo,
}: AiDirectorPanelProps) {
  const [isEditingBrief, setIsEditingBrief] = useState(false);
  const [editedTitle, setEditedTitle] = useState(brief.title);
  const [editedDesc, setEditedDesc] = useState(brief.description);
  const [hasAuthorizedConsent, setHasAuthorizedConsent] = useState(false);
  const [showConsentPrompt, setShowConsentPrompt] = useState(false);

  // Correction feedback UI state
  const [isEditingCorrection, setIsEditingCorrection] = useState(false);
  const [correctedSource, setCorrectedSource] = useState(
    sourceIntelligence?.likely_title || "",
  );
  const [correctedSong, setCorrectedSong] = useState(
    audioIntelligence?.song_title || "",
  );
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  const handleSaveBrief = () => {
    setBrief({
      ...brief,
      title: editedTitle.trim() || brief.title,
      description: editedDesc.trim() || brief.description,
    });
    setIsEditingBrief(false);
  };

  const handleTriggerGenerate = () => {
    if (!hasAuthorizedConsent) {
      setShowConsentPrompt(true);
      return;
    }
    setShowConsentPrompt(false);
    onGenerateBlueprint(true, selectedProvider);
  };

  const handleConfirmAccuracy = () => {
    if (!onFeedbackSubmit) return;
    setIsSubmittingFeedback(true);
    try {
      onFeedbackSubmit({
        confirmed_by_user: true,
        corrected_source_title: null,
        corrected_song_title: null,
        notes: "Confirmed accurate by user",
      });
      setFeedbackSuccess(true);
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const handleSubmitCorrection = () => {
    if (!onFeedbackSubmit) return;
    setIsSubmittingFeedback(true);
    try {
      onFeedbackSubmit({
        confirmed_by_user: false,
        corrected_source_title: correctedSource.trim() || null,
        corrected_song_title: correctedSong.trim() || null,
        notes: feedbackNotes.trim() || null,
      });
      setIsEditingCorrection(false);
      setFeedbackSuccess(true);
    } finally {
      setIsSubmittingFeedback(false);
    }
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

  const getMatchStatusBadge = (status?: string | null) => {
    switch (status) {
      case "confirmed_fingerprint":
        return {
          label: "Confirmed Fingerprint",
          className: "bg-[#4ade80]/15 text-[#4ade80] border-[#4ade80]/30",
        };
      case "strong_inference":
        return {
          label: "Strong Model Inference",
          className: "bg-[#38bdf8]/15 text-[#38bdf8] border-[#38bdf8]/30",
        };
      case "possible_match":
        return {
          label: "Possible Match",
          className: "bg-[#fbbf24]/15 text-[#fbbf24] border-[#fbbf24]/30",
        };
      default:
        return {
          label: "Unconfirmed",
          className: "bg-[#94a3b8]/15 text-[#94a3b8] border-[#94a3b8]/30",
        };
    }
  };

  const hasIntelligence = Boolean(sourceIntelligence || audioIntelligence);

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

          {/* Provider Selection Segmented Control */}
          <div className="flex items-center rounded-md border border-[#1f2433] bg-[#08090c] p-0.5">
            <button
              type="button"
              onClick={() => onSelectProvider?.("baseten")}
              className={`rounded px-2 py-0.5 font-mono text-[9px] font-bold transition-colors ${
                selectedProvider === "baseten"
                  ? "bg-[#ffe600]/15 text-[#ffe600] border border-[#ffe600]/40 shadow-sm"
                  : "text-[#64748b] hover:text-[#9ca3af]"
              }`}
            >
              Baseten
            </button>
            <button
              type="button"
              onClick={() => onSelectProvider?.("meta")}
              className={`rounded px-2 py-0.5 font-mono text-[9px] font-bold transition-colors ${
                selectedProvider === "meta"
                  ? "bg-[#38bdf8]/15 text-[#38bdf8] border border-[#38bdf8]/40 shadow-sm"
                  : "text-[#64748b] hover:text-[#9ca3af]"
              }`}
            >
              Meta AI
            </button>
          </div>
        </div>

        <p className="mt-0.5 text-[11px] text-[#9ca3af]">
          {selectedProvider === "meta"
            ? "Official Meta Model API · muse-spark-1.3"
            : "Baseten Inference · muse-spark-open-1026"}
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

        {/* Contextual Suggestion Banner after Upload (Phase C & E) */}
        {hasUploadedVideo && !hasIntelligence && !isGenerating && (
          <div className="rounded-lg border border-[#ffe600]/40 bg-[#ffe600]/10 p-3.5 space-y-2.5 shadow-[0_0_15px_rgba(255,230,0,0.1)]">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[#ffe600]">
              <span>✦</span>
              <span>Footage Ready for Multimodal Intelligence</span>
            </div>
            <p className="text-[11px] leading-relaxed text-[#f3f4f6]">
              Video uploaded. Want me to identify the source, characters, and soundtrack?
            </p>
            <button
              type="button"
              onClick={handleTriggerGenerate}
              className="flex w-full items-center justify-center gap-1.5 rounded-md bg-[#ffe600] py-2 text-xs font-bold text-[#000000] shadow-[0_0_10px_rgba(255,230,0,0.3)] transition-all hover:bg-[#fff04d] active:scale-98"
            >
              <span>✦</span>
              <span>Identify source, characters & soundtrack</span>
              <span>→</span>
            </button>
          </div>
        )}

        {/* Structured Media Intelligence Card (Phase C & E) */}
        {hasIntelligence && (
          <div className="rounded-lg border border-[#1f2433] bg-[#11141e] p-3.5 space-y-3">
            <div className="flex items-center justify-between border-b border-[#1f2433] pb-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-[#ffe600]">✦</span>
                <h3 className="text-xs font-bold text-[#ffffff] uppercase tracking-wider">
                  Media Intelligence
                </h3>
              </div>
              {sourceIntelligence?.confidence && (
                <span className="rounded bg-[#ffe600]/15 px-1.5 py-0.5 font-mono text-[9px] font-bold text-[#ffe600] border border-[#ffe600]/30 uppercase">
                  {sourceIntelligence.confidence} confidence
                </span>
              )}
            </div>

            {/* Source Identification */}
            {sourceIntelligence && (
              <div className="space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-[#64748b]">
                      Likely Source
                    </span>
                    <h4 className="text-xs font-bold text-[#ffffff]">
                      {sourceIntelligence.likely_title || "Unconfirmed Title"}
                    </h4>
                    {sourceIntelligence.franchise && (
                      <span className="text-[10px] text-[#9ca3af]">
                        Franchise: {sourceIntelligence.franchise}
                      </span>
                    )}
                  </div>
                  <span className="rounded bg-[#08090c] px-2 py-0.5 font-mono text-[9px] font-semibold text-[#9ca3af] border border-[#1f2433] uppercase">
                    {sourceIntelligence.media_type}
                  </span>
                </div>

                {/* Character Candidates */}
                {sourceIntelligence.characters && sourceIntelligence.characters.length > 0 && (
                  <div className="pt-1">
                    <span className="text-[9px] uppercase tracking-wider text-[#64748b]">
                      Recognized Characters:
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {sourceIntelligence.characters.map((char, i) => (
                        <span
                          key={i}
                          className="rounded bg-[#08090c] px-1.5 py-0.5 text-[10px] text-[#f3f4f6] border border-[#1f2433]"
                        >
                          {char}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Audio Intelligence */}
            {audioIntelligence && (
              <div className="border-t border-[#1a1f2c] pt-2.5 space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-[#64748b]">
                      Soundtrack & Audio
                    </span>
                    <h4 className="text-xs font-bold text-[#ffffff]">
                      {audioIntelligence.song_title ? (
                        <>
                          {audioIntelligence.song_title}
                          {audioIntelligence.artist && (
                            <span className="text-[#9ca3af] font-normal">
                              {" "}— {audioIntelligence.artist}
                            </span>
                          )}
                        </>
                      ) : (
                        "No confirmed song match"
                      )}
                    </h4>
                  </div>
                  {(() => {
                    const badge = getMatchStatusBadge(audioIntelligence.match_status);
                    return (
                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[9px] font-bold ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    );
                  })()}
                </div>

                {/* Musical Hallmarks */}
                <div className="flex flex-wrap gap-1.5 text-[10px] text-[#9ca3af]">
                  {audioIntelligence.genre && (
                    <span className="rounded bg-[#08090c] px-1.5 py-0.5 border border-[#1f2433]">
                      {audioIntelligence.genre}
                    </span>
                  )}
                  {audioIntelligence.tempo && (
                    <span className="rounded bg-[#08090c] px-1.5 py-0.5 border border-[#1f2433]">
                      {audioIntelligence.tempo}
                    </span>
                  )}
                  {audioIntelligence.mood && (
                    <span className="rounded bg-[#08090c] px-1.5 py-0.5 border border-[#1f2433]">
                      {audioIntelligence.mood}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* User Feedback & Correction Section (Phase E) */}
            <div className="border-t border-[#1a1f2c] pt-2.5">
              {feedbackSuccess || userFeedback ? (
                <div className="rounded bg-[#4ade80]/10 border border-[#4ade80]/30 p-2 text-center text-[10px] text-[#4ade80] font-semibold">
                  ✓ {userFeedback?.confirmed_by_user ? "Verified by editor" : "Correction saved"}:{" "}
                  {userFeedback?.corrected_source_title || userFeedback?.corrected_song_title
                    ? [userFeedback?.corrected_source_title, userFeedback?.corrected_song_title].filter(Boolean).join(" · ")
                    : "Feedback submitted. Thank you for helping refine editor accuracy!"}
                </div>
              ) : isEditingCorrection ? (
                <div className="space-y-2 rounded bg-[#08090c] p-2.5 border border-[#1f2433]">
                  <span className="text-[10px] font-bold text-[#ffffff]">
                    Correct Identification
                  </span>
                  <input
                    type="text"
                    value={correctedSource}
                    onChange={(e) => setCorrectedSource(e.target.value)}
                    placeholder="Correct anime / film title..."
                    className="w-full rounded border border-[#1f2433] bg-[#11141e] p-1.5 text-xs text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
                  />
                  <input
                    type="text"
                    value={correctedSong}
                    onChange={(e) => setCorrectedSong(e.target.value)}
                    placeholder="Correct track / artist..."
                    className="w-full rounded border border-[#1f2433] bg-[#11141e] p-1.5 text-xs text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
                  />
                  <textarea
                    rows={1}
                    value={feedbackNotes}
                    onChange={(e) => setFeedbackNotes(e.target.value)}
                    placeholder="Notes (optional)..."
                    className="w-full resize-none rounded border border-[#1f2433] bg-[#11141e] p-1.5 text-xs text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
                  />
                  <div className="flex justify-end gap-1.5">
                    <button
                      type="button"
                      onClick={() => setIsEditingCorrection(false)}
                      className="rounded px-2 py-1 text-[10px] font-semibold text-[#9ca3af] hover:text-[#ffffff]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleSubmitCorrection}
                      disabled={isSubmittingFeedback}
                      className="rounded bg-[#ffe600] px-2.5 py-1 text-[10px] font-bold text-[#000000] hover:bg-[#fff04d] disabled:opacity-50"
                    >
                      Save Correction
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#64748b]">
                    Is this identification accurate?
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleConfirmAccuracy}
                      disabled={isSubmittingFeedback}
                      className="rounded border border-[#4ade80]/40 bg-[#4ade80]/10 px-2 py-0.5 text-[10px] font-semibold text-[#4ade80] hover:bg-[#4ade80] hover:text-[#000000] transition-colors"
                    >
                      ✓ Yes
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsEditingCorrection(true)}
                      className="rounded border border-[#1f2433] bg-[#08090c] px-2 py-0.5 text-[10px] font-semibold text-[#9ca3af] hover:text-[#ffffff] transition-colors"
                    >
                      ✎ Edit
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Inference Telemetry Line */}
            {usageMetadata && (
              <div className="border-t border-[#1a1f2c] pt-2 flex items-center justify-between text-[9px] font-mono text-[#64748b]">
                <span>
                  {selectedProvider === "meta" ? "Meta AI" : "Baseten"}
                  {usageMetadata.latency_ms
                    ? ` · ${(usageMetadata.latency_ms / 1000).toFixed(1)}s`
                    : ""}
                </span>
                {usageMetadata.total_tokens && (
                  <span>{usageMetadata.total_tokens} tokens</span>
                )}
              </div>
            )}
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

          {/* Explicit User Inference Authorization Checkbox (Cost Protection) */}
          <div
            className={`mt-3 rounded border p-2.5 transition-colors ${
              showConsentPrompt && !hasAuthorizedConsent
                ? "border-[#ffe600] bg-[#ffe600]/10 ring-1 ring-[#ffe600]/40"
                : "border-[#1f2433] bg-[#08090c]"
            }`}
          >
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={hasAuthorizedConsent}
                onChange={(e) => {
                  setHasAuthorizedConsent(e.target.checked);
                  if (e.target.checked) setShowConsentPrompt(false);
                }}
                className="mt-0.5 h-3.5 w-3.5 rounded border-[#1f2433] bg-[#11141e] text-[#ffe600] focus:ring-0 accent-[#ffe600]"
              />
              <span className="text-[10px] leading-tight text-[#9ca3af]">
                Authorize{" "}
                <strong className="text-[#ffffff]">
                  {selectedProvider === "meta" ? "Meta AI" : "Baseten"}
                </strong>{" "}
                ({selectedProvider === "meta" ? "muse-spark-1.3" : "muse-spark-open-1026"}) to
                analyze video via short-lived private S3 URL.
              </span>
            </label>
            {showConsentPrompt && !hasAuthorizedConsent && (
              <p className="mt-1.5 text-[10px] font-semibold text-[#ffe600]">
                ⚠ Please check the box above to authorize analysis before proceeding.
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
                ? generationStage || "Analyzing Footage..."
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
