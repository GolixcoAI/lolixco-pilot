import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  getAuthToken,
  clearAnonymousSession,
  getSupabaseClient,
  resetSupabaseClient,
} from "./supabase";

describe("Supabase anonymous auth", () => {
  const originalEnv = { ...process.env };

  beforeEach(async () => {
    process.env = { ...originalEnv };
    resetSupabaseClient();
    await clearAnonymousSession();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    resetSupabaseClient();
  });

  it("returns null client when public env vars are not set", () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    resetSupabaseClient();

    const client = getSupabaseClient();
    expect(client).toBeNull();
  });

  it("generates a persistent anonymous token when running with explicit local fallback enabled", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK = "true";
    resetSupabaseClient();

    const token1 = await getAuthToken();
    expect(token1).toBeDefined();
    expect(token1.length).toBeGreaterThan(10);

    // Calling again returns the exact same cached token
    const token2 = await getAuthToken();
    expect(token2).toBe(token1);
  });

  it("throws clear authentication error when credentials not configured and fallback disabled", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    delete process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK;
    resetSupabaseClient();

    await expect(getAuthToken()).rejects.toThrow(
      "Supabase credentials are not configured and local anonymous authentication fallback is disabled"
    );
  });

  it("blocks local fallback in production even if fallback env var is set", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK = "true";
    // @ts-expect-error test override
    process.env.NODE_ENV = "production";
    resetSupabaseClient();

    await expect(getAuthToken()).rejects.toThrow(
      "Supabase credentials are not configured and local anonymous authentication fallback is disabled"
    );
  });

  it("throws clear error and NEVER silently falls back to local UUID when signInAnonymously fails", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://mockproject.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "mock-pub-key-123";
    process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK = "true"; // Even if fallback enabled!
    resetSupabaseClient();

    const client = getSupabaseClient();
    expect(client).not.toBeNull();

    // Mock client auth methods
    if (client) {
      vi.spyOn(client.auth, "getSession").mockResolvedValue({
        data: { session: null },
        error: null,
      } as unknown as Awaited<ReturnType<typeof client.auth.getSession>>);

      vi.spyOn(client.auth, "signInAnonymously").mockResolvedValue({
        data: { user: null, session: null },
        error: {
          message: "Anonymous sign-ins are disabled for this project",
          name: "AuthApiError",
          status: 400,
        },
      } as unknown as Awaited<ReturnType<typeof client.auth.signInAnonymously>>);
    }

    // Must throw clear authentication error rather than returning a local UUID
    await expect(getAuthToken()).rejects.toThrow(
      "Authentication error: Supabase anonymous sign-in failed: Anonymous sign-ins are disabled for this project"
    );
  });

  it("returns access token when Supabase anonymous sign-in succeeds", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://mockproject.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "mock-pub-key-123";
    resetSupabaseClient();

    const client = getSupabaseClient();
    expect(client).not.toBeNull();

    if (client) {
      vi.spyOn(client.auth, "getSession").mockResolvedValue({
        data: { session: null },
        error: null,
      } as unknown as Awaited<ReturnType<typeof client.auth.getSession>>);

      vi.spyOn(client.auth, "signInAnonymously").mockResolvedValue({
        data: {
          session: {
            access_token: "mock-supabase-jwt-token-xyz",
            token_type: "bearer",
            expires_in: 3600,
            expires_at: 1800000000,
            refresh_token: "refresh-token",
            user: {
              id: "user-123",
              app_metadata: {},
              user_metadata: {},
              aud: "authenticated",
              created_at: new Date().toISOString(),
            },
          },
          user: {
            id: "user-123",
            app_metadata: {},
            user_metadata: {},
            aud: "authenticated",
            created_at: new Date().toISOString(),
          },
        },
        error: null,
      } as unknown as Awaited<ReturnType<typeof client.auth.signInAnonymously>>);
    }

    const token = await getAuthToken();
    expect(token).toBe("mock-supabase-jwt-token-xyz");
  });

  it("clears session data on clearAnonymousSession()", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK = "true";
    resetSupabaseClient();

    const tokenBefore = await getAuthToken();
    expect(tokenBefore).toBeDefined();

    await clearAnonymousSession();
    // After clear, a new token is generated
    const tokenAfter = await getAuthToken();
    expect(tokenAfter).toBeDefined();
  });
});
