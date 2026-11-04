"use client";

import { useEffect, useState } from "react";
import { AIUsageTelemetry } from "@/types/workstation";
import { fetchUsageTelemetry } from "@/lib/mediaApi";

interface AiUsageWidgetProps {
  telemetry?: AIUsageTelemetry | null;
  onRefresh?: () => void;
  compact?: boolean;
}

export function AiUsageWidget({ telemetry: propTelemetry, compact = false }: AiUsageWidgetProps) {
  const [telemetry, setTelemetry] = useState<AIUsageTelemetry | null>(propTelemetry || null);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    let active = true;
    const pollUsage = async () => {
      try {
        const data = await fetchUsageTelemetry();
        if (active) {
          setTelemetry(data);
        }
      } catch {
        // Fallback silently if offline
      }
    };

    pollUsage();
    const interval = setInterval(pollUsage, 12000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const totalCalls = telemetry?.total_ai_calls ?? 0;
  const modalSec = telemetry?.modal.compute_seconds ?? 0;
  const metaTokens = telemetry?.meta.total_tokens ?? 0;
  const basetenTokens = telemetry?.baseten.total_tokens ?? 0;
  const lambdaRuns = telemetry?.lambda_processor.calls ?? 0;
  const totalCost = telemetry?.estimated_total_cost_usd ?? 0;

  if (compact) {
    return (
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="group relative flex w-full cursor-pointer flex-col items-center px-1 py-2 text-[#9ca3af] hover:text-[#f3f4f6]"
        title="View live AI compute usage"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded border border-[#1f2433] bg-[#11141e] text-[10px] font-bold text-[#ffe600]">
          {totalCalls}
        </div>
        <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wider text-[#64748b]">
          Usage
        </span>
      </div>
    );
  }

  return (
    <div className="w-full rounded-md border border-[#1f2433] bg-[#0c0e15] p-2.5 text-xs select-none">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wider text-[#9ca3af]">
          AI Telemetry
        </span>
        <span className="rounded bg-[#ffe600]/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#ffe600]">
          {totalCalls} {totalCalls === 1 ? "Call" : "Calls"}
        </span>
      </div>

      {/* Compute stats row */}
      <div className="mt-2 space-y-1.5 text-[11px] font-mono">
        <div className="flex items-center justify-between text-[#d1d5db]">
          <span className="flex items-center gap-1 text-[#9ca3af]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]" />
            Modal H100
          </span>
          <span>{modalSec.toFixed(1)}s</span>
        </div>

        <div className="flex items-center justify-between text-[#d1d5db]">
          <span className="flex items-center gap-1 text-[#9ca3af]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#a855f7]" />
            Meta Spark
          </span>
          <span>{metaTokens} tok</span>
        </div>

        <div className="flex items-center justify-between text-[#d1d5db]">
          <span className="flex items-center gap-1 text-[#9ca3af]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#10b981]" />
            Baseten Open
          </span>
          <span>{basetenTokens} tok</span>
        </div>

        {lambdaRuns > 0 && (
          <div className="flex items-center justify-between text-[#d1d5db]">
            <span className="flex items-center gap-1 text-[#9ca3af]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#f59e0b]" />
              AWS Lambda
            </span>
            <span>{lambdaRuns} runs</span>
          </div>
        )}
      </div>

      {/* Cost estimation footer */}
      <div className="mt-2.5 flex items-center justify-between border-t border-[#1f2433] pt-1.5 text-[10px] text-[#64748b]">
        <span>Est. Session Cost</span>
        <span className="font-mono font-semibold text-[#f3f4f6]">
          ${totalCost.toFixed(4)}
        </span>
      </div>
    </div>
  );
}

