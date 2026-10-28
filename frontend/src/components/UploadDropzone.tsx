"use client";

import { useState } from "react";

export function UploadDropzone({
  onSelectPreset,
}: {
  onSelectPreset?: (brief: string) => void;
}) {
  const [selectedDemo, setSelectedDemo] = useState<string | null>(null);

  const demoClips = [
    {
      id: "sprint",
      title: "Athlete Prep & Sprint (32s)",
      brief:
        "Create an intense 30-second kinetic teaser; build slow tension during prep and cut rapidly on the acceleration.",
    },
    {
      id: "macro",
      title: "Coffee Brew Macro (28s)",
      brief:
        "Cut a sleek 20-second product reel; emphasize steam rising, drip contact, and satisfying pouring sounds.",
    },
  ];

  return (
    <div className="rounded-xl border border-[#262b33] bg-[#111418] p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[#9ca3af]">
          1. Source Video
        </h2>
        <span className="font-mono text-xs text-[#6b7280]">
          MP4 / MOV / WebM • Max 60s • 100 MB
        </span>
      </div>

      <div className="group relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-[#262b33] bg-[#0a0c0f] p-8 text-center transition-colors hover:border-[#e6ff00]/40">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-[#262b33] bg-[#181c22] text-[#e6ff00]">
          <svg
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.75}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>

        <p className="mb-1 text-sm font-medium text-[#f3f4f6]">
          Drop video clip here, or browse files
        </p>
        <p className="text-xs text-[#6b7280]">
          Direct browser upload to private S3 via presigned URL (Phase 1)
        </p>

        <input
          type="file"
          accept="video/mp4,video/quicktime,video/webm"
          className="absolute inset-0 cursor-pointer opacity-0"
          disabled
          aria-label="Upload raw video file (Phase 1 integration)"
        />
      </div>

      <div className="mt-4 pt-4 border-t border-[#1c2026]">
        <div className="mb-2 text-xs font-medium text-[#9ca3af]">
          Or test with authorized starter clip:
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {demoClips.map((demo) => (
            <button
              key={demo.id}
              type="button"
              onClick={() => {
                setSelectedDemo(demo.id);
                onSelectPreset?.(demo.brief);
              }}
              className={`flex flex-col items-start rounded-lg border p-3 text-left transition-all ${
                selectedDemo === demo.id
                  ? "border-[#e6ff00] bg-[#181c22] ring-1 ring-[#e6ff00]/40"
                  : "border-[#262b33] bg-[#0a0c0f] hover:border-[#383f4a] hover:bg-[#181c22]"
              }`}
            >
              <div className="flex w-full items-center justify-between text-xs font-semibold text-[#f3f4f6]">
                <span>{demo.title}</span>
                {selectedDemo === demo.id && (
                  <span className="text-[10px] font-mono font-bold text-[#e6ff00]">
                    SELECTED
                  </span>
                )}
              </div>
              <p className="mt-1 line-clamp-1 text-[11px] text-[#9ca3af]">
                {demo.brief}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
