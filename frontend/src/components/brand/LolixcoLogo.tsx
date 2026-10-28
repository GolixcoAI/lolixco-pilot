import Image from "next/image";

interface LolixcoLogoProps {
  size?: number;
  className?: string;
  showWordmark?: boolean;
}

export function LolixcoLogo({
  size = 28,
  className = "",
  showWordmark = false,
}: LolixcoLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {/* Official Lolixco Icon */}
      <div
        className="relative shrink-0 overflow-hidden rounded-md bg-[#000000] p-0.5"
        style={{ width: size, height: size }}
      >
        <Image
          src="/brand/icon.png"
          alt="Lolixco Logo"
          width={size * 2}
          height={size * 2}
          className="h-full w-full object-contain"
          priority
        />
      </div>

      {showWordmark && (
        <div className="flex items-center text-sm font-black tracking-wider">
          <span className="text-[#ffffff]">LOLIXCO</span>
          <span className="text-[#ffe600]">PILOT</span>
        </div>
      )}
    </div>
  );
}
