"use client";

import { useEffect, useState } from "react";
import { LolixcoLogo } from "@/components/brand/LolixcoLogo";
import { getFrontendConfig } from "@/lib/config";

interface TopCommandBarProps {
  projectName: string;
  setProjectName: (name: string) => void;
  aspectRatio: "9:16" | "16:9" | "1:1";
  setAspectRatio: (ratio: "9:16" | "16:9" | "1:1") => void;
  onOpenPrivacyNotice: () => void;
  onOpenExport?: () => void;
  isExporting?: boolean;
}

export function TopCommandBar({
  projectName,
  setProjectName,
  aspectRatio,
  setAspectRatio,
  onOpenPrivacyNotice,
  onOpenExport,
  isExporting,
}: TopCommandBarProps) {
  const [isEditingName, setIsEditingName] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "connecting" | "offline">("connecting");
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const config = getFrontendConfig();

  useEffect(() => {
    let active = true;
    const checkApi = async () => {
      try {
        const res = await fetch(`${config.apiBaseUrl}/api/health`, { cache: "no-store" });
        if (active) {
          setHealthStatus(res.ok ? "healthy" : "offline");
        }
      } catch {
        if (active) setHealthStatus("offline");
      }
    };
    checkApi();
    const interval = setInterval(checkApi, 20000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [config.apiBaseUrl]);

  const handleExportClick = () => {
    if (onOpenExport) {
      onOpenExport();
      return;
    }
    setExportNotice("Exporting blueprints will be enabled in Phase 3. Workstation is currently in preview mode.");
    setTimeout(() => setExportNotice(null), 3500);
  };

  const handleShareClick = () => {
    setExportNotice("Collaborative project sharing will be configured with Supabase Auth in Phase 1.");
    setTimeout(() => setExportNotice(null), 3500);
  };

  return (
    <header className="relative z-30 flex h-12 w-full shrink-0 items-center justify-between border-b border-[#1f2433] bg-[#0a0c10] px-4 select-none">
      {/* Left side: Brand, Project name, and Save state */}
      <div className="flex items-center gap-3">
        <LolixcoLogo size={26} showWordmark={true} />

        <div className="h-4 w-px bg-[#202532]" aria-hidden="true" />

        {isEditingName ? (
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            onBlur={() => setIsEditingName(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "Escape") setIsEditingName(false);
            }}
            autoFocus
            className="rounded border border-[#ffe600] bg-[#11141e] px-2 py-0.5 text-xs font-semibold text-[#ffffff] focus:outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => setIsEditingName(true)}
            title="Click to rename project"
            className="flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs font-semibold text-[#f3f4f6] transition-colors hover:bg-[#161a26]"
          >
            <span>{projectName}</span>
            <svg
              className="h-3.5 w-3.5 text-[#9ca3af]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}

        <div className="hidden items-center gap-1 text-[11px] font-mono text-[#64748b] md:flex">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#22c55e]" />
          <span>Saved</span>
        </div>
      </div>

      {/* Center: Live API status & notification */}
      <div className="flex items-center gap-3">
        {exportNotice && (
          <div className="animate-fade-in rounded border border-[#ffe600]/40 bg-[#161a26] px-3 py-1 text-xs font-medium text-[#ffe600]">
            {exportNotice}
          </div>
        )}

        <div
          className="flex items-center gap-1.5 rounded-full border border-[#1f2433] bg-[#11141e] px-2.5 py-0.5 text-[11px] font-mono text-[#9ca3af]"
          title={
            healthStatus === "healthy"
              ? `Connected to LolixCopilot FastAPI backend at ${config.apiBaseUrl}`
              : `FastAPI backend unavailable at ${config.apiBaseUrl}`
          }
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              healthStatus === "healthy"
                ? "bg-[#22c55e]"
                : healthStatus === "connecting"
                ? "bg-[#eab308] animate-pulse"
                : "bg-[#ef4444]"
            }`}
          />
          <span className="hidden sm:inline">
            {healthStatus === "healthy" ? "API Online" : healthStatus === "connecting" ? "Connecting" : "API Offline"}
          </span>
        </div>
      </div>

      {/* Right side: Aspect ratio selector, Privacy notice, Share, Export */}
      <div className="flex items-center gap-2">
        {/* Aspect ratio selector */}
        <div className="relative">
          <select
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value as "9:16" | "16:9" | "1:1")}
            aria-label="Select preview aspect ratio"
            className="cursor-pointer appearance-none rounded-md border border-[#1f2433] bg-[#11141e] py-1.5 pl-3 pr-7 text-xs font-medium text-[#f3f4f6] transition-colors hover:border-[#333a4d] focus:border-[#ffe600] focus:outline-none"
          >
            <option value="9:16">9:16 (Reels/TikTok)</option>
            <option value="16:9">16:9 (Landscape)</option>
            <option value="1:1">1:1 (Square)</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-[#9ca3af]">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Data / Privacy info */}
        <button
          type="button"
          onClick={onOpenPrivacyNotice}
          title="Data protection and Meta AI credits disclosure"
          className="flex h-8 items-center gap-1.5 rounded-md border border-[#1f2433] bg-[#11141e] px-2.5 text-xs font-medium text-[#9ca3af] transition-colors hover:border-[#333a4d] hover:text-[#ffffff]"
        >
          <svg className="h-3.5 w-3.5 text-[#ffe600]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="hidden lg:inline">Notice</span>
        </button>

        {/* Share Button */}
        <button
          type="button"
          onClick={handleShareClick}
          className="flex h-8 items-center gap-1.5 rounded-md border border-[#1f2433] bg-[#11141e] px-3 text-xs font-semibold text-[#f3f4f6] transition-colors hover:border-[#333a4d] hover:bg-[#161a26]"
        >
          <svg className="h-3.5 w-3.5 text-[#9ca3af]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
          </svg>
          <span>Share</span>
        </button>

        {/* Export Button (Exact Neon Yellow CTA) */}
        <button
          type="button"
          onClick={handleExportClick}
          disabled={isExporting}
          className="flex h-8 items-center gap-1.5 rounded-md bg-[#ffe600] px-3.5 text-xs font-bold text-[#000000] shadow-[0_0_12px_rgba(255,230,0,0.25)] transition-all hover:bg-[#fff04d] active:scale-98 disabled:opacity-50"
        >
          {isExporting ? (
            <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          )}
          <span>{isExporting ? "Rendering..." : "Export Cut"}</span>
        </button>
      </div>
    </header>
  );
}
