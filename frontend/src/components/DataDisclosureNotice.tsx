export function DataDisclosureNotice() {
  return (
    <div
      role="region"
      aria-label="Privacy and Model Disclosure"
      className="rounded-lg border border-[#262b33] bg-[#111418] p-4 text-xs text-[#9ca3af]"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-block text-[#e6ff00] font-mono font-bold">
            [i]
          </span>
          <div>
            <span className="font-semibold text-[#f3f4f6]">
              Data Notice & Privacy:
            </span>{" "}
            Content processed with promotional AI credits may be subject to provider
            improvement terms per Meta API guidelines. Test only with authorized,
            non-sensitive footage. Originals and previews expire after 7 days by default.
          </div>
        </div>

        <div className="flex items-center gap-3 self-end sm:self-auto shrink-0 font-mono text-[11px] text-[#6b7280]">
          <span>TTL: 7 Days</span>
          <span>•</span>
          <span>Private S3</span>
        </div>
      </div>
    </div>
  );
}
