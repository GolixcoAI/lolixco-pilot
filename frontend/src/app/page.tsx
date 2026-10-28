"use client";

import { useEffect, useRef, useState } from "react";
import { TopCommandBar } from "@/components/workstation/TopCommandBar";
import { NavRail, NavTab } from "@/components/workstation/NavRail";
import { MediaBin } from "@/components/workstation/MediaBin";
import { PreviewMonitor } from "@/components/workstation/PreviewMonitor";
import { AiDirectorPanel } from "@/components/workstation/AiDirectorPanel";
import { Timeline } from "@/components/workstation/Timeline";
import { PrivacyModal } from "@/components/workstation/PrivacyModal";
import {
  INITIAL_AI_SUGGESTIONS,
  INITIAL_BRIEF,
  INITIAL_DEMO_CLIPS,
  INITIAL_KEY_MOMENTS,
} from "@/lib/mockData";
import { CreativeBriefState, KeyMoment, MediaClip } from "@/types/workstation";

export default function WorkstationPage() {
  const [projectName, setProjectName] = useState("Midnight Sequence");
  const [aspectRatio, setAspectRatio] = useState<"9:16" | "16:9" | "1:1">("9:16");
  const [activeTab, setActiveTab] = useState<NavTab>("editpilot");

  // Media and playback state
  const [clips, setClips] = useState<MediaClip[]>(INITIAL_DEMO_CLIPS);
  const [activeClipId, setActiveClipId] = useState<string | null>("clip-1");
  const [currentTime, setCurrentTime] = useState(18.4); // Matches 00:18:24 playhead in reference mockup
  const [isPlaying, setIsPlaying] = useState(false);

  // Creative Director state
  const [brief, setBrief] = useState<CreativeBriefState>(INITIAL_BRIEF);
  const [moments, setMoments] = useState<KeyMoment[]>(INITIAL_KEY_MOMENTS);
  const [activeMomentId, setActiveMomentId] = useState<string | null>("moment-3");
  const [aiSuggestions] = useState<string[]>(INITIAL_AI_SUGGESTIONS);
  const [isGenerating, setIsGenerating] = useState(false);

  // Modal dialog state
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);

  // Find currently active clip
  const activeClip = clips.find((c) => c.id === activeClipId) || clips[0] || null;
  const clipDuration = activeClip ? activeClip.duration : 32.16;

  // Playback timer ticker for preview
  const animFrameRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);

  useEffect(() => {
    if (!isPlaying) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    lastTickRef.current = performance.now();

    const tick = (now: number) => {
      const delta = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;

      setCurrentTime((prev) => {
        const next = prev + delta;
        if (next >= clipDuration) {
          setIsPlaying(false);
          return clipDuration;
        }
        return next;
      });

      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, clipDuration]);

  // Spacebar toggle playback shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setIsPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Moment seek action
  const handleJumpToMoment = (seconds: number, momentId: string) => {
    setCurrentTime(seconds);
    setActiveMomentId(momentId);
  };

  // Import local custom video
  const handleImportCustomVideo = (file: File) => {
    const objectUrl = URL.createObjectURL(file);
    const newClip: MediaClip = {
      id: `custom-${Date.now()}`,
      title: file.name,
      type: "video",
      duration: 30, // Default until metadata loads
      size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
      resolution: "Custom",
      src: objectUrl,
      isCustom: true,
    };

    setClips((prev) => [newClip, ...prev]);
    setActiveClipId(newClip.id);
    setCurrentTime(0);
    setIsPlaying(false);
  };

  // Mock blueprint generation animation
  const handleGenerateBlueprint = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      // Re-order or refresh moments to show dynamic response
      setMoments([...INITIAL_KEY_MOMENTS]);
    }, 1200);
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#050505] text-[#ffffff] font-sans">
      {/* Top Command Bar */}
      <TopCommandBar
        projectName={projectName}
        setProjectName={setProjectName}
        aspectRatio={aspectRatio}
        setAspectRatio={setAspectRatio}
        onOpenPrivacyNotice={() => setIsPrivacyModalOpen(true)}
      />

      {/* Center Workstation: Left Rail + Media Bin + Preview Monitor + AI Director */}
      <div className="flex flex-1 overflow-hidden">
        {/* Navigation Rail */}
        <NavRail
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onOpenPrivacyNotice={() => setIsPrivacyModalOpen(true)}
        />

        {/* Media Bin Dock */}
        <MediaBin
          clips={clips}
          activeClipId={activeClipId}
          onSelectClip={(clip) => {
            setActiveClipId(clip.id);
            setCurrentTime(0);
            setIsPlaying(false);
          }}
          onImportCustomVideo={handleImportCustomVideo}
        />

        {/* Central Preview Monitor */}
        <PreviewMonitor
          activeClip={activeClip}
          currentTime={currentTime}
          duration={clipDuration}
          isPlaying={isPlaying}
          aspectRatio={aspectRatio}
          onSeek={(sec) => setCurrentTime(sec)}
          onTogglePlay={() => setIsPlaying((p) => !p)}
          onSkipBack={() => setCurrentTime(0)}
          onSkipForward={() => setCurrentTime(clipDuration)}
        />

        {/* Right AI Director Panel */}
        <AiDirectorPanel
          brief={brief}
          setBrief={setBrief}
          moments={moments}
          aiSuggestions={aiSuggestions}
          activeMomentId={activeMomentId}
          onJumpToMoment={handleJumpToMoment}
          onGenerateBlueprint={handleGenerateBlueprint}
          isGenerating={isGenerating}
        />
      </div>

      {/* Bottom Horizontal Timeline */}
      <Timeline
        currentTime={currentTime}
        duration={clipDuration}
        moments={moments}
        activeClip={activeClip}
        onSeek={(sec) => setCurrentTime(sec)}
      />

      {/* Privacy and Policy Modal */}
      <PrivacyModal
        isOpen={isPrivacyModalOpen}
        onClose={() => setIsPrivacyModalOpen(false)}
      />
    </div>
  );
}
