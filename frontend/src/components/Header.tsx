"use client";

import { useEffect, useState } from "react";
import { getFrontendConfig } from "@/lib/config";

interface HealthState {
  status: "checking" | "healthy" | "offline";
  service?: string;
  version?: string;
  environment?: string;
}

export function Header() {
  const [health, setHealth] = useState<HealthState>({ status: "checking" });
  const config = getFrontendConfig();

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${config.apiBaseUrl}/api/health`, {
          cache: "no-store",
        });
        if (res.ok) {
          const data = await res.json();
          if (active) {
            setHealth({
              status: "healthy",
              service: data.service,
              version: data.version,
              environment: data.environment,
            });
          }
        } else {
          if (active) setHealth({ status: "offline" });
        }
      } catch {
        if (active) setHealth({ status: "offline" });
      }
    };

    checkHealth();
    return () => {
      active = false;
    };
  }, [config.apiBaseUrl]);

  return (
    <header className="border-b border-[#262b33] bg-[#111418] px-6 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-3 rounded-full bg-[#e6ff00] shadow-[0_0_8px_rgba(230,255,0,0.5)]"
              aria-hidden="true"
            />
            <span className="text-xl font-bold tracking-tight text-[#f3f4f6]">
              LolixCopilot
            </span>
          </div>
          <span className="hidden text-xs text-[#6b7280] sm:inline-block">/</span>
          <span className="hidden text-xs font-medium text-[#9ca3af] md:inline-block">
            From raw footage to a stronger cut.
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="rounded border border-[#262b33] bg-[#181c22] px-2.5 py-1 text-[11px] font-mono font-medium text-[#9ca3af]">
            Meta Hackathon MVP
          </span>

          <div
            className="flex items-center gap-1.5 rounded-full border border-[#262b33] bg-[#181c22] px-3 py-1 text-xs"
            title={
              health.status === "healthy"
                ? `Backend: ${health.service} v${health.version} (${health.environment})`
                : health.status === "checking"
                ? "Checking API connectivity..."
                : `API unavailable at ${config.apiBaseUrl}`
            }
          >
            <span
              className={`h-2 w-2 rounded-full ${
                health.status === "healthy"
                  ? "bg-[#22c55e]"
                  : health.status === "checking"
                  ? "bg-[#eab308] animate-pulse"
                  : "bg-[#ef4444]"
              }`}
              aria-hidden="true"
            />
            <span className="font-mono text-[11px] text-[#9ca3af]">
              {health.status === "healthy"
                ? "API Active"
                : health.status === "checking"
                ? "Connecting"
                : "API Offline"}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
