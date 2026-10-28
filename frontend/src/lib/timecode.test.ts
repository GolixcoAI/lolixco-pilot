import { describe, expect, it } from "vitest";
import { formatTimecode, validateSceneTimestamps } from "./timecode";

describe("formatTimecode", () => {
  it("formats 0 seconds properly", () => {
    expect(formatTimecode(0)).toBe("00:00.0");
  });

  it("formats seconds with tenths precision", () => {
    expect(formatTimecode(4.2)).toBe("00:04.2");
    expect(formatTimecode(15.8)).toBe("00:15.8");
  });

  it("formats minutes and seconds accurately", () => {
    expect(formatTimecode(65.4)).toBe("01:05.4");
    expect(formatTimecode(135.0)).toBe("02:15.0");
  });

  it("handles negative or non-finite numbers gracefully", () => {
    expect(formatTimecode(-10)).toBe("00:00.0");
    expect(formatTimecode(Infinity)).toBe("00:00.0");
    expect(formatTimecode(NaN)).toBe("00:00.0");
  });
});

describe("validateSceneTimestamps", () => {
  it("validates proper chronological bounds", () => {
    const res = validateSceneTimestamps(2.4, 6.8, 30.0);
    expect(res.valid).toBe(true);
    expect(res.error).toBeUndefined();
  });

  it("rejects inverted timestamps", () => {
    const res = validateSceneTimestamps(10.0, 5.0, 30.0);
    expect(res.valid).toBe(false);
    expect(res.error).toContain("must be strictly less than end timestamp");
  });

  it("rejects equal timestamps", () => {
    const res = validateSceneTimestamps(4.0, 4.0, 30.0);
    expect(res.valid).toBe(false);
    expect(res.error).toContain("must be strictly less than end timestamp");
  });

  it("rejects negative start timestamp", () => {
    const res = validateSceneTimestamps(-2.0, 5.0, 30.0);
    expect(res.valid).toBe(false);
    expect(res.error).toContain("cannot be negative");
  });

  it("rejects timestamps exceeding media duration", () => {
    const res = validateSceneTimestamps(20.0, 65.0, 60.0);
    expect(res.valid).toBe(false);
    expect(res.error).toContain("exceeds media duration");
  });
});
