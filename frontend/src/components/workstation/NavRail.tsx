"use client";

export type NavTab = "media" | "editpilot" | "timeline" | "assets";

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
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      ),
    },
    {
      id: "editpilot" as NavTab,
      label: "EditPilot",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
      ),
    },
    {
      id: "timeline" as NavTab,
      label: "Timeline",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 6h16M4 12h16M4 18h7" />
        </svg>
      ),
    },
    {
      id: "assets" as NavTab,
      label: "Assets",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
      ),
    },
  ];

  return (
    <aside
      aria-label="Workstation View Modes"
      className="flex w-16 shrink-0 flex-col items-center justify-between border-r border-[#1f2433] bg-[#08090c] py-3 select-none"
    >
      {/* Top action rail */}
      <div className="flex w-full flex-col items-center gap-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`group relative flex w-full flex-col items-center justify-center py-2.5 transition-colors ${
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

              <div className="mb-1 transition-transform group-hover:scale-110">
                {tab.icon}
              </div>
              <span className="text-[10px] font-semibold tracking-wide">
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Bottom rail actions */}
      <div className="flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={onOpenPrivacyNotice}
          title="Privacy and Data Terms"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-[#64748b] transition-colors hover:bg-[#11141e] hover:text-[#ffe600]"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
