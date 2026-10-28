"use client";

interface PrivacyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PrivacyModal({ isOpen, onClose }: PrivacyModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#000000]/80 p-4 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-lg rounded-xl border border-[#1f2433] bg-[#0d1016] p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1f2433] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-[#ffe600]/15 text-[#ffe600] font-bold text-xs">
              i
            </span>
            <h2 id="privacy-modal-title" className="text-sm font-bold text-[#ffffff]">
              Data Protection & Privacy Notice
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded p-1 text-[#64748b] hover:bg-[#181c28] hover:text-[#ffffff]"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="mt-4 space-y-3.5 text-xs leading-relaxed text-[#9ca3af]">
          <div className="rounded-lg border border-[#1f2433] bg-[#07090f] p-3">
            <span className="font-semibold text-[#ffe600]">
              Meta Model API Terms:
            </span>{" "}
            Content processed while utilizing promotional AI credits may be subject
            to provider improvement guidelines. Always process authorized,
            licensed, or non-sensitive source footage.
          </div>

          <div className="rounded-lg border border-[#1f2433] bg-[#07090f] p-3">
            <span className="font-semibold text-[#ffffff]">
              Private Object Storage:
            </span>{" "}
            Original footage is uploaded directly to a private Amazon S3 bucket.
            URLs are short-lived signed tokens with a 15-minute TTL. No public S3
            endpoints or arbitrary remote URLs are permitted.
          </div>

          <div className="rounded-lg border border-[#1f2433] bg-[#07090f] p-3">
            <span className="font-semibold text-[#ffffff]">
              7-Day Default Retention:
            </span>{" "}
            Raw uploads and derived preview thumbnails automatically expire after 7
            days. Manual project deletion removes database rows and associated
            storage objects immediately.
          </div>
        </div>

        {/* Footer */}
        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-[#ffe600] px-4 py-1.5 text-xs font-bold text-[#000000] transition-colors hover:bg-[#fff04d]"
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}
