"use client";

import { useMemo, useRef, useState } from "react";
import { MediaClip } from "@/types/workstation";
import { formatTimecode } from "@/lib/timecode";

interface MediaBinProps {
  clips: MediaClip[];
  activeClipId: string | null;
  onSelectClip: (clip: MediaClip) => void;
  onImportCustomVideo: (file: File) => void;
  onDeleteClip?: (clipId: string) => void;
  isUploading?: boolean;
  uploadError?: string | null;
  onDismissError?: () => void;
}

export function MediaBin({
  clips,
  activeClipId,
  onSelectClip,
  onImportCustomVideo,
  onDeleteClip,
  isUploading = false,
  uploadError = null,
  onDismissError,
}: MediaBinProps) {
  const [activeFilter, setActiveFilter] = useState<"all" | "video" | "audio" | "image">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredClips = useMemo(() => {
    return clips.filter((clip) => {
      const matchesType =
        activeFilter === "all" ? true : clip.type === activeFilter;
      const matchesSearch = clip.title
        .toLowerCase()
        .includes(searchQuery.toLowerCase().trim());
      return matchesType && matchesSearch;
    });
  }, [clips, activeFilter, searchQuery]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      onImportCustomVideo(file);
      // Reset input so same file can be re-imported
      e.target.value = "";
    }
  };

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-[#1f2433] bg-[#0d1016] select-none">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-[#1f2433] px-4 py-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#ffffff]">
            Project Media
          </h2>
          <p className="text-[10px] text-[#64748b]">7-day auto-retention</p>
        </div>

        <button
          type="button"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1 rounded border border-[#ffe600] px-2.5 py-1 text-xs font-semibold text-[#ffe600] transition-all hover:bg-[#ffe600] hover:text-[#000000] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="text-sm leading-none">+</span>
          <span>{isUploading ? "Uploading..." : "Import"}</span>
        </button>

        {/* Hidden native file input for real uploads */}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
          onChange={handleFileChange}
          className="hidden"
          aria-label="Import local video clip"
        />
      </div>

      {/* Error notification banner if upload fails or is invalid */}
      {uploadError && (
        <div className="flex items-center justify-between border-b border-[#ef4444]/30 bg-[#ef4444]/10 px-3 py-2 text-[11px] text-[#fca5a5]">
          <span className="truncate pr-2">{uploadError}</span>
          {onDismissError && (
            <button
              type="button"
              onClick={onDismissError}
              className="text-[#fca5a5] hover:text-[#ffffff]"
              title="Dismiss error"
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 border-b border-[#1f2433] px-3 py-2 text-xs">
        {(["all", "video", "audio", "image"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveFilter(tab)}
            className={`rounded px-2.5 py-1 font-medium capitalize transition-colors ${
              activeFilter === tab
                ? "bg-[#181c28] text-[#ffffff]"
                : "text-[#9ca3af] hover:text-[#f3f4f6]"
            }`}
          >
            {tab === "image" ? "Images" : tab}
          </button>
        ))}
      </div>

      {/* Search Bar */}
      <div className="border-b border-[#1f2433] p-3">
        <div className="relative flex items-center">
          <svg
            className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[#64748b]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search media..."
            className="w-full rounded border border-[#1f2433] bg-[#08090c] py-1.5 pl-8 pr-7 text-xs text-[#ffffff] placeholder-[#64748b] transition-colors focus:border-[#ffe600] focus:outline-none"
          />
        </div>
      </div>

      {/* Media Items Grid */}
      <div className="flex-1 overflow-y-auto p-3">
        {filteredClips.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center text-center text-xs text-[#64748b]">
            <svg className="mb-2 h-8 w-8 text-[#252a3a]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
            </svg>
            <p>No media files found</p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="mt-2 text-[#ffe600] underline hover:text-[#fff04d]"
            >
              Import video clip (max 100MB)
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2.5">
            {filteredClips.map((clip) => {
              const isSelected = activeClipId === clip.id;
              const isPending = clip.status === "pending";
              const isFailed = clip.status === "failed";
              const isExpired = clip.status === "expired";
              const progress = clip.uploadProgress ?? 0;

              return (
                <div
                  key={clip.id}
                  className={`group relative flex flex-col overflow-hidden rounded border text-left transition-all ${
                    isSelected
                      ? "border-[#ffe600] bg-[#141724] ring-1 ring-[#ffe600]/40"
                      : "border-[#1f2433] bg-[#08090c] hover:border-[#333a4c] hover:bg-[#121520]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectClip(clip)}
                    className="w-full text-left"
                  >
                    {/* Thumbnail / Visual Placeholder */}
                    <div className="relative aspect-video w-full overflow-hidden bg-[#10131c]">
                      {clip.type === "audio" ? (
                        <div className="flex h-full w-full items-center justify-center bg-[#0d101a] p-2 text-[#ffe600]">
                          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                          </svg>
                        </div>
                      ) : (
                        <div className="relative flex h-full w-full items-center justify-center bg-gradient-to-br from-[#1a1e2c] to-[#0a0d14]">
                          <span className="font-mono text-[10px] text-[#64748b]">
                            {clip.resolution || "HD"}
                          </span>
                          {/* Film strip edge indicator */}
                          <div className="absolute top-1 left-1 flex gap-0.5 opacity-40">
                            <span className="h-1 w-1 rounded-full bg-[#ffffff]" />
                            <span className="h-1 w-1 rounded-full bg-[#ffffff]" />
                          </div>
                        </div>
                      )}

                      {/* Upload Progress Overlay */}
                      {isPending && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#000000]/80 p-2">
                          <span className="font-mono text-[10px] font-bold text-[#ffe600]">
                            {progress}%
                          </span>
                          <div className="mt-1 h-1 w-3/4 overflow-hidden rounded-full bg-[#222]">
                            <div
                              className="h-full bg-[#ffe600] transition-all duration-200"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <span className="mt-1 text-[9px] text-[#9ca3af]">Uploading</span>
                        </div>
                      )}

                      {/* Status Badges */}
                      {isFailed && (
                        <span className="absolute top-1 left-1 rounded bg-[#ef4444] px-1 py-0.5 text-[8px] font-bold text-[#ffffff]">
                          FAILED
                        </span>
                      )}

                      {isExpired && (
                        <span className="absolute top-1 left-1 rounded bg-[#f59e0b] px-1 py-0.5 text-[8px] font-bold text-[#000000]">
                          EXPIRED
                        </span>
                      )}

                      {clip.isRealUpload && clip.status === "verified" && (
                        <span className="absolute top-1 left-1 flex items-center gap-1 rounded bg-[#000000]/80 px-1 py-0.5 text-[8px] font-semibold text-[#ffe600]">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#ffe600]" />
                          S3
                        </span>
                      )}

                      {/* Duration badge */}
                      <span className="absolute bottom-1 right-1 rounded bg-[#000000]/80 px-1 py-0.2 font-mono text-[9px] text-[#f3f4f6]">
                        {formatTimecode(clip.duration)}
                      </span>
                    </div>

                    {/* Title and Metadata */}
                    <div className="p-1.5">
                      <p className="truncate text-[11px] font-medium text-[#f3f4f6] group-hover:text-[#ffffff]">
                        {clip.title}
                      </p>
                      <p className="mt-0.5 font-mono text-[9px] text-[#64748b]">
                        {clip.resolution ? `${clip.resolution} • ` : ""}
                        {clip.size}
                      </p>
                    </div>
                  </button>

                  {/* Delete Button (accessible on hover or for custom uploads) */}
                  {onDeleteClip && (clip.isRealUpload || clip.isCustom) && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Delete "${clip.title}" and its storage asset?`)) {
                          onDeleteClip(clip.id);
                        }
                      }}
                      title="Delete asset"
                      className="absolute top-1 right-1 hidden rounded bg-[#000000]/80 p-1 text-[#ef4444] hover:bg-[#ef4444] hover:text-[#ffffff] group-hover:block"
                    >
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
