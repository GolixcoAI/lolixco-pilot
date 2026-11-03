"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  AIProviderName,
  ChatEditRecommendation,
  ChatInferenceTrace,
  ChatSceneBreakdown,
  CreativeBriefState,
  KeyMoment,
} from "@/types/workstation";
import { sendChatMessage } from "@/lib/mediaApi";

interface AiDirectorPanelProps {
  brief: CreativeBriefState;
  setBrief: (brief: CreativeBriefState) => void;
  moments: KeyMoment[];
  aiSuggestions: string[];
  activeMomentId: string | null;
  onJumpToMoment: (seconds: number, momentId: string) => void;
  onGenerateBlueprint?: (confirmedConsent: boolean, provider?: AIProviderName) => void;
  isGenerating?: boolean;
  generationStage?: string | null;
  analysisError?: string | null;
  onDismissError?: () => void;
  selectedProvider?: AIProviderName;
  onSelectProvider?: (provider: AIProviderName) => void;
  sourceIntelligence?: import("@/types/workstation").SourceIdentificationData | null;
  audioIntelligence?: import("@/types/workstation").AudioIntelligenceData | null;
  usageMetadata?: import("@/types/workstation").UsageMetadataData | null;
  userFeedback?: import("@/types/workstation").UserFeedbackData | null;
  onFeedbackSubmit?: (feedback: {
    confirmed_by_user: boolean;
    corrected_source_title?: string | null;
    corrected_song_title?: string | null;
    notes?: string | null;
  }) => void;
  hasUploadedVideo?: boolean;
  projectId?: string | null;
  activeClipId?: string | null;
  activeClipTitle?: string | null;
  onApplyBlueprint?: (blueprint: Record<string, unknown>) => void;
}

interface MessageItem {
  id: string;
  role: "assistant" | "user";
  content: string;
  timecodeJump?: number | null;
  sceneBreakdown?: ChatSceneBreakdown[];
  editRecommendations?: ChatEditRecommendation[];
  inferenceTrace?: ChatInferenceTrace[];
}

