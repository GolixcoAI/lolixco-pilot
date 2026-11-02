"use client";

import { useMemo, useRef, useState } from "react";
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
  moments,
  activeClip,
  onSeek,
  beatTimestamps,
}: TimelineProps) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [snapping, setSnapping] = useState(true);
  const rulerRef = useRef<HTMLDivElement>(null);

  const totalSeconds = duration > 0 ? duration : 32;

  // Generate ruler tick marks every 5 seconds up to totalSeconds
  const rulerTicks = useMemo(() => {
    const ticks: { sec: number; label: string }[] = [];
    const step = 5;
    for (let s = 0; s <= totalSeconds; s += step) {
      const mins = Math.floor(s / 60);
      const secs = s % 60;
      ticks.push({
        sec: s,
        label: `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`,
      });
    }
    return ticks;
  }, [totalSeconds]);

  const handleRulerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!rulerRef.current) return;
    const rect = rulerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(ratio * totalSeconds);
  };

  const playheadPercent = Math.min(100, Math.max(0, (currentTime / totalSeconds) * 100));

  return (
    <div className="flex h-64 shrink-0 flex-col border-t border-[#1f2433] bg-[#08090c] select-none">
      {/* Timeline Toolbar */}
      <div className="flex h-9 items-center justify-between border-b border-[#1f2433] bg-[#0c0e15] px-4">
        {/* Left edit tools */}
        <div className="flex items-center gap-1 text-[#9ca3af]">
          {/* Undo */}
          <button type="button" title="Undo (Ctrl+Z)" className="rounded p-1 hover:text-[#ffffff]">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2m0 0l-4-4m4 4l4-4" />
            </svg>
          </button>

          {/* Redo */}
          <button type="button" title="Redo (Ctrl+Y)" className="rounded p-1 hover:text-[#ffffff]">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a5 5 0 00-5 5v2m0 0l4-4m-4 4l-4-4" />
            </svg>
          </button>

          <div className="mx-1 h-3.5 w-px bg-[#202532]" />

          {/* Split / Razor */}
          <button type="button" title="Split clip at playhead (C)" className="rounded p-1 hover:text-[#ffffff]">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0-5.758a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z" />
            </svg>
          </button>

          {/* Delete */}
          <button type="button" title="Delete selected (Del)" className="rounded p-1 hover:text-[#ffffff]">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>

          {/* Snapping */}
          <button
            type="button"
            onClick={() => setSnapping(!snapping)}
            title="Toggle Magnet / Snapping (S)"
            className={`rounded p-1 transition-colors ${
              snapping ? "text-[#ffe600]" : "text-[#64748b] hover:text-[#ffffff]"
            }`}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </button>
        </div>

        {/* Right timeline controls: Zoom, Waveform */}
        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <button
            type="button"
            onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
            className="text-xs text-[#9ca3af] hover:text-[#ffffff]"
          >
            −
          </button>

          <input
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={zoomLevel}
            onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
            aria-label="Timeline zoom level"
            className="h-1 w-20 cursor-pointer accent-[#ffe600]"
          />

          <button
            type="button"
            onClick={() => setZoomLevel((z) => Math.min(2, z + 0.25))}
            className="text-xs text-[#9ca3af] hover:text-[#ffffff]"
          >
            +
          </button>
        </div>
      </div>

      {/* Main Timeline Workspace: Left Track Headers + Right Track Ruler & Tracks */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Track Headers Rack */}
        <div className="flex w-24 shrink-0 flex-col border-r border-[#1f2433] bg-[#0c0e15] text-[11px] font-mono text-[#9ca3af]">
          {/* Ruler Corner Spacer */}
          <div className="h-6 border-b border-[#1f2433]" />

          {/* Track V2 */}
          <div className="flex h-11 items-center justify-between border-b border-[#1f2433] px-2">
            <span className="font-bold text-[#64748b]">V2</span>
            <div className="flex items-center gap-1 text-[#64748b]">
              <span className="cursor-pointer hover:text-[#ffffff]">🔒</span>
              <span className="cursor-pointer hover:text-[#ffffff]">👁</span>
            </div>
          </div>

          {/* Track V1 (Active Highlighted Track) */}
          <div className="flex h-14 items-center justify-between border-b border-[#1f2433] bg-[#141724] px-2 border-l-2 border-l-[#ffe600]">
            <span
              title={activeClip ? `Active Clip: ${activeClip.title}` : "Track V1 (Main)"}
              className="rounded bg-[#ffe600]/15 px-1 font-bold text-[#ffe600] border border-[#ffe600]/40"
            >
              V1
            </span>
            <div className="flex items-center gap-1 text-[#ffe600]">
              <span className="cursor-pointer">🔒</span>
              <span className="cursor-pointer">👁</span>
            </div>
          </div>

          {/* Track A1 (Audio Primary) */}
          <div className="flex h-11 items-center justify-between border-b border-[#1f2433] px-2">
            <span className="font-bold text-[#9ca3af]">A1</span>
            <div className="flex items-center gap-1 text-[#64748b]">
              <span className="cursor-pointer hover:text-[#ffffff]">🔒</span>
              <span className="cursor-pointer hover:text-[#ffffff]">🔊</span>
            </div>
          </div>

          {/* Track A2 (Audio Secondary) */}
          <div className="flex h-11 items-center justify-between border-b border-[#1f2433] px-2">
            <span className="font-bold text-[#64748b]">A2</span>
            <div className="flex items-center gap-1 text-[#64748b]">
              <span className="cursor-pointer hover:text-[#ffffff]">🔒</span>
              <span className="cursor-pointer hover:text-[#ffffff]">🔊</span>
            </div>
          </div>

          {/* Add Track */}
          <button
            type="button"
            className="flex items-center justify-center py-1 text-[10px] text-[#64748b] hover:text-[#ffe600]"
          >
            + Add Track
          </button>
        </div>

        {/* Right Scrollable Timeline Channels & Ruler */}
        <div
          ref={rulerRef}
          onClick={handleRulerClick}
          className="relative flex-1 overflow-x-auto bg-[#07080b] cursor-pointer"
        >
          {/* Top Time Ruler */}
          <div className="relative h-6 w-full border-b border-[#1f2433] bg-[#0a0c12]">
            {rulerTicks.map((tick) => {
              const leftPercent = (tick.sec / totalSeconds) * 100;
              return (
                <div
                  key={tick.sec}
                  className="absolute top-0 flex flex-col items-center"
                  style={{ left: `${leftPercent}%` }}
                >
                  <span className="font-mono text-[9px] text-[#64748b]">
                    {tick.label}
                  </span>
                  <span className="h-1.5 w-px bg-[#252a38]" />
                </div>
              );
            })}
          </div>

          {/* Track V2 Clips Container */}
          <div className="relative h-11 w-full border-b border-[#1f2433]/60">
            {/* Sample Overlay Clip on V2 */}
            <div
              className="absolute top-1 bottom-1 rounded border border-[#3b82f6]/40 bg-[#1e293b]/70 px-2 flex items-center justify-between text-[10px] text-[#93c5fd]"
              style={{ left: "28%", width: "24%" }}
            >
              <span className="truncate">overlay_broll.mov</span>
              <span className="rounded bg-[#0f172a] px-1 font-mono text-[8px] text-[#60a5fa] border border-[#3b82f6]/40">
                fx
              </span>
            </div>

            <div
              className="absolute top-1 bottom-1 rounded border border-[#ef4444]/40 bg-[#3b1219]/60 px-2 flex items-center justify-between text-[10px] text-[#fca5a5]"
              style={{ left: "68%", width: "20%" }}
            >
              <span className="truncate">impact_flash.mp4</span>
              <span className="rounded bg-[#0f172a] px-1 font-mono text-[8px] text-[#ef4444] border border-[#ef4444]/40">
                fx
              </span>
            </div>
          </div>

          {/* Track V1 Clips Container (Main Cuts) */}
          <div className="relative h-14 w-full border-b border-[#1f2433]/60 bg-[#0d1017]/40">
            {/* Sequence of clip blocks based on moments */}
            {moments.map((moment, idx) => {
              const startRatio = moment.seconds / totalSeconds;
              const nextSec = moments[idx + 1] ? moments[idx + 1].seconds : totalSeconds;
              const widthRatio = Math.max(0.08, (nextSec - moment.seconds) / totalSeconds);

              return (
                <div
                  key={moment.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(moment.seconds);
                  }}
                  title={`Click to seek playhead to ${moment.timecode}`}
                  className="group absolute top-1 bottom-1 flex flex-col justify-between overflow-hidden rounded border border-[#333d52] bg-[#161b29] p-1.5 shadow-sm transition-colors hover:border-[#ffe600] cursor-pointer"
                  style={{
                    left: `${startRatio * 100}%`,
                    width: `${widthRatio * 100}%`,
                  }}
                >
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="truncate font-semibold text-[#f3f4f6]">
                      {moment.title}
                    </span>
                    <span className="font-mono text-[8px] text-[#ffe600]">
                      {moment.tag}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[8px] font-mono text-[#64748b]">
                    <span>{moment.timecode}</span>
                    <span className="text-[#ffe600]">⧖</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Track A1 Audio Waveform Container (Bright Neon Yellow Waveform & Beat Markers) */}
          <div className="relative h-11 w-full border-b border-[#1f2433]/60 bg-[#0a0d14]">
            {/* Dynamic beat markers on musical onsets */}
            {beatTimestamps &&
              beatTimestamps.map((beat, i) => {
                const leftPercent = (beat / totalSeconds) * 100;
                if (leftPercent > 100) return null;
                return (
                  <div
                    key={i}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSeek(beat);
                    }}
                    title={`Beat sync marker at ${beat.toFixed(1)}s (Click to seek)`}
                    className="absolute top-0 bottom-0 z-20 flex flex-col items-center cursor-pointer group"
                    style={{ left: `${leftPercent}%` }}
                  >
                    <div className="h-2 w-2 rounded-full bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.9)] -translate-y-0.5" />
                    <div className="h-full w-px bg-[#ffe600]/40 group-hover:bg-[#ffe600] group-hover:w-[2px] transition-all" />
                  </div>
                );
              })}

            <svg
              className="h-full w-full"
              preserveAspectRatio="none"
              viewBox="0 0 600 40"
            >
              {/* Dynamic waveform path in neon yellow */}
              <path
                d="M0,20 Q20,5 40,20 T80,20 T120,5 T160,20 T200,32 T240,20 T280,2 T320,20 T360,35 T400,20 T440,8 T480,20 T520,30 T560,20 T600,20"
                fill="none"
                stroke="#ffe600"
                strokeWidth="1.8"
                className="drop-shadow-[0_0_4px_rgba(255,230,0,0.5)]"
              />
              {/* Audio keyframe nodes */}
              <circle cx="120" cy="5" r="3" fill="#ffe600" />
              <circle cx="280" cy="2" r="3" fill="#ffe600" />
              <circle cx="440" cy="8" r="3" fill="#ffe600" />
            </svg>
          </div>

          {/* Track A2 Secondary Audio (Ambient Waveform) */}
          <div className="relative h-11 w-full bg-[#07090f]">
            <svg
              className="h-full w-full opacity-40"
              preserveAspectRatio="none"
              viewBox="0 0 600 40"
            >
              <path
                d="M0,20 Q30,12 60,20 T120,20 T180,14 T240,20 T300,25 T360,20 T420,12 T480,20 T540,24 T600,20"
                fill="none"
                stroke="#64748b"
                strokeWidth="1.2"
              />
            </svg>
          </div>

          {/* Full Height Playhead Needle & Handle */}
          <div
            className="pointer-events-none absolute top-0 bottom-0 z-30 -translate-x-1/2"
            style={{ left: `${playheadPercent}%` }}
          >
            {/* Downward triangle pointer handle */}
            <div className="h-0 w-0 border-x-4 border-t-6 border-x-transparent border-t-[#ffe600] drop-shadow-[0_0_6px_rgba(255,230,0,0.8)]" />
            {/* Playhead vertical line */}
            <div className="h-full w-[2px] bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.8)]" />
          </div>
        </div>
      </div>
    </div>
  );
}
