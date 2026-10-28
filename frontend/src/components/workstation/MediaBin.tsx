"use client";

import { useMemo, useRef, useState } from "react";
import { MediaClip } from "@/types/workstation";
import { formatTimecode } from "@/lib/timecode";

interface MediaBinProps {
  clips: MediaClip[];
  activeClipId: string | null;
  onSelectClip: (clip: MediaClip) => void;
  onImportCustomVideo: (file: File) => void;
}

export function MediaBin({
  clips,
  activeClipId,
  onSelectClip,
  onImportCustomVideo,
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
    }
  };

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-[#1f2433] bg-[#0d1016] select-none">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-[#1f2433] px-4 py-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#ffffff]">
          Project Media
        </h2>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-1 rounded border border-[#ffe600] px-2.5 py-1 text-xs font-semibold text-[#ffe600] transition-all hover:bg-[#ffe600] hover:text-[#000000]"
        >
          <span className="text-sm leading-none">+</span>
          <span>Import</span>
        </button>

        {/* Hidden native file input for real local uploads */}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/webm"
          onChange={handleFileChange}
          className="hidden"
          aria-label="Import local video clip"
        />
      </div>

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

          <button
            type="button"
            title="Filter by resolution / duration"
            className="absolute right-2 text-[#64748b] hover:text-[#f3f4f6]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
          </button>
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
              Import video clip
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2.5">
            {filteredClips.map((clip) => {
              const isSelected = activeClipId === clip.id;
              return (
                <button
                  key={clip.id}
                  type="button"
                  onClick={() => onSelectClip(clip)}
                  className={`group relative flex flex-col overflow-hidden rounded border text-left transition-all ${
                    isSelected
                      ? "border-[#ffe600] bg-[#141724] ring-1 ring-[#ffe600]/40"
                      : "border-[#1f2433] bg-[#08090c] hover:border-[#333a4c] hover:bg-[#121520]"
                  }`}
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
                      <div className="relative h-full w-full bg-gradient-to-br from-[#1a1e2c] to-[#0a0d14] flex items-center justify-center">
                        <span className="text-[10px] font-mono text-[#64748b]">
                          {clip.resolution}
                        </span>
                        {/* Film strip edge indicator */}
                        <div className="absolute top-1 left-1 flex gap-0.5 opacity-40">
                          <span className="h-1 w-1 rounded-full bg-[#ffffff]" />
                          <span className="h-1 w-1 rounded-full bg-[#ffffff]" />
                        </div>
                      </div>
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
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
