"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
import {
  AIProviderName,
  AudioIntelligenceData,
  CreativeBriefState,
  KeyMoment,
  MediaClip,
  MomentTag,
  SourceIdentificationData,
  UsageMetadataData,
  UserFeedbackData,
} from "@/types/workstation";
import { ExportModal } from "@/components/workstation/ExportModal";
import {
  analyzeMedia,
  confirmUpload,
  deleteMedia,
  getAudioAnalysis,
  getLatestAnalysis,
  getOrCreateProject,
  getProxyPlaybackUrl,
  listProjectMedia,
  requestPresignedUpload,
  submitAnalysisFeedback,
  uploadFileToS3,
} from "@/lib/mediaApi";
import { formatTimecode } from "@/lib/timecode";

export default function WorkstationPage() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("Untitled Cut");
  const [aspectRatio, setAspectRatio] = useState<"9:16" | "16:9" | "1:1">("9:16");
  const [activeTab, setActiveTab] = useState<NavTab>("editpilot");

  // Media and playback state
  const [clips, setClips] = useState<MediaClip[]>(INITIAL_DEMO_CLIPS);
  const [activeClipId, setActiveClipId] = useState<string | null>("clip-1");
  const [currentTime, setCurrentTime] = useState(18.4);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Creative Director state
  const [brief, setBrief] = useState<CreativeBriefState>(INITIAL_BRIEF);
  const [moments, setMoments] = useState<KeyMoment[]>(INITIAL_KEY_MOMENTS);
  const [activeMomentId, setActiveMomentId] = useState<string | null>("moment-3");
  const [aiSuggestions] = useState<string[]>(INITIAL_AI_SUGGESTIONS);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Multimodal Media Intelligence & Provider state
  const [selectedProvider, setSelectedProvider] = useState<AIProviderName>("baseten");
  const [sourceIntelligence, setSourceIntelligence] =
    useState<SourceIdentificationData | null>(null);
  const [audioIntelligence, setAudioIntelligence] =
    useState<AudioIntelligenceData | null>(null);
  const [usageMetadata, setUsageMetadata] = useState<UsageMetadataData | null>(null);
  const [userFeedback, setUserFeedback] = useState<UserFeedbackData | null>(null);
  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(null);

  // Modal dialog state
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Audio beat markers and proxy playback states
  const [beatTimestamps, setBeatTimestamps] = useState<number[]>([12.8, 19.6, 28.0, 35.0, 48.0]);
  const [isProxyActive, setIsProxyActive] = useState(false);
  const originalSrcRef = useRef<{ [key: string]: string }>({});

  // Find currently active clip
  const activeClip = clips.find((c) => c.id === activeClipId) || clips[0] || null;
  const clipDuration = activeClip ? activeClip.duration : 32.16;

  // Playback timer ticker for preview
  const animFrameRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);

  // Fetch or create project and restore saved media assets on mount
  useEffect(() => {
    let mounted = true;

    async function initProject() {
      try {
        const project = await getOrCreateProject();
        if (!mounted) return;
        setProjectId(project.id);
        if (project.name) setProjectName(project.name);

        // Fetch user's persistent media assets
        const mediaItems = await listProjectMedia(project.id);
        if (!mounted) return;

        if (mediaItems.length > 0) {
          const loadedClips: MediaClip[] = mediaItems.map((item) => ({
            id: item.id,
            title: item.original_filename,
            type: "video",
            duration: item.duration_seconds || 30,
            size: `${(((item.verified_size_bytes || item.declared_size_bytes) / (1024 * 1024)) || 0).toFixed(1)} MB`,
            resolution: "HD",
            src: item.preview_url || undefined,
            status: item.status,
            expiresAt: item.expires_at,
            isRealUpload: true,
          }));

          setClips(loadedClips);
          setActiveClipId(loadedClips[0].id);
          setCurrentTime(0);
        }
      } catch (err) {
        console.warn("Could not load backend project, using local workstation baseline:", err);
      }
    }

    initProject();
    return () => {
      mounted = false;
    };
  }, []);

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

  // Import local custom video and perform real S3 upload
  const handleImportCustomVideo = async (file: File) => {
    setUploadError(null);

    // Client-side pre-validation
    const MAX_BYTES = 104857600; // 100 MB
    if (file.size > MAX_BYTES) {
      setUploadError(`File "${file.name}" exceeds 100 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["mp4", "mov", "webm"].includes(ext)) {
      setUploadError("Unsupported format. Please upload MP4, MOV, or WebM video.");
      return;
    }

    // Temporary local preview URL for immediate responsive feedback
    const localBlobUrl = URL.createObjectURL(file);
    const tempMediaId = `upload-${Date.now()}`;

    // Optimistically add clip to media bin
    const optimisticClip: MediaClip = {
      id: tempMediaId,
      title: file.name,
      type: "video",
      duration: 30,
      size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
      resolution: "HD",
      src: localBlobUrl,
      isRealUpload: true,
      status: "pending",
      uploadProgress: 0,
    };

    setClips((prev) => [optimisticClip, ...prev.filter((c) => c.id !== tempMediaId)]);
    setActiveClipId(tempMediaId);
    setCurrentTime(0);
    setIsPlaying(false);
    setIsUploading(true);

    try {
      // 1. Ensure project exists
      let currentProjId = projectId;
      if (!currentProjId) {
        const project = await getOrCreateProject();
        currentProjId = project.id;
        setProjectId(project.id);
      }

      // 2. Request presigned upload URL from backend
      const presign = await requestPresignedUpload(
        currentProjId,
        file.name,
        file.type || "video/mp4",
        file.size,
      );

      // 3. Direct upload to S3 with honest progress updates
      await uploadFileToS3(
        presign.upload_url,
        file,
        file.type || "video/mp4",
        (percent) => {
          setClips((prev) =>
            prev.map((c) => (c.id === tempMediaId ? { ...c, uploadProgress: percent } : c)),
          );
        },
      );

      // 4. Measure video duration if possible
      let videoDuration: number | undefined;
      try {
        const tempVideo = document.createElement("video");
        tempVideo.preload = "metadata";
        tempVideo.src = localBlobUrl;
        await new Promise((res) => {
          tempVideo.onloadedmetadata = () => {
            videoDuration = tempVideo.duration;
            res(true);
          };
          tempVideo.onerror = () => res(false);
        });
      } catch {
        // Fallback to default
      }

      // 5. Confirm upload with backend
      const confirmed = await confirmUpload(
        currentProjId,
        presign.media_id,
        videoDuration,
      );

      // 6. Update clip in state with verified S3 preview URL
      const verifiedClip: MediaClip = {
        id: confirmed.id,
        title: confirmed.original_filename,
        type: "video",
        duration: confirmed.duration_seconds || videoDuration || 30,
        size: `${(((confirmed.verified_size_bytes || file.size) / (1024 * 1024)) || 0).toFixed(1)} MB`,
        resolution: "HD",
        src: confirmed.preview_url || localBlobUrl,
        isRealUpload: true,
        status: "verified",
        expiresAt: confirmed.expires_at,
        uploadProgress: 100,
      };

      setClips((prev) =>
        prev.map((c) => (c.id === tempMediaId ? verifiedClip : c)),
      );
      setActiveClipId(verifiedClip.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Video upload failed";
      console.error("Upload error:", err);
      setUploadError(msg);

      setClips((prev) =>
        prev.map((c) => (c.id === tempMediaId ? { ...c, status: "failed", errorMessage: msg } : c)),
      );
    } finally {
      setIsUploading(false);
    }
  };

  // Delete media asset
  const handleDeleteClip = useCallback(
    async (clipId: string) => {
      const clipToDelete = clips.find((c) => c.id === clipId);
      if (!clipToDelete) return;

      // If it is a real uploaded asset on server
      if (clipToDelete.isRealUpload && projectId && !clipId.startsWith("upload-")) {
        try {
          await deleteMedia(projectId, clipId);
        } catch (err) {
          console.warn("Failed to delete media on backend:", err);
        }
      }

      // Remove from client state
      setClips((prev) => {
        const next = prev.filter((c) => c.id !== clipId);
        if (activeClipId === clipId) {
          const nextActive = next[0] ? next[0].id : null;
          setActiveClipId(nextActive);
          setCurrentTime(0);
          setIsPlaying(false);
        }
        return next;
      });
    },
    [clips, projectId, activeClipId],
  );

  // Video understanding blueprint generation with Baseten/Meta or local mock fallback
  const handleGenerateBlueprint = async (
    confirmedConsent: boolean,
    provider?: AIProviderName,
  ) => {
    const activeProvider = provider || selectedProvider;
    if (!confirmedConsent) {
      setAnalysisError(
        `User authorization required: please authorize ${activeProvider === "meta" ? "Meta AI" : "Baseten"} model analysis.`,
      );
      return;
    }

    setAnalysisError(null);
    setIsGenerating(true);
    setGenerationStage("Preparing footage...");

    try {
      if (activeClip?.isRealUpload && projectId && activeClipId && !activeClipId.startsWith("upload-")) {
        setGenerationStage(
          activeProvider === "meta"
            ? "Understanding scenes with Meta AI (muse-spark-1.3)..."
            : "Understanding scenes with Baseten (muse-spark-open)...",
        );
        const res = await analyzeMedia(
          projectId,
          activeClipId,
          brief,
          confirmedConsent,
          activeProvider,
        );

        setActiveAnalysisId(res.id);
        setSourceIntelligence(res.source_identification || null);
        setAudioIntelligence(res.audio_intelligence || null);
        setUsageMetadata(res.usage_metadata || null);
        setUserFeedback(res.user_feedback || null);

        setGenerationStage("Building blueprint...");
        if (res.blueprint && res.blueprint.scenes) {
          const mappedMoments: KeyMoment[] = res.blueprint.scenes.map((scene, idx) => {
            const tag: MomentTag =
              idx === 0 ? "HOOK" : idx === 1 ? "BUILD" : idx === 2 ? "CLIMAX" : "RESOLVE";
            return {
              id: scene.id,
              index: idx + 1,
              timecode: formatTimecode(scene.start_seconds),
              seconds: scene.start_seconds,
              endSeconds: scene.end_seconds,
              tag,
              title: scene.moment,
              description: scene.why_it_works,
              action: scene.editing_direction,
            };
          });

          setMoments(mappedMoments);
          if (mappedMoments.length > 0) {
            setActiveMomentId(mappedMoments[0].id);
            setCurrentTime(mappedMoments[0].seconds);
          }
        }
      } else {
        // Fallback demo/sample footage simulation
        await new Promise((res) => setTimeout(res, 400));
        setGenerationStage("Understanding scenes...");
        await new Promise((res) => setTimeout(res, 500));
        setGenerationStage("Building blueprint...");
        await new Promise((res) => setTimeout(res, 300));
        setMoments([...INITIAL_KEY_MOMENTS]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Video analysis failed";
      console.error("Blueprint generation error:", err);
      setAnalysisError(msg);
    } finally {
      setIsGenerating(false);
      setGenerationStage(null);
    }
  };

  const handleFeedbackSubmit = async (feedback: {
    confirmed_by_user: boolean;
    corrected_source_title?: string | null;
    corrected_song_title?: string | null;
    notes?: string | null;
  }) => {
    if (!projectId || !activeClipId || activeClipId.startsWith("upload-")) return;
    try {
      const res = await submitAnalysisFeedback(
        projectId,
        activeClipId,
        feedback,
        activeAnalysisId || undefined,
      );
      setUserFeedback(res.user_feedback || null);
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    }
  };

  // Restore latest persistent analysis when active clip changes
  useEffect(() => {
    let isCurrent = true;
    if (activeClip?.isRealUpload && projectId && activeClipId && !activeClipId.startsWith("upload-")) {
      getLatestAnalysis(projectId, activeClipId)
        .then((latest) => {
          if (!isCurrent) return;
          if (latest) {
            setActiveAnalysisId(latest.id);
            setSourceIntelligence(latest.source_identification || null);
            setAudioIntelligence(latest.audio_intelligence || null);
            setUsageMetadata(latest.usage_metadata || null);
            setUserFeedback(latest.user_feedback || null);
          } else {
            setActiveAnalysisId(null);
            setSourceIntelligence(null);
            setAudioIntelligence(null);
            setUsageMetadata(null);
            setUserFeedback(null);
          }
        })
        .catch(() => {
          // Safe non-blocking fallback if no previous analysis
        });
    } else {
      const timer = setTimeout(() => {
        if (!isCurrent) return;
        setActiveAnalysisId(null);
        setSourceIntelligence(null);
        setAudioIntelligence(null);
        setUsageMetadata(null);
        setUserFeedback(null);
      }, 0);
      return () => {
        isCurrent = false;
        clearTimeout(timer);
      };
    }
    return () => {
      isCurrent = false;
    };
  }, [activeClipId, activeClip?.isRealUpload, projectId]);

  // Fetch audio beat timestamps when active clip changes
  useEffect(() => {
    let active = true;
    if (activeClip?.isRealUpload && projectId && activeClipId && !activeClipId.startsWith("upload-")) {
      getAudioAnalysis(projectId, activeClipId)
        .then((analysis) => {
          if (!active) return;
          if (analysis?.beat_timestamps && analysis.beat_timestamps.length > 0) {
            setBeatTimestamps(analysis.beat_timestamps);
          }
        })
        .catch(() => {
          // Graceful fallback to default beat points
        });
    }
    return () => {
      active = false;
    };
  }, [activeClipId, activeClip?.isRealUpload, projectId]);

  // Toggle browser-compatible H.264 preview proxy vs original source
  const handleSwitchToProxy = async () => {
    if (!activeClip || !projectId || !activeClipId || activeClipId.startsWith("upload-")) return;

    if (isProxyActive) {
      const originalSrc = originalSrcRef.current[activeClipId];
      if (originalSrc) {
        setClips((prev) =>
          prev.map((c) => (c.id === activeClipId ? { ...c, src: originalSrc } : c)),
        );
      }
      setIsProxyActive(false);
      return;
    }

    try {
      if (activeClip.src && !originalSrcRef.current[activeClipId]) {
        originalSrcRef.current[activeClipId] = activeClip.src;
      }
      const proxyUrl = await getProxyPlaybackUrl(projectId, activeClipId);
      setClips((prev) =>
        prev.map((c) => (c.id === activeClipId ? { ...c, src: proxyUrl } : c)),
      );
      setIsProxyActive(true);
    } catch (err) {
      console.warn("Could not load H.264 proxy, keeping source:", err);
    }
  };

  // Load rendered FFmpeg export cut into preview monitor
  const handleLoadRenderedCut = (cutUrl: string, duration: number) => {
    const exportClipId = `export-${Date.now()}`;
    const exportClip: MediaClip = {
      id: exportClipId,
      title: `${projectName} - Exported Cut (${duration.toFixed(1)}s)`,
      type: "video",
      duration,
      size: "22.4 MB",
      resolution: "1080p",
      src: cutUrl,
      isRealUpload: false,
      status: "verified",
    };
    setClips((prev) => [exportClip, ...prev]);
    setActiveClipId(exportClipId);
    setCurrentTime(0);
    setIsPlaying(true);
    setIsExportModalOpen(false);
  };

  // Apply AI Director generated blueprint scenes directly to timeline
  const handleApplyBlueprint = (blueprint: Record<string, unknown>) => {
    const rawScenes = blueprint?.scenes;
    if (Array.isArray(rawScenes)) {
      const mappedMoments: KeyMoment[] = rawScenes.map((rawScene: unknown, idx: number) => {
        const scene = rawScene as {
          id?: string;
          start_seconds?: number;
          end_seconds?: number;
          moment?: string;
          why_it_works?: string;
          editing_direction?: string;
        };
        const startSec = typeof scene.start_seconds === "number" ? scene.start_seconds : 0;
        const tag: MomentTag =
          idx === 0 ? "HOOK" : idx === 1 ? "BUILD" : idx === 2 ? "CLIMAX" : "RESOLVE";
        return {
          id: scene.id || `scene-${idx + 1}`,
          index: idx + 1,
          timecode: formatTimecode(startSec),
          seconds: startSec,
          endSeconds: scene.end_seconds,
          tag,
          title: scene.moment || `Scene ${idx + 1}`,
          description: scene.why_it_works || "",
          action: scene.editing_direction || "",
        };
      });
      setMoments(mappedMoments);
      if (mappedMoments.length > 0) {
        setActiveMomentId(mappedMoments[0].id);
        setCurrentTime(mappedMoments[0].seconds);
      }
    }
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
        onOpenExport={() => setIsExportModalOpen(true)}
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
          onDeleteClip={handleDeleteClip}
          isUploading={isUploading}
          uploadError={uploadError}
          onDismissError={() => setUploadError(null)}
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
          onSwitchToProxy={handleSwitchToProxy}
          isProxyActive={isProxyActive}
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
          generationStage={generationStage}
          analysisError={analysisError}
          onDismissError={() => setAnalysisError(null)}
          selectedProvider={selectedProvider}
          onSelectProvider={setSelectedProvider}
          sourceIntelligence={sourceIntelligence}
          audioIntelligence={audioIntelligence}
          usageMetadata={usageMetadata}
          userFeedback={userFeedback}
          onFeedbackSubmit={handleFeedbackSubmit}
          hasUploadedVideo={Boolean(activeClip?.isRealUpload)}
          projectId={projectId}
          activeClipId={activeClipId}
          activeClipTitle={activeClip?.title}
          onApplyBlueprint={handleApplyBlueprint}
        />
      </div>

      {/* Bottom Horizontal Timeline */}
      <Timeline
        currentTime={currentTime}
        duration={clipDuration}
        moments={moments}
        activeClip={activeClip}
        onSeek={(sec) => setCurrentTime(sec)}
        beatTimestamps={beatTimestamps}
      />

      {/* Privacy and Policy Modal */}
      <PrivacyModal
        isOpen={isPrivacyModalOpen}
        onClose={() => setIsPrivacyModalOpen(false)}
      />

      {/* Real FFmpeg S3 Video Export Modal */}
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        projectId={projectId}
        mediaId={activeClipId}
        projectName={projectName}
        defaultSegments={
          moments.length > 0
            ? moments.map((m) => ({
                start_seconds: m.seconds,
                end_seconds:
                  m.endSeconds !== undefined
                    ? m.endSeconds
                    : Math.min(clipDuration, m.seconds + 5.0),
                title: m.title,
              }))
            : undefined
        }
        onLoadRenderedCut={handleLoadRenderedCut}
      />
    </div>
  );
}