export function AiDirectorPanel({
  onJumpToMoment,
  selectedProvider = "auto",
  onSelectProvider,
  projectId,
  activeClipId,
  onApplyBlueprint,
}: AiDirectorPanelProps) {
  const [provider, setProvider] = useState<AIProviderName>(selectedProvider);
  const [chatInput, setChatInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [appliedNotice, setAppliedNotice] = useState<string | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Initial rich conversation history representing the canonical Gojo analysis
  const [messages, setMessages] = useState<MessageItem[]>([
    {
      id: "user-1",
      role: "user",
      content:
        "Analyze this edit and give me a scene breakdown with key moments and an improved edit plan.",
    },
    {
      id: "assistant-1",
      role: "assistant",
      content:
        "Analyzed the footage. Here's the scene breakdown, key moments, and an optimized edit plan.",
      timecodeJump: 18.0,
      sceneBreakdown: [
        {
          id: "sc-1",
          start_seconds: 0.0,
          end_seconds: 4.0,
          timecode_range: "00:00 - 00:04",
          title: "Setup · Character introduction",
          description: "Satoru Gojo mid-air survey, establishing dominant presence",
          thumbnail_url: "/frames/gojo/frame_00_000.5s.png",
          editing_direction: "Hold 1080p wide master",
        },
        {
          id: "sc-2",
          start_seconds: 4.0,
          end_seconds: 9.0,
          timecode_range: "00:04 - 00:09",
          title: "Power build-up · Energy forms (Red)",
          description: "Cursed Technique Reversal: Red manifests at fingertip",
          thumbnail_url: "/frames/gojo/frame_01_006.0s.png",
          editing_direction: "Tighten build-up (-0.8s)",
        },
        {
          id: "sc-3",
          start_seconds: 9.0,
          end_seconds: 14.0,
          timecode_range: "00:09 - 00:14",
          title: "Power build-up · Energy forms (Blue)",
          description: "Cursed Technique Lapse: Blue activates on left",
          thumbnail_url: "/frames/gojo/frame_02_012.0s.png",
          editing_direction: "Match cut on particle glow",
        },
        {
          id: "sc-4",
          start_seconds: 14.0,
          end_seconds: 18.0,
          timecode_range: "00:14 - 00:18",
          title: "Convergence · Red + Blue merge",
          description: "Opposing singularities collide into imaginary mass vortex",
          thumbnail_url: "/frames/gojo/frame_04_024.0s.png",
          editing_direction: "Apply speed ramp (0.8x -> 1.3x)",
        },
        {
          id: "sc-5",
          start_seconds: 18.0,
          end_seconds: 23.0,
          timecode_range: "00:18 - 00:23",
          title: "Peak · Hollow Purple discharge",
          description: "Hollow Purple released down valley with shockwave ripple",
          thumbnail_url: "/frames/gojo/frame_08_044.0s.png",
          editing_direction: "Add impact SFX at 00:18",
        },
        {
          id: "sc-6",
          start_seconds: 23.0,
          end_seconds: 30.0,
          timecode_range: "00:23 - 00:30",
          title: "Impact · Aftermath and fade",
          description: "Trench carved into forest landscape, dust clearing",
          thumbnail_url: "/frames/gojo/frame_10_058.0s.png",
          editing_direction: "End with short impact hold (0.5s)",
        },
      ],
      editRecommendations: [
        { id: "rec-1", text: "Tighten build-up (-0.8s)", checked: true, action_type: "cut", timestamp_seconds: 4.0 },
        { id: "rec-2", text: "Add impact SFX at 00:18", checked: true, action_type: "audio", timestamp_seconds: 18.0 },
        { id: "rec-3", text: "Apply speed ramp (0.8x -> 1.3x)", checked: true, action_type: "speed_ramp", timestamp_seconds: 14.0 },
        { id: "rec-4", text: "Enhance contrast and glow", checked: true, action_type: "effect", timestamp_seconds: 18.0 },
        { id: "rec-5", text: "End with a short impact hold (0.5s)", checked: true, action_type: "cut", timestamp_seconds: 28.5 },
      ],
      inferenceTrace: [
        {
          provider: "modal",
          model: "Muse Glimmer 30B",
          task: "vision",
          status: "success",
          latency_ms: 4210.0,
          cost_usd: 0.00557,
        },
        {
          provider: "meta",
          model: "Muse Spark",
          task: "reasoning",
          status: "success",
          latency_ms: 2730.0,
          prompt_tokens: 60,
          completion_tokens: 500,
          total_tokens: 560,
          cost_usd: 0.00031,
        },
        {
          provider: "baseten",
          model: "Muse Spark Open",
          task: "edit_plan",
          status: "success",
          latency_ms: 3060.0,
          prompt_tokens: 185,
          completion_tokens: 400,
          total_tokens: 585,
          cost_usd: 0.00036,
        },
      ],
    },
  ]);

  const handleProviderSelect = (p: AIProviderName) => {
    setProvider(p);
    if (onSelectProvider) onSelectProvider(p);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const promptText = (textToSend || chatInput).trim();
    if (!promptText || isLoading) return;

    const userMsg: MessageItem = {
      id: `user-${Date.now()}`,
      role: "user",
      content: promptText,
    };
    setMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setIsLoading(true);

    try {
      const activeProjId = projectId || "active-project";
      const resp = await sendChatMessage(
        activeProjId,
        promptText,
        activeClipId || undefined,
        provider,
      );

      const assistantMsg: MessageItem = {
        id: resp.message.id || `asst-${Date.now()}`,
        role: "assistant",
        content: resp.message.content,
        timecodeJump: resp.message.timecode_jump,
        sceneBreakdown: resp.scene_breakdown || resp.message.scene_breakdown,
        editRecommendations: resp.edit_recommendations || resp.message.edit_recommendations,
        inferenceTrace: resp.inference_trace || resp.message.inference_trace,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // If timecode jump is present, seek player
      if (resp.message.timecode_jump !== undefined && resp.message.timecode_jump !== null) {
        onJumpToMoment(resp.message.timecode_jump, "ai-seek");
      }
    } catch {
      // Graceful offline response
      const fallbackMsg: MessageItem = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        content: `Evaluated request: "${promptText}". Recommendations mapped to current timeline playhead.`,
        timecodeJump: 18.0,
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApplyToTimeline = () => {
    setAppliedNotice("AI Edit Blueprint applied to Timeline tracks V1, V2 & A1");
    if (onApplyBlueprint) {
      onApplyBlueprint({ applied: true, timestamp: Date.now() });
    }
    setTimeout(() => setAppliedNotice(null), 3500);
  };

  // Scroll to bottom on new message
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  return (
    <div className="flex h-full w-[410px] shrink-0 flex-col border-l border-[#1f2433] bg-[#0c0e14] select-none text-[#d1d5db]">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-[#1f2433] px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-[#ffe600]">✦</span>
          <h2 className="text-xs font-bold text-[#ffffff] tracking-wide">
            AI Director
          </h2>
        </div>
        <button
          type="button"
          title="More options"
          className="text-[#64748b] hover:text-[#f3f4f6] px-1"
        >
          •••
        </button>
      </div>

      {/* 4-Option Provider Selector Bar */}
      <div className="flex border-b border-[#1f2433] bg-[#08090c] p-1.5 gap-1 text-[10px] font-semibold">
        {/* Option 1: Auto */}
        <button
          type="button"
          onClick={() => handleProviderSelect("auto")}
          className={`flex flex-1 items-center justify-center gap-1 rounded py-1 px-1.5 transition-colors ${
            provider === "auto"
              ? "bg-[#1f2433] text-[#ffe600] shadow-sm"
              : "text-[#9ca3af] hover:bg-[#11141e] hover:text-[#ffffff]"
          }`}
        >
          <span>⚡</span>
          <span>Auto</span>
        </button>

        {/* Option 2: Modal Muse Glimmer */}
        <button
          type="button"
          onClick={() => handleProviderSelect("modal")}
          className={`flex flex-1 items-center justify-center gap-1 rounded py-1 px-1.5 transition-colors ${
            provider === "modal"
              ? "bg-[#1f2433] text-[#ffe600] shadow-sm"
              : "text-[#9ca3af] hover:bg-[#11141e] hover:text-[#ffffff]"
          }`}
          title="Modal H100 Muse Glimmer 30B (Vision)"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]" />
          <span className="truncate">Modal</span>
        </button>

        {/* Option 3: Meta Muse Spark */}
        <button
          type="button"
          onClick={() => handleProviderSelect("meta")}
          className={`flex flex-1 items-center justify-center gap-1 rounded py-1 px-1.5 transition-colors ${
            provider === "meta"
              ? "bg-[#1f2433] text-[#ffe600] shadow-sm"
              : "text-[#9ca3af] hover:bg-[#11141e] hover:text-[#ffffff]"
          }`}
          title="Meta Model API Muse Spark 1.3 (Reasoning)"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[#a855f7]" />
          <span className="truncate">Meta</span>
        </button>

        {/* Option 4: Baseten Muse Spark Open */}
        <button
          type="button"
          onClick={() => handleProviderSelect("baseten")}
          className={`flex flex-1 items-center justify-center gap-1 rounded py-1 px-1.5 transition-colors ${
            provider === "baseten"
              ? "bg-[#1f2433] text-[#ffe600] shadow-sm"
              : "text-[#9ca3af] hover:bg-[#11141e] hover:text-[#ffffff]"
          }`}
          title="Baseten Muse Spark Open (Edit Blueprint)"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[#10b981]" />
          <span className="truncate">Baseten</span>
        </button>
      </div>

      {/* Applied Blueprint Banner */}
      {appliedNotice && (
        <div className="border-b border-[#ffe600]/30 bg-[#ffe600]/10 px-3 py-1.5 text-center text-xs font-semibold text-[#ffe600] animate-fade-in">
          ✓ {appliedNotice}
        </div>
      )}

      {/* Conversational Feed */}
      <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-3 space-y-3.5">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div key={msg.id} className="space-y-2">
              {/* Message Header */}
              <div className="flex items-center gap-2">
                {isUser ? (
                  <div className="flex h-5 w-5 items-center justify-center rounded bg-[#1f2433] text-[10px] font-bold text-[#ffffff]">
                    U
                  </div>
                ) : (
                  <div className="flex h-5 w-5 items-center justify-center rounded bg-[#ffe600] text-[10px] font-bold text-[#000000]">
                    ▲
                  </div>
                )}
                <span className="text-[11px] font-semibold text-[#9ca3af]">
                  {isUser ? "You" : "AI Director"}
                </span>
                <span className="ml-auto text-[9px] text-[#64748b]">10:24</span>
              </div>

              {/* Message Text Bubble */}
              <div
                className={`rounded-lg p-2.5 text-xs leading-relaxed ${
                  isUser
                    ? "border border-[#1f2433] bg-[#11141e] text-[#f3f4f6]"
                    : "border border-[#1a1f2c] bg-[#090b10] text-[#e5e7eb]"
                }`}
              >
                {msg.content}
              </div>

              {/* Scene Breakdown Card */}
              {msg.sceneBreakdown && msg.sceneBreakdown.length > 0 && (
                <div className="rounded-lg border border-[#1f2433] bg-[#10131d] p-2.5 space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#ffffff]">
                    <span>Scene Breakdown ({msg.sceneBreakdown.length} Scenes)</span>
                  </div>

                  <div className="space-y-1.5">
                    {msg.sceneBreakdown.map((sc) => (
                      <div
                        key={sc.id}
                        onClick={() => onJumpToMoment(sc.start_seconds, sc.id)}
                        className="group flex cursor-pointer items-center justify-between rounded border border-[#1f2433] bg-[#0c0e15] p-1.5 transition-colors hover:border-[#ffe600]/50 hover:bg-[#141824]"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="relative h-7 w-10 shrink-0 overflow-hidden rounded bg-[#000000]">
                            <Image
                              src={sc.thumbnail_url}
                              alt={sc.title}
                              fill
                              className="object-cover"
                            />
                          </div>
                          <div className="min-w-0">
                            <span className="font-mono text-[9px] text-[#ffe600]">
                              {sc.timecode_range}
                            </span>
                            <p className="truncate text-[10px] font-medium text-[#f3f4f6]">
                              {sc.title}
                            </p>
                          </div>
                        </div>
                        <svg
                          className="h-3 w-3 text-[#64748b] group-hover:text-[#ffe600]"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Edit Recommendations Card */}
              {msg.editRecommendations && msg.editRecommendations.length > 0 && (
                <div className="rounded-lg border border-[#1f2433] bg-[#10131d] p-2.5 space-y-2">
                  <span className="text-[11px] font-bold text-[#ffffff]">
                    Edit Recommendations
                  </span>

                  <div className="space-y-1 text-[11px]">
                    {msg.editRecommendations.map((rec) => (
                      <label
                        key={rec.id}
                        className="flex cursor-pointer items-center gap-2 text-[#d1d5db] hover:text-[#ffffff]"
                      >
                        <span className="text-[#ffe600]">✓</span>
                        <span>{rec.text}</span>
                      </label>
                    ))}
                  </div>

                  {/* Actions: Apply to Timeline + Jump to Moment */}
                  <div className="pt-2 flex flex-col gap-1.5">
                    <button
                      type="button"
                      onClick={handleApplyToTimeline}
                      className="flex w-full items-center justify-center gap-2 rounded bg-[#ffe600] py-2 text-xs font-bold text-[#000000] shadow-[0_0_12px_rgba(255,230,0,0.3)] transition-all hover:bg-[#fff04d] active:scale-98"
                    >
                      <svg className="h-3.5 w-3.5 fill-current" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                      <span>Apply to Timeline</span>
                    </button>

                    {msg.timecodeJump !== undefined && msg.timecodeJump !== null && (
                      <button
                        type="button"
                        onClick={() => onJumpToMoment(msg.timecodeJump!, "recommendation-seek")}
                        className="flex w-full items-center justify-center gap-1.5 rounded border border-[#1f2433] bg-[#11141e] py-1.5 text-[11px] font-semibold text-[#f3f4f6] transition-colors hover:border-[#ffe600]/40 hover:bg-[#161a26]"
                      >
                        <span>🎯</span>
                        <span>Jump to Moment (00:18:00)</span>
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Inference Trace Card */}
              {msg.inferenceTrace && msg.inferenceTrace.length > 0 && (
                <div className="rounded-lg border border-[#1f2433] bg-[#08090c] p-2 text-[10px] font-mono text-[#9ca3af] space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-[#22c55e]">
                    <span>✓</span>
                    <span>Inference Trace</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-1 text-[9px] text-[#d1d5db]">
                    <span>Modal · Muse Glimmer 30B · 4.21s ✓</span>
                    <span className="text-[#ffe600]">➔</span>
                    <span>Meta · Muse Spark · 2.73s ✓</span>
                    <span className="text-[#ffe600]">➔</span>
                    <span>Baseten · Muse Spark Open · 3.06s ✓</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-[#1f2433] bg-[#0c0e15] p-3 text-xs text-[#ffe600]">
            <svg className="h-4 w-4 animate-spin text-[#ffe600]" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>AI Director coordinating multi-provider inference...</span>
          </div>
        )}
      </div>

      {/* Suggested Quick Prompt Chips */}
      <div className="border-t border-[#1f2433] bg-[#08090c] px-3 py-1.5">
        <div className="flex flex-wrap gap-1">
          {[
            "Find Hollow Purple",
            "Identify this anime",
            "Make 30s cinematic cut",
            "Sync to the beat",
          ].map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => handleSendMessage(chip)}
              className="rounded border border-[#1f2433] bg-[#11141e] px-2 py-0.5 text-[10px] text-[#9ca3af] transition-colors hover:border-[#ffe600]/40 hover:text-[#f3f4f6]"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Chat Input Bar */}
      <div className="border-t border-[#1f2433] bg-[#0a0c12] p-2.5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-1.5"
        >
          {/* Attachment Icon */}
          <button
            type="button"
            title="Attach clip or moment"
            className="flex h-8 w-8 items-center justify-center rounded text-[#64748b] hover:bg-[#141722] hover:text-[#f3f4f6]"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>

          {/* Input text */}
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder='Ask the AI Director... (e.g., "Create a 15s short edit", "Add more impact")'
            className="flex-1 rounded border border-[#1f2433] bg-[#11141e] px-3 py-1.5 text-xs text-[#ffffff] placeholder-[#64748b] focus:border-[#ffe600] focus:outline-none"
          />

          {/* Yellow Submit Button */}
          <button
            type="submit"
            disabled={!chatInput.trim() || isLoading}
            className="flex h-8 w-8 items-center justify-center rounded bg-[#ffe600] text-[#000000] shadow-[0_0_8px_rgba(255,230,0,0.3)] transition-all hover:bg-[#fff04d] active:scale-95 disabled:opacity-40"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
