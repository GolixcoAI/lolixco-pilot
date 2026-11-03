"use client";

import { useMemo, useRef, useState } from "react";
import Image from "next/image";
import { KeyMoment, MediaClip } from "@/types/workstation";

interface TimelineProps {
  currentTime: number;
  duration: number;
  moments: KeyMoment[];
  activeClip: MediaClip | null;
  onSeek: (seconds: number) => void;
  beatTimestamps?: number[];
}

export function Timeline({
  currentTime,
  duration,
  onSeek,
}: TimelineProps) {
  const [activeTab, setActiveTab] = useState<
    "timeline" | "scenes" | "aicuts" | "effects" | "color" | "audio" | "captions"
  >("timeline");
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [snapping, setSnapping] = useState(true);
  const rulerRef = useRef<HTMLDivElement>(null);

  const totalDuration = duration > 0 ? duration : 30.18;
  const playheadPercent = Math.min(100, Math.max(0, (currentTime / totalDuration) * 100));

  // SMPTE 30fps timecode formatter: 00:00:12:14
  const formatSMPTE = (sec: number) => {
    const totalFrames = Math.floor(sec * 30);
    const frames = totalFrames % 30;
    const s = Math.floor(sec % 60);
    const m = Math.floor((sec / 60) % 60);
    const h = Math.floor(sec / 3600);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(frames).padStart(2, "0")}`;
  };

  const rulerTicks = useMemo(() => {
    return [
      { sec: 0.0, label: "00:00:00:00" },
      { sec: 4.0, label: "00:00:04:00" },
      { sec: 8.0, label: "00:00:08:00", marker: "Build-up" },
      { sec: 12.0, label: "00:00:12:00" },
      { sec: 16.0, label: "00:00:16:00", marker: "Convergence" },
      { sec: 20.0, label: "00:00:20:00", marker: "Discharge" },
      { sec: 24.0, label: "00:00:24:00", marker: "Impact" },
      { sec: 28.0, label: "00:00:28:00" },
      { sec: 30.18, label: "00:00:30:18" },
    ];
  }, []);

  // Video shots sequence with real thumbnails
  const videoShots = [
    { id: "shot-1", start: 0.0, end: 4.0, img: "/frames/gojo/frame_00_000.5s.png" },
    { id: "shot-2", start: 4.0, end: 9.0, img: "/frames/gojo/frame_01_006.0s.png" },
    { id: "shot-3", start: 9.0, end: 14.0, img: "/frames/gojo/frame_02_012.0s.png" },
    { id: "shot-4", start: 14.0, end: 18.0, img: "/frames/gojo/frame_04_024.0s.png" },
    { id: "shot-5", start: 18.0, end: 23.0, img: "/frames/gojo/frame_08_044.0s.png" },
    { id: "shot-6", start: 23.0, end: 30.18, img: "/frames/gojo/frame_10_058.0s.png" },
  ];

  const handleRulerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!rulerRef.current) return;
    const rect = rulerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(ratio * totalDuration);
  };

  return (
    <div className="flex h-64 shrink-0 flex-col border-t border-[#1f2433] bg-[#08090c] select-none text-[#d1d5db]">
      {/* Timeline Header Tabs */}
      <div className="flex h-8 items-center border-b border-[#1f2433] bg-[#0c0e14] px-3 gap-1 text-[11px] font-semibold">
        {[
          { id: "timeline", label: "Timeline" },
          { id: "scenes", label: "Scenes" },
          { id: "aicuts", label: "AI Cuts" },
          { id: "effects", label: "Effects" },
          { id: "color", label: "Color" },
          { id: "audio", label: "Audio" },
          { id: "captions", label: "Captions" },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`relative px-2.5 py-1.5 transition-colors ${
                isActive ? "text-[#ffe600]" : "text-[#9ca3af] hover:text-[#f3f4f6]"
              }`}
            >
              {tab.label}
              {isActive && (
                <span className="absolute bottom-0 left-2 right-2 h-[2px] bg-[#ffe600]" />
              )}
            </button>
          );
        })}
      </div>

      {/* Toolbar: Undo/Redo, Yellow Timecode, Snap, Zoom */}
      <div className="flex h-8 items-center justify-between border-b border-[#1f2433] bg-[#0a0c10] px-3 text-xs">
        {/* Left: Tools & Timecode */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[#9ca3af]">
            <button type="button" title="Undo" className="p-1 hover:text-[#ffffff]">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2m0 0l-4-4m4 4l4-4" />
              </svg>
            </button>
            <button type="button" title="Redo" className="p-1 hover:text-[#ffffff]">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a5 5 0 00-5 5v2m0 0l4-4m-4 4l-4-4" />
              </svg>
            </button>
          </div>

          <div className="h-3 w-px bg-[#1f2433]" />

          {/* Timecode display */}
          <div className="flex items-center gap-2 font-mono">
            <span className="text-xs font-bold text-[#ffe600]">
              {formatSMPTE(currentTime)}
            </span>
          </div>
        </div>

        {/* Right: Snapping, Zoom Slider, Fit */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSnapping(!snapping)}
            className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold transition-colors ${
              snapping ? "bg-[#1f2433] text-[#ffe600]" : "text-[#64748b] hover:text-[#ffffff]"
            }`}
          >
            <span>🧲</span>
            <span>Snap</span>
          </button>

          {/* Zoom slider */}
          <div className="flex items-center gap-1.5 text-[10px] text-[#64748b]">
            <span>-</span>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={zoomLevel}
              onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
              aria-label="Timeline zoom"
              className="h-1 w-20 cursor-pointer appearance-none rounded-full bg-[#1f2433] accent-[#ffe600]"
            />
            <span>+</span>
          </div>

          <button
            type="button"
            title="Fit to view"
            className="p-1 text-[#64748b] hover:text-[#f3f4f6]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main Timeline Workspace: Left Track Headers + Right Timeline Tracks */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Track Headers Column (Left) */}
        <div className="w-28 shrink-0 border-r border-[#1f2433] bg-[#0c0e14] text-[10px] font-semibold text-[#9ca3af]">
          {/* Ruler spacer */}
          <div className="h-6 border-b border-[#1f2433] bg-[#090b10] px-2 flex items-center">
            <span>TRACKS</span>
          </div>

          {/* V2 Effects Header */}
          <div className="flex h-11 items-center justify-between border-b border-[#1f2433] px-2">
            <div className="flex items-center gap-1.5">
              <span>🔒</span>
              <span className="text-[#f3f4f6]">V2</span>
              <span>Effects</span>
            </div>
            <span>👁</span>
          </div>

          {/* V1 Video Header */}
          <div className="flex h-14 items-center justify-between border-b border-[#1f2433] px-2">
            <div className="flex items-center gap-1.5">
              <span>🔒</span>
              <span className="text-[#ffe600]">V1</span>
              <span>Video</span>
            </div>
            <span>👁</span>
          </div>

          {/* A1 Audio Header */}
          <div className="flex h-12 items-center justify-between border-b border-[#1f2433] px-2">
            <div className="flex items-center gap-1.5">
              <span>🔒</span>
              <span className="text-[#22c55e]">A1</span>
              <span>Audio</span>
            </div>
            <span>🔊</span>
          </div>
        </div>

        {/* Tracks Area (Right) */}
        <div
          ref={rulerRef}
          onClick={handleRulerClick}
          className="relative flex-1 cursor-pointer overflow-hidden bg-[#07080b]"
        >
          {/* Time Ruler */}
          <div className="relative h-6 w-full border-b border-[#1f2433] bg-[#090b10] text-[9px] font-mono text-[#64748b]">
            {rulerTicks.map((t) => {
              const leftPct = (t.sec / totalDuration) * 100;
              return (
                <div
                  key={t.sec}
                  className="absolute top-0 flex flex-col items-center"
                  style={{ left: `${leftPct}%` }}
                >
                  <span className="-translate-x-1/2 pt-0.5">{t.label}</span>
                  {t.marker && (
                    <span className="absolute top-3.5 -translate-x-1/2 rounded bg-[#ffe600] px-1 text-[8px] font-bold text-[#000000] shadow-sm">
                      {t.marker}
                    </span>
                  )}
                  <span className="h-1.5 w-px bg-[#1f2433]" />
                </div>
              );
            })}
          </div>

          {/* Track 1: V2 Effects Track */}
          <div className="relative h-11 w-full border-b border-[#1f2433] bg-[#080a0e] p-1">
            {/* Speed Ramp Block */}
            <div
              className="absolute top-1.5 h-8 rounded border border-[#3b82f6]/60 bg-[#1e293b] px-2 flex items-center text-[10px] font-semibold text-[#60a5fa] shadow-sm"
              style={{
                left: `${(10.0 / totalDuration) * 100}%`,
                width: `${(6.0 / totalDuration) * 100}%`,
              }}
            >
              <span className="truncate">Speed Ramp (0.8x → 1.3x)</span>
            </div>

            {/* Glow / Energy FX Block */}
            <div
              className="absolute top-1.5 h-8 rounded border border-[#a855f7]/60 bg-[#2e1065]/70 px-2 flex items-center text-[10px] font-semibold text-[#c084fc] shadow-sm"
              style={{
                left: `${(18.0 / totalDuration) * 100}%`,
                width: `${(8.0 / totalDuration) * 100}%`,
              }}
            >
              <span className="truncate">Glow / Energy FX</span>
            </div>
          </div>

          {/* Track 2: V1 Video Track with Thumbnails & Cuts */}
          <div className="relative h-14 w-full border-b border-[#1f2433] bg-[#050608] flex items-center overflow-hidden">
            {videoShots.map((shot, idx) => {
              const leftPct = (shot.start / totalDuration) * 100;
              const widthPct = ((shot.end - shot.start) / totalDuration) * 100;
              return (
                <div
                  key={shot.id}
                  className="absolute top-0 bottom-0 border-r border-[#000000] overflow-hidden"
                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                >
                  <div className="relative h-full w-full">
                    <Image
                      src={shot.img}
                      alt={`Shot ${idx + 1}`}
                      fill
                      className="object-cover opacity-80"
                    />
                  </div>
                  {/* Transition icon */}
                  {idx > 0 && (
                    <div className="absolute top-1 left-1 flex h-4 w-4 items-center justify-center rounded bg-[#000000]/80 font-mono text-[9px] font-bold text-[#ffe600]">
                      ⨉
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Track 3: A1 Audio Track with Neon Green Waveform */}
          <div className="relative h-12 w-full border-b border-[#1f2433] bg-[#040608] flex items-center overflow-hidden">
            <svg
              className="h-full w-full text-[#22c55e]"
              preserveAspectRatio="none"
              viewBox="0 0 1000 60"
            >
              <path
                d="M0 30 Q20 10, 40 30 T80 30 T120 15 T160 30 T200 45 T240 30 T280 10 T320 30 T360 50 T400 30 T440 5 T480 30 T520 55 T560 30 T600 5 T640 30 T680 50 T720 30 T760 12 T800 30 T840 48 T880 30 T920 20 T960 30 T1000 30"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              />
              <path
                d="M0 30 Q20 20, 40 30 T80 30 T120 22 T160 30 T200 38 T240 30 T280 20 T320 30 T360 40 T400 30 T440 18 T480 30 T520 42 T560 30 T600 18 T640 30 T680 42 T720 30 T760 22 T800 30 T840 38 T880 30 T920 24 T960 30 T1000 30"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
                opacity="0.5"
              />
            </svg>
          </div>

          {/* Yellow Playhead Needle */}
          <div
            className="pointer-events-none absolute top-0 bottom-0 z-30 flex flex-col items-center"
            style={{ left: `${playheadPercent}%` }}
          >
            {/* Top yellow inverted triangle */}
            <div className="h-0 w-0 border-x-4 border-x-transparent border-t-6 border-t-[#ffe600]" />
            {/* Vertical yellow playhead line */}
            <div className="h-full w-[2px] bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.8)]" />
          </div>
        </div>
      </div>
    </div>
  );
}
