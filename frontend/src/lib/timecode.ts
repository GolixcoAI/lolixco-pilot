/**
 * Timecode formatting and validation utilities for video editing workflows.
 */

export function formatTimecode(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "00:00.0";
  }

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const wholeSecs = Math.floor(secs);
  const tenths = Math.floor((secs - wholeSecs) * 10);

  const formattedMins = String(mins).padStart(2, "0");
  const formattedSecs = String(wholeSecs).padStart(2, "0");

  return `${formattedMins}:${formattedSecs}.${tenths}`;
}

export function validateSceneTimestamps(
  startSeconds: number,
  endSeconds: number,
  mediaDuration?: number
): { valid: boolean; error?: string } {
  if (!Number.isFinite(startSeconds) || !Number.isFinite(endSeconds)) {
    return { valid: false, error: "Timestamps must be finite numbers" };
  }

  if (startSeconds < 0) {
    return { valid: false, error: "Start timestamp cannot be negative" };
  }

  if (startSeconds >= endSeconds) {
    return {
      valid: false,
      error: `Start timestamp (${startSeconds}s) must be strictly less than end timestamp (${endSeconds}s)`,
    };
  }

  if (mediaDuration !== undefined && endSeconds > mediaDuration + 0.1) {
    return {
      valid: false,
      error: `End timestamp (${endSeconds}s) exceeds media duration (${mediaDuration}s)`,
    };
  }

  return { valid: true };
}
