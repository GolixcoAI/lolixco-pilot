"use client";

import { AiUsageWidget } from "./AiUsageWidget";

export type NavTab =
  | "media"
  | "edit"
  | "ai"
  | "effects"
  | "color"
  | "audio"
  | "captions"
  | "project";

interface NavRailProps {
  activeTab: NavTab;
  setActiveTab: (tab: NavTab) => void;
  onOpenPrivacyNotice: () => void;
}

export function NavRail({
  activeTab,
  setActiveTab,
  onOpenPrivacyNotice,
}: NavRailProps) {
  const tabs = [
    {
      id: "media" as NavTab,
      label: "Media",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
          />
        </svg>
      ),
    },
    {
      id: "edit" as NavTab,
      label: "Edit",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0-5.758a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z"
          />
        </svg>
      ),
    },
    {
      id: "ai" as NavTab,
      label: "AI",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
          />
        </svg>
      ),
    },
    {
      id: "effects" as NavTab,
      label: "Effects",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
      ),
    },
    {
      id: "color" as NavTab,
      label: "Color",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M7 21a4 4 0 01-4-4 8.014 8.014 0 014-7.236M17 21a4 4 0 004-4 8.014 8.014 0 00-4-7.236M12 3a9 9 0 019 9 4 4 0 01-4 4 4 4 0 01-4-4 9 9 0 01-1-9z"
          />
        </svg>
      ),
    },
    {
      id: "audio" as NavTab,
      label: "Audio",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
          />
        </svg>
      ),
    },
    {
      id: "captions" as NavTab,
      label: "Captions",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      ),
    },
    {
      id: "project" as NavTab,
      label: "Project",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
          />
        </svg>
      ),
    },
  ];

  return (
    <aside
      aria-label="Workstation View Modes"
      className="flex w-16 shrink-0 flex-col items-center justify-between border-r border-[#1f2433] bg-[#08090c] py-2 select-none z-20"
    >
      {/* Top action rail */}
      <div className="flex w-full flex-col items-center gap-0.5">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`group relative flex w-full flex-col items-center justify-center py-2 transition-colors ${
                isActive
                  ? "bg-[#11141e] text-[#ffe600]"
                  : "text-[#9ca3af] hover:bg-[#10131c] hover:text-[#f3f4f6]"
              }`}
            >
              {/* Active yellow indicator on the left edge */}
              {isActive && (
                <span
                  className="absolute left-0 top-0 h-full w-[3px] bg-[#ffe600] shadow-[0_0_8px_rgba(255,230,0,0.6)]"
                  aria-hidden="true"
                />
              )}

              <div className="mb-0.5 transition-transform group-hover:scale-110">
                {tab.icon}
              </div>
              <span className="text-[9px] font-medium tracking-wide">
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Bottom rail actions */}
      <div className="flex w-full flex-col items-center gap-2 px-1">
        {/* Compact AI Usage Pill */}
        <AiUsageWidget compact={true} />

        <div className="h-px w-8 bg-[#1f2433]" />

        {/* Settings button */}
        <button
          type="button"
          title="Project and Workspace Settings"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[#64748b] transition-colors hover:bg-[#11141e] hover:text-[#f3f4f6]"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
        </button>

        {/* Privacy notice button */}
        <button
          type="button"
          onClick={onOpenPrivacyNotice}
          title="Privacy and Data Terms"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[#64748b] transition-colors hover:bg-[#11141e] hover:text-[#ffe600]"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.8}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        </button>
      </div>
    </aside>
  );
}
