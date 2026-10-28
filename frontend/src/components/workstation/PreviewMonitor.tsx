"use client";

import { useEffect, useRef, useState } from "react";
import { MediaClip } from "@/types/workstation";
import { formatTimecode } from "@/lib/timecode";

interface PreviewMonitorProps {
  activeClip: MediaClip | null;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  aspectRatio: "9:16" | "16:9" | "1:1";
  onSeek: (seconds: number) => void;
  onTogglePlay: () => void;
  onSkipBack?: () => void;
  onSkipForward?: () => void;
}

export function PreviewMonitor({
  activeClip,
  currentTime,
  duration,
  isPlaying,
  aspectRatio,
  onSeek,
  onTogglePlay,
  onSkipBack,
  onSkipForward,
}: PreviewMonitorProps) {
  const [volume, setVolume] = useState(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Sync real HTML video element if clip has source
  useEffect(() => {
    if (videoRef.current && activeClip?.src) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying, activeClip?.src]);

  useEffect(() => {
    if (videoRef.current && activeClip?.src) {
      if (Math.abs(videoRef.current.currentTime - currentTime) > 0.4) {
        videoRef.current.currentTime = currentTime;
      }
    }
  }, [currentTime, activeClip?.src]);

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    onSeek(val);
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  // Format full timecode for monitor (00:18:24 / 00:32:16)
  const formatMonitorTimecode = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(ms).padStart(2, "0")}`;
  };

  return (
    <div
      ref={containerRef}
      className="relative flex flex-1 flex-col overflow-hidden bg-[#050505] select-none"
    >
      {/* Top Overlays */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-1.5">
        <span className="rounded bg-[#0a0d14]/80 px-2 py-0.5 text-[10px] font-mono font-semibold text-[#9ca3af] backdrop-blur-md border border-[#1f2433]">
          4K
        </span>
        <span className="rounded bg-[#0a0d14]/80 px-2 py-0.5 text-[10px] font-mono font-semibold text-[#9ca3af] backdrop-blur-md border border-[#1f2433]">
          60 FPS
        </span>
        <span className="rounded bg-[#0a0d14]/80 px-2 py-0.5 text-[10px] font-mono font-semibold text-[#9ca3af] backdrop-blur-md border border-[#1f2433]">
          HDR
        </span>
      </div>

      {/* Main Preview Canvas Area */}
      <div className="relative flex flex-1 items-center justify-center p-4">
        <div
          className={`relative max-h-full max-w-full overflow-hidden rounded-md border border-[#1f2433] bg-[#0c0f17] shadow-2xl transition-all ${
            aspectRatio === "9:16"
              ? "aspect-[9/16] h-[92%]"
              : aspectRatio === "1:1"
              ? "aspect-square h-[85%]"
              : "aspect-video w-[92%]"
          }`}
        >
          {activeClip?.src ? (
            <video
              ref={videoRef}
              src={activeClip.src}
              className="h-full w-full object-contain"
              onTimeUpdate={() => {
                if (videoRef.current) {
                  onSeek(videoRef.current.currentTime);
                }
              }}
            />
          ) : (
            /* Animated Cinematic Mockup Canvas representing the reference */
            <div className="relative flex h-full w-full flex-col items-center justify-center bg-gradient-to-t from-[#0a0c10] via-[#161a26] to-[#0a0c10] p-6 text-center">
              {/* Silhouette and cinematic warm neon glow */}
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,230,0,0.12)_0%,transparent_70%)]" />

              {/* Graphic elements */}
              <div className="relative z-10 flex flex-col items-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-[#ffe600]/40 bg-[#141724] text-[#ffe600] shadow-[0_0_20px_rgba(255,230,0,0.25)]">
                  {isPlaying ? (
                    <svg className="h-8 w-8 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                    </svg>
                  ) : (
                    <svg className="h-8 w-8 ml-1" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  )}
                </div>

                <p className="font-mono text-sm font-bold tracking-wide text-[#ffffff]">
                  {activeClip ? activeClip.title : "No Clip Selected"}
                </p>

                <p className="mt-1 text-xs text-[#9ca3af]">
                  {activeClip
                    ? `${activeClip.resolution || "4K"} • ${formatTimecode(currentTime)} / ${formatTimecode(duration)}`
                    : "Select a clip from Project Media or import video"}
                </p>

                {/* Subtle timecode watermark overlay */}
                <div className="mt-4 rounded bg-[#000000]/60 px-3 py-1 font-mono text-xs font-semibold text-[#ffe600] border border-[#202532]">
                  TC: {formatMonitorTimecode(currentTime)}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scrubber / Seekbar (Full Width with Bright Yellow Progress) */}
      <div className="relative w-full px-4 pt-1">
        <div className="relative flex h-2 w-full items-center">
          {/* Progress bar background */}
          <div className="absolute inset-0 rounded-full bg-[#1a1f2c]">
            {/* Bright yellow filled elapsed bar */}
            <div
              className="h-full rounded-full bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.6)]"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Interactive Range Input */}
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeekChange}
            aria-label="Video playback scrubber"
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          />

          {/* Scrubber Playhead Thumb */}
          <div
            className="pointer-events-none absolute h-3.5 w-3.5 -translate-x-1/2 rounded-full border-2 border-[#000000] bg-[#ffe600] shadow-md"
            style={{ left: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Bottom Transport Controls Bar */}
      <div className="flex h-12 w-full items-center justify-between border-t border-[#1f2433] bg-[#0a0c10] px-4">
        {/* Left: Timecode readout */}
        <div className="flex items-center gap-1 font-mono text-xs">
          <span className="font-bold text-[#ffffff]">
            {formatMonitorTimecode(currentTime)}
          </span>
          <span className="text-[#64748b]">/</span>
          <span className="text-[#9ca3af]">
            {formatMonitorTimecode(duration)}
          </span>
        </div>

        {/* Center: Transport buttons */}
        <div className="flex items-center gap-4 text-[#ffffff]">
          {/* Skip Back */}
          <button
            type="button"
            onClick={onSkipBack}
            title="Previous scene / start"
            className="rounded p-1 text-[#9ca3af] transition-colors hover:text-[#ffffff]"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>

          {/* Play / Pause Toggle */}
          <button
            type="button"
            onClick={onTogglePlay}
            title={isPlaying ? "Pause (Space)" : "Play (Space)"}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[#ffffff] text-[#000000] transition-transform hover:scale-105 active:scale-95"
          >
            {isPlaying ? (
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            ) : (
              <svg className="h-4 w-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          {/* Skip Forward */}
          <button
            type="button"
            onClick={onSkipForward}
            title="Next scene / end"
            className="rounded p-1 text-[#9ca3af] transition-colors hover:text-[#ffffff]"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>
        </div>

        {/* Right: Volume & Monitor controls */}
        <div className="flex items-center gap-3">
          {/* Volume control */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setIsMuted(!isMuted)}
              title={isMuted ? "Unmute" : "Mute"}
              className="text-[#9ca3af] hover:text-[#ffffff]"
            >
              {isMuted || volume === 0 ? (
                <svg className="h-4 w-4 text-[#ef4444]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
              )}
            </button>

            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={(e) => {
                setVolume(parseFloat(e.target.value));
                setIsMuted(false);
              }}
              aria-label="Volume level"
              className="h-1 w-14 cursor-pointer accent-[#ffe600]"
            />
          </div>

          {/* Fullscreen button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            aria-pressed={isFullscreen}
            title={isFullscreen ? "Exit fullscreen monitor" : "Toggle fullscreen monitor"}
            className="text-[#9ca3af] hover:text-[#ffffff]"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
