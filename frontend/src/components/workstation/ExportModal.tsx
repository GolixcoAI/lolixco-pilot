"use client";

import { useState } from "react";
import { ExportCutResponse, ExportSegmentRequest, renderExportCut } from "@/lib/mediaApi";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string | null;
  mediaId: string | null;
  projectName: string;
  defaultSegments?: ExportSegmentRequest[];
  textOverlays?: Array<{
    text: string;
    color?: string;
    start_seconds: number;
    end_seconds: number;
  }>;
  onLoadRenderedCut?: (cutUrl: string, duration: number) => void;
}

export function ExportModal({
  isOpen,
  onClose,
  projectId,
  mediaId,
  projectName,
  defaultSegments = [
    { start_seconds: 18.0, end_seconds: 24.0, title: "Scene 1: Incantation Hook" },
    { start_seconds: 26.0, end_seconds: 31.0, title: "Scene 2: Red/Blue Convergence" },
    { start_seconds: 34.0, end_seconds: 41.0, title: "Scene 3: Peak Discharge" },
    { start_seconds: 44.0, end_seconds: 50.0, title: "Scene 4: Target Impact & Aftermath" },
  ],
  textOverlays = [],
  onLoadRenderedCut,
}: ExportModalProps) {
  const [resolution, setResolution] = useState<"1080p" | "720p">("1080p");
  const [includeAudio, setIncludeAudio] = useState(true);
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<ExportCutResponse | null>(null);

  if (!isOpen) return null;

  const totalCutDuration = defaultSegments.reduce(
    (acc, seg) => acc + (seg.end_seconds - seg.start_seconds),
    0,
  );

  const handleStartExport = async () => {
    if (!projectId || !mediaId) {
      setRenderError("Please select a verified media asset in the project bin before exporting.");
      return;
    }

    setIsRendering(true);
    setRenderError(null);
    setRenderProgress(15);

    const progressTimer = setInterval(() => {
      setRenderProgress((prev) => Math.min(prev + 12, 90));
    }, 400);

    try {
      const res = await renderExportCut(projectId, {
        media_id: mediaId,
        segments: defaultSegments,
        resolution,
        include_audio: includeAudio,
        text_overlays: textOverlays,
      });
      clearInterval(progressTimer);
      setRenderProgress(100);
      setExportResult(res);
    } catch (err: unknown) {
      clearInterval(progressTimer);
      const msg = err instanceof Error ? err.message : "Failed to render export cut.";
      setRenderError(msg);
    } finally {
      setIsRendering(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#000000]/80 backdrop-blur-sm p-4 select-none">
      <div className="relative w-full max-w-lg rounded-xl border border-[#1f2433] bg-[#0d1017] p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1f2433] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#ffe600] text-xs font-bold text-[#000000]">
              ✂
            </span>
            <h2 className="text-sm font-bold text-[#ffffff] uppercase tracking-wider">
              Export Cut Manifest
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-[#64748b] hover:text-[#ffffff] transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body Content */}
        <div className="mt-4 space-y-4">
          {/* Project & Format Info */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-[#1f2433] bg-[#08090c] p-2.5">
              <span className="block text-[10px] text-[#64748b] uppercase tracking-wider">
                Project Name
              </span>
              <span className="mt-0.5 block truncate text-xs font-bold text-[#ffffff]">
                {projectName}
              </span>
            </div>
            <div className="rounded-lg border border-[#1f2433] bg-[#08090c] p-2.5">
              <span className="block text-[10px] text-[#64748b] uppercase tracking-wider">
                Codec & Container
              </span>
              <span className="mt-0.5 block font-mono text-xs font-bold text-[#ffe600]">
                H.264 / MP4 (AAC Stereo)
              </span>
            </div>
          </div>

          {/* Planned Segments Summary */}
          <div className="rounded-lg border border-[#1f2433] bg-[#08090c] p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#9ca3af]">
                Active Blueprint Segments ({defaultSegments.length})
              </span>
              <span className="font-mono text-xs font-bold text-[#ffe600]">
                {totalCutDuration.toFixed(1)}s Total Cut
              </span>
            </div>

            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {defaultSegments.map((seg, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded bg-[#11141e] px-2.5 py-1.5 text-[11px] border border-[#1f2433]"
                >
                  <span className="text-[#f3f4f6] font-medium">{seg.title || `Cut ${i + 1}`}</span>
                  <span className="font-mono text-[#ffe600]">
                    {seg.start_seconds.toFixed(1)}s → {seg.end_seconds.toFixed(1)}s (
                    {(seg.end_seconds - seg.start_seconds).toFixed(1)}s)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Render Settings */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-[#64748b] mb-1">
                Resolution
              </label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value as "1080p" | "720p")}
                disabled={isRendering}
                className="w-full rounded border border-[#1f2433] bg-[#08090c] p-2 text-xs font-semibold text-[#ffffff] focus:border-[#ffe600] focus:outline-none"
              >
                <option value="1080p">1080p Full HD (2560x1440 Source)</option>
                <option value="720p">720p Mobile Preview</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-wider text-[#64748b] mb-1">
                Audio Pipeline
              </label>
              <label className="flex h-9 items-center gap-2 rounded border border-[#1f2433] bg-[#08090c] px-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeAudio}
                  onChange={(e) => setIncludeAudio(e.target.checked)}
                  disabled={isRendering}
                  className="rounded border-[#1f2433] bg-[#11141e] text-[#ffe600] accent-[#ffe600]"
                />
                <span className="text-xs text-[#f3f4f6]">Preserve AAC Stereo</span>
              </label>
            </div>
          </div>

          {/* Rendering Progress */}
          {isRendering && (
            <div className="space-y-1.5 rounded-lg border border-[#ffe600]/30 bg-[#ffe600]/10 p-3">
              <div className="flex items-center justify-between text-xs font-bold text-[#ffe600]">
                <span>Rendering Cut with FFmpeg Engine...</span>
                <span>{renderProgress}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1f2433]">
                <div
                  className="h-full bg-[#ffe600] transition-all duration-300 shadow-[0_0_8px_rgba(255,230,0,0.8)]"
                  style={{ width: `${renderProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error Message */}
          {renderError && (
            <div className="rounded border border-[#f87171]/40 bg-[#f87171]/10 p-2.5 text-xs text-[#f87171]">
              <strong>Render Failed:</strong> {renderError}
            </div>
          )}

          {/* Success Download Card */}
          {exportResult && (
            <div className="rounded-lg border border-[#4ade80]/40 bg-[#4ade80]/10 p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-[#4ade80]">
                <span>✓</span>
                <span>H.264 Cut Ready for Distribution!</span>
              </div>
              <p className="text-[11px] text-[#9ca3af]">
                Rendered {exportResult.segment_count} segments into a single{" "}
                {exportResult.duration_seconds.toFixed(1)}s MP4 (
                {(exportResult.file_size_bytes / (1024 * 1024)).toFixed(1)} MB).
              </p>
              <div className="flex items-center gap-2 pt-1">
                <a
                  href={exportResult.download_url}
                  download={`cut_${projectName.toLowerCase().replace(/\s+/g, "_")}.mp4`}
                  className="flex-1 rounded bg-[#ffe600] py-2 text-center text-xs font-bold text-[#000000] hover:bg-[#fff04d] transition-colors"
                >
                  Download MP4
                </a>
                {onLoadRenderedCut && (
                  <button
                    type="button"
                    onClick={() => {
                      onLoadRenderedCut(exportResult.download_url, exportResult.duration_seconds);
                      onClose();
                    }}
                    className="rounded border border-[#1f2433] bg-[#11141e] px-3 py-2 text-xs font-semibold text-[#f3f4f6] hover:bg-[#161a26]"
                  >
                    Play in Preview
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="mt-5 flex items-center justify-end gap-2 border-t border-[#1f2433] pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded px-3 py-1.5 text-xs font-semibold text-[#9ca3af] hover:text-[#ffffff]"
          >
            Close
          </button>
          {!exportResult && (
            <button
              type="button"
              onClick={handleStartExport}
              disabled={isRendering}
              className="rounded bg-[#ffe600] px-4 py-1.5 text-xs font-bold text-[#000000] hover:bg-[#fff04d] disabled:opacity-50 transition-colors shadow-[0_0_10px_rgba(255,230,0,0.3)]"
            >
              {isRendering ? "Rendering..." : "Start Export Render"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
