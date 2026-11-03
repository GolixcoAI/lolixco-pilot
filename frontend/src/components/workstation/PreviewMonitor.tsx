"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { MediaClip } from "@/types/workstation";

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
  onSwitchToProxy?: () => void;
  isProxyActive?: boolean;
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
  const [playbackSpeed, setPlaybackSpeed] = useState("1.0x");
  const [resolution, setResolution] = useState("1080p");
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

  const totalDuration = duration > 0 ? duration : 30.18;
  const progressPercent = Math.min(100, Math.max(0, (currentTime / totalDuration) * 100));

  // SMPTE 30fps timecode formatter: 00:00:12:14
  const formatSMPTETimecode = (sec: number) => {
    const totalFrames = Math.floor(sec * 30);
    const frames = totalFrames % 30;
    const s = Math.floor(sec % 60);
    const m = Math.floor((sec / 60) % 60);
    const h = Math.floor(sec / 3600);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(frames).padStart(2, "0")}`;
  };

  // Determine current frame image based on currentTime
  const getDynamicFrameImage = () => {
    if (currentTime < 4.0) return "/frames/gojo/frame_00_000.5s.png";
    if (currentTime < 9.0) return "/frames/gojo/frame_01_006.0s.png";
    if (currentTime < 14.0) return "/frames/gojo/frame_02_012.0s.png";
    if (currentTime < 18.0) return "/frames/gojo/frame_04_024.0s.png";
    if (currentTime < 23.0) return "/frames/gojo/frame_08_044.0s.png";
    return "/frames/gojo/frame_10_058.0s.png";
  };

  return (
    <div
      ref={containerRef}
      className="relative flex flex-1 flex-col overflow-hidden bg-[#050608] select-none"
    >
      {/* Top Monitor Header: Program Selector */}
      <div className="absolute top-3 left-3.5 z-20">
        <div className="flex items-center gap-1.5 rounded border border-[#1f2433] bg-[#0c0e15]/90 px-2.5 py-1 text-[11px] font-semibold text-[#f3f4f6] backdrop-blur-md">
          <span>Program: Final Edit</span>
          <svg className="h-3 w-3 text-[#9ca3af]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Main Video Viewport */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden p-2">
        <div
          className={`relative flex items-center justify-center overflow-hidden rounded bg-[#000000] shadow-2xl transition-all ${
            aspectRatio === "9:16"
              ? "h-full max-h-[88%] aspect-[9/16]"
              : aspectRatio === "1:1"
              ? "h-full max-h-[88%] aspect-square"
              : "w-full max-w-[94%] aspect-video"
          }`}
        >
          {activeClip?.src ? (
            <video
              ref={videoRef}
              src={activeClip.src}
              className="h-full w-full object-contain"
              playsInline
              muted={volume === 0}
            />
          ) : (
            <div className="relative h-full w-full">
              <Image
                src={getDynamicFrameImage()}
                alt="Program Monitor"
                fill
                priority
                className="object-cover"
              />
            </div>
          )}
        </div>
      </div>

      {/* Scrubber Bar directly above player controls */}
      <div
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const clickX = e.clientX - rect.left;
          const ratio = Math.max(0, Math.min(1, clickX / rect.width));
          onSeek(ratio * totalDuration);
        }}
        className="group relative h-1.5 w-full cursor-pointer bg-[#141722]"
      >
        {/* Yellow Progress Fill */}
        <div
          className="h-full bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.6)]"
          style={{ width: `${progressPercent}%` }}
        />

        {/* Scene Cut Markers */}
        {[0, 4.0, 9.0, 14.0, 18.0, 23.0, 30.18].map((sec) => {
          const leftPct = (sec / totalDuration) * 100;
          return (
            <span
              key={sec}
              className="absolute top-0 h-full w-[2px] bg-[#000000]/60 pointer-events-none"
              style={{ left: `${leftPct}%` }}
            />
          );
        })}

        {/* Scrub Handle */}
        <div
          className="absolute top-1/2 -mt-1.5 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-[#000000] bg-[#ffe600] opacity-0 transition-opacity group-hover:opacity-100"
          style={{ left: `${progressPercent}%` }}
        />
      </div>

      {/* Bottom Player Control Bar */}
      <div className="flex h-10 w-full shrink-0 items-center justify-between border-t border-[#1f2433] bg-[#08090c] px-4 text-[#d1d5db]">
        {/* Left: Accurate Yellow SMPTE Timecode */}
        <div className="flex items-center gap-1.5 font-mono text-xs">
          <span className="font-bold text-[#ffe600]">
            {formatSMPTETimecode(currentTime)}
          </span>
          <span className="text-[#64748b]">/</span>
          <span className="text-[#9ca3af]">
            {formatSMPTETimecode(totalDuration)}
          </span>
        </div>

        {/* Center: Frame Stepping & Playback Controls */}
        <div className="flex items-center gap-1">
          {/* Previous Edit / Frame */}
          <button
            type="button"
            onClick={() => onSeek(Math.max(0, currentTime - 1.0))}
            title="Previous Frame"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>

          {/* Step Back (1 frame = ~0.033s) */}
          <button
            type="button"
            onClick={() => onSeek(Math.max(0, currentTime - 0.033))}
            title="Step Back 1 Frame"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
              <path d="M19 12L5 5v14l14-7z" transform="rotate(180 12 12)" />
            </svg>
          </button>

          {/* Play / Pause (Center) */}
          <button
            type="button"
            onClick={onTogglePlay}
            title={isPlaying ? "Pause (Space)" : "Play (Space)"}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffe600]"
          >
            {isPlaying ? (
              <svg className="h-3.5 w-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
              </svg>
            ) : (
              <svg className="h-3.5 w-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          {/* Step Forward (1 frame = ~0.033s) */}
          <button
            type="button"
            onClick={() => onSeek(Math.min(totalDuration, currentTime + 0.033))}
            title="Step Forward 1 Frame"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
              <path d="M19 12L5 5v14l14-7z" />
            </svg>
          </button>

          {/* Next Edit / Frame */}
          <button
            type="button"
            onClick={() => onSeek(Math.min(totalDuration, currentTime + 1.0))}
            title="Next Frame"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Right: Volume, Speed, Resolution, Fit, Fullscreen */}
        <div className="flex items-center gap-2.5 text-xs text-[#9ca3af]">
          {/* Volume slider */}
          <div className="flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            </svg>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              aria-label="Volume slider"
              className="h-1 w-14 cursor-pointer appearance-none rounded-full bg-[#1f2433] accent-[#ffe600]"
            />
          </div>

          {/* Speed Selector */}
          <div className="relative">
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(e.target.value)}
              aria-label="Playback speed"
              className="cursor-pointer appearance-none rounded border border-[#1f2433] bg-[#11141e] py-0.5 pl-2 pr-5 text-[11px] font-mono text-[#f3f4f6] focus:border-[#ffe600] focus:outline-none"
            >
              <option value="0.5x">0.5x</option>
              <option value="1.0x">1.0x</option>
              <option value="1.5x">1.5x</option>
              <option value="2.0x">2.0x</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-1 text-[#9ca3af]">
              <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Resolution Selector */}
          <div className="relative">
            <select
              value={resolution}
              onChange={(e) => setResolution(e.target.value)}
              aria-label="Display resolution"
              className="cursor-pointer appearance-none rounded border border-[#1f2433] bg-[#11141e] py-0.5 pl-2 pr-5 text-[11px] font-mono text-[#f3f4f6] focus:border-[#ffe600] focus:outline-none"
            >
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="Proxy">Proxy</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-1 text-[#9ca3af]">
              <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Fullscreen button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            className="flex h-6 w-6 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
