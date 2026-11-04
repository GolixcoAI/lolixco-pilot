"use client";

import { useMemo, useRef, useState } from "react";
import Image from "next/image";
import { MediaClip } from "@/types/workstation";

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
  const [activeTab, setActiveTab] = useState<"all" | "video" | "audio" | "image">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [showUploadCard, setShowUploadCard] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredClips = useMemo(() => {
    return clips.filter((clip) => {
      const matchesType =
        activeTab === "all" ? true : clip.type === activeTab;
      const matchesSearch = clip.title
        .toLowerCase()
        .includes(searchQuery.toLowerCase().trim());
      return matchesType && matchesSearch;
    });
  }, [clips, activeTab, searchQuery]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      onImportCustomVideo(file);
      e.target.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onImportCustomVideo(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="flex h-full w-[290px] shrink-0 flex-col border-r border-[#1f2433] bg-[#0c0e14] select-none text-[#d1d5db]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f2433] px-3.5 py-2.5">
        <h2 className="text-xs font-bold text-[#ffffff] tracking-wide">
          Media Bin
        </h2>
        <button
          type="button"
          title="Filter media"
          className="rounded p-1 text-[#9ca3af] hover:bg-[#161a26] hover:text-[#ffffff]"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
        </button>
      </div>

      {/* Media Type Tabs */}
      <div className="flex border-b border-[#1f2433] px-2 text-[11px] font-medium text-[#9ca3af]">
        {(["all", "video", "audio", "image"] as const).map((tab) => {
          const labels = { all: "All Media", video: "Video", audio: "Audio", image: "Image" };
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`relative px-2.5 py-1.5 transition-colors ${
                isActive ? "text-[#ffffff]" : "hover:text-[#f3f4f6]"
              }`}
            >
              {labels[tab]}
              {isActive && (
                <span className="absolute bottom-0 left-2.5 right-2.5 h-[2px] bg-[#ffe600]" />
              )}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Prominent Import Button */}
        <button
          type="button"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-[#ffe600] py-2 text-xs font-bold text-[#000000] shadow-[0_0_12px_rgba(255,230,0,0.25)] transition-all hover:bg-[#fff04d] active:scale-98 disabled:opacity-50"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <span>{isUploading ? "Uploading..." : "Import Media"}</span>
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
          onChange={handleFileChange}
          className="hidden"
          aria-label="Import local video"
        />

        {/* Drag and Drop Zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[#23293a] bg-[#090b10] px-3 py-4 text-center transition-colors hover:border-[#ffe600]/40"
        >
          <div className="mb-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-[#141722] text-[#9ca3af]">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p className="text-[11px] font-medium text-[#f3f4f6]">
            Drop video, audio, or images here
          </p>
          <p className="mt-0.5 text-[9px] text-[#64748b]">
            MP4, MOV, MKV, WAV, MP3, PNG, JPG · up to 8 GB
          </p>
        </div>

        {/* Upload Progress Card (Only shown during active upload) */}
        {isUploading && (
          <div className="relative rounded-md border border-[#1f2433] bg-[#11141e] p-2.5">
            <div className="flex items-center gap-2.5">
              <div className="relative h-10 w-12 shrink-0 overflow-hidden rounded bg-[#000000]">
                <Image
                  src="/frames/gojo/frame_00_000.5s.png"
                  alt="Upload Thumbnail"
                  fill
                  className="object-cover"
                />
              </div>
              <div className="min-w-0 flex-1 pr-4">
                <p className="truncate text-xs font-semibold text-[#f3f4f6]">
                  Uploading footage...
                </p>
                <p className="text-[10px] text-[#9ca3af]">
                  Processing and verifying with S3
                </p>
                {/* Yellow Progress Bar */}
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[#1f2433]">
                  <div
                    className="h-full bg-[#ffe600] transition-all duration-300"
                    style={{ width: "87%" }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Search & Layout toggle */}
        <div className="flex items-center gap-1.5 pt-1">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search media..."
              className="w-full rounded border border-[#1f2433] bg-[#11141e] py-1 pl-7 pr-2 text-xs text-[#f3f4f6] placeholder-[#64748b] focus:border-[#ffe600] focus:outline-none"
            />
            <svg
              className="absolute left-2 top-2 h-3.5 w-3.5 text-[#64748b]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <div className="flex items-center rounded border border-[#1f2433] bg-[#11141e] p-0.5 text-[#9ca3af]">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`rounded p-1 ${viewMode === "grid" ? "bg-[#1f2433] text-[#ffe600]" : "hover:text-[#ffffff]"}`}
              title="Grid View"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`rounded p-1 ${viewMode === "list" ? "bg-[#1f2433] text-[#ffe600]" : "hover:text-[#ffffff]"}`}
              title="List View"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {/* Dynamic Media Items List */}
        <div className="space-y-1.5 pt-1">
          {filteredClips.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-[#64748b] space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#141722] border border-[#1f2433] text-sm text-[#9ca3af]">
                📁
              </div>
              <div>
                <p className="text-xs font-semibold text-[#9ca3af]">No media in bin</p>
                <p className="mt-0.5 text-[10px] text-[#64748b]">Drop video files above to start</p>
              </div>
            </div>
          ) : (
            filteredClips.map((clip) => {
              const isActive = clip.id === activeClipId;
              return (
                <div
                  key={clip.id}
                  onClick={() => onSelectClip(clip)}
                  className={`group flex cursor-pointer items-center justify-between rounded-md border p-2 transition-colors ${
                    isActive
                      ? "border-[#ffe600] bg-[#1a1f2c]"
                      : "border-[#1f2433] bg-[#11141e] hover:border-[#ffe600]/40 hover:bg-[#161a26]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="relative h-9 w-12 shrink-0 overflow-hidden rounded bg-[#000000]">
                      <Image
                        src="/frames/gojo/frame_00_000.5s.png"
                        alt={clip.title}
                        fill
                        className="object-cover"
                      />
                      <span className="absolute bottom-0.5 right-0.5 rounded bg-[#000000]/80 px-1 font-mono text-[8px] font-bold text-[#ffffff]">
                        {Math.floor(clip.duration)}s
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-[#f3f4f6]">
                        {clip.title}
                      </p>
                      <p className="text-[10px] font-mono text-[#9ca3af]">
                        {clip.resolution || "1080p"} · {clip.duration.toFixed(1)}s · {clip.size || "Video"}
                      </p>
                    </div>
                  </div>
                  {onDeleteClip && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteClip(clip.id);
                      }}
                      className="text-[#64748b] hover:text-[#ef4444] px-1 text-xs"
                      title="Delete clip"
                    >
                      ✕
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
