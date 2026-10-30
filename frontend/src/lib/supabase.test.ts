import { describe, it, expect, beforeEach, vi } from "vitest";
import { getAuthToken, clearAnonymousSession, getSupabaseClient } from "./supabase";

describe("Supabase anonymous auth", () => {
  beforeEach(async () => {
    await clearAnonymousSession();
    vi.restoreAllMocks();
  });

  it("returns null client when public env vars are not set", () => {
    const client = getSupabaseClient();
    expect(client).toBeNull();
  });

  it("generates a persistent anonymous token when running without credentials", async () => {
    const token1 = await getAuthToken();
    expect(token1).toBeDefined();
    expect(token1.length).toBeGreaterThan(10);

    // Calling again returns the exact same cached token
    const token2 = await getAuthToken();
    expect(token2).toBe(token1);
  });

  it("clears session data on clearAnonymousSession()", async () => {
    const tokenBefore = await getAuthToken();
    expect(tokenBefore).toBeDefined();

    await clearAnonymousSession();
    // After clear, a new token is generated
    const tokenAfter = await getAuthToken();
    expect(tokenAfter).toBeDefined();
  });
});
