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
  onNewProject?: () => void;
}

export function TopCommandBar({
  projectName,
  setProjectName,
  aspectRatio,
  setAspectRatio,
  onOpenPrivacyNotice,
  onOpenExport,
  isExporting,
  onNewProject,
}: TopCommandBarProps) {
  const [isEditingName, setIsEditingName] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "connecting" | "offline">("connecting");
  const [commitSha, setCommitSha] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const config = getFrontendConfig();

  useEffect(() => {
    let active = true;
    const checkApi = async () => {
      try {
        const res = await fetch(`${config.apiBaseUrl}/api/health`, { cache: "no-store" });
        if (active) {
          if (res.ok) {
            setHealthStatus("healthy");
            const data = await res.json().catch(() => null);
            if (data?.commit_sha) {
              setCommitSha(data.commit_sha.slice(0, 7));
            }
          } else {
            setHealthStatus("offline");
          }
        }
      } catch {
        if (active) setHealthStatus("offline");
      }
    };
    checkApi();
    const interval = setInterval(checkApi, 25000);
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
  };

  const handleShareClick = () => {
    setNotice("Project URL copied to clipboard");
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(window.location.href).catch(() => {});
    }
    setTimeout(() => setNotice(null), 3000);
  };

  return (
    <header className="relative z-30 flex h-11 w-full shrink-0 items-center justify-between border-b border-[#1f2433] bg-[#08090c] px-3 select-none">
      {/* Left section: Logo, Project Name, Saved State */}
      <div className="flex items-center gap-3">
        <LolixcoLogo height={26} showDropdown={true} />

        <div className="h-4 w-px bg-[#1f2433]" aria-hidden="true" />

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
            title="Click to rename session"
            className="group flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs font-semibold text-[#f3f4f6] transition-colors hover:bg-[#161a26]"
          >
            <span>{projectName}</span>
            <svg
              className="h-3 w-3 text-[#64748b] group-hover:text-[#ffe600]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
              />
            </svg>
          </button>
        )}

        <div className="flex items-center gap-1 text-[11px] font-mono text-[#9ca3af]">
          <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#22c55e]/15 text-[#22c55e]">
            ✓
          </span>
          <span className="text-[#64748b]">Saved just now</span>
        </div>

        {commitSha && (
          <span
            title={`Deployed Release Commit: ${commitSha}`}
            className="rounded border border-[#1f2433] bg-[#11141e] px-1.5 py-0.5 font-mono text-[10px] text-[#64748b]"
          >
            {commitSha}
          </span>
        )}

        {onNewProject && (
          <button
            type="button"
            onClick={onNewProject}
            title="Create a new empty project session"
            className="flex items-center gap-1 rounded border border-[#1f2433] bg-[#11141e] px-2 py-0.5 text-[11px] font-semibold text-[#f3f4f6] transition-colors hover:border-[#ffe600]/40 hover:bg-[#161a26]"
          >
            <span className="text-[#ffe600] font-bold">+</span>
            <span>New Project</span>
          </button>
        )}
      </div>

      {/* Center: Live status notification */}
      <div className="flex items-center gap-3">
        {notice && (
          <div className="animate-fade-in rounded border border-[#ffe600]/40 bg-[#161a26] px-3 py-0.5 text-[11px] font-medium text-[#ffe600]">
            {notice}
          </div>
        )}
      </div>

      {/* Right section: Undo/Redo, Aspect ratio, Share, Export */}
      <div className="flex items-center gap-2">
        {/* Undo / Redo */}
        <div className="flex items-center gap-0.5 pr-1 text-[#9ca3af]">
          <button
            type="button"
            title="Undo (Ctrl+Z)"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2m0 0l-4-4m4 4l4-4" />
            </svg>
          </button>
          <button
            type="button"
            title="Redo (Ctrl+Y)"
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-[#141722] hover:text-[#ffffff]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a5 5 0 00-5 5v2m0 0l4-4m-4 4l-4-4" />
            </svg>
          </button>
        </div>

        {/* Aspect ratio dropdown */}
        <div className="relative">
          <select
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value as "9:16" | "16:9" | "1:1")}
            aria-label="Select aspect ratio"
            className="cursor-pointer appearance-none rounded border border-[#1f2433] bg-[#11141e] py-1 pl-2.5 pr-6 text-[11px] font-medium text-[#f3f4f6] transition-colors hover:border-[#333a4d] focus:border-[#ffe600] focus:outline-none"
          >
            <option value="16:9">16:9</option>
            <option value="9:16">9:16</option>
            <option value="1:1">1:1</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-1.5 text-[#9ca3af]">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Share Button */}
        <button
          type="button"
          onClick={handleShareClick}
          className="flex h-7 items-center gap-1.5 rounded border border-[#1f2433] bg-[#11141e] px-2.5 text-[11px] font-semibold text-[#f3f4f6] transition-colors hover:border-[#333a4d] hover:bg-[#161a26]"
        >
          <svg className="h-3.5 w-3.5 text-[#9ca3af]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <span>Share</span>
        </button>

        {/* Export Button (Exact Neon Yellow CTA) */}
        <button
          type="button"
          onClick={handleExportClick}
          disabled={isExporting}
          className="flex h-7 items-center gap-1.5 rounded bg-[#ffe600] px-3.5 text-xs font-bold text-[#000000] shadow-[0_0_12px_rgba(255,230,0,0.3)] transition-all hover:bg-[#fff04d] active:scale-98 disabled:opacity-50"
        >
          {isExporting ? (
            <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
          <span>{isExporting ? "Rendering..." : "Export"}</span>
        </button>
      </div>
    </header>
  );
}
