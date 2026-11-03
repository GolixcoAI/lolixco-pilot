interface LolixcoLogoProps {
  size?: number;
  height?: number;
  className?: string;
  showWordmark?: boolean;
  showDropdown?: boolean;
}

export function LolixcoLogo({
  size = 28,
  height,
  className = "",
  showWordmark = false,
  showDropdown = false,
}: LolixcoLogoProps) {
  const actualHeight = height || size || 28;

  return (
    <div
      className={`flex items-center gap-1.5 select-none cursor-pointer group ${className}`}
      title="LolixCopilot — From raw footage to a stronger cut."
    >
      {/* Official LolixCopilot Logo (Emblem + LOLIXCO + PILOT) */}
      <div className="relative flex items-center">
        <img
          src="/branding/lolixcopilot-logo.svg"
          alt="LolixCopilot"
          className="h-6 sm:h-7 w-auto object-contain transition-opacity group-hover:opacity-95"
          style={{ maxHeight: actualHeight ? `${actualHeight}px` : "28px" }}
        />
      </div>

      {showDropdown && (
        <svg
          className="h-3 w-3 text-[#9ca3af] transition-colors group-hover:text-[#ffe600] shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      )}
    </div>
  );
}
