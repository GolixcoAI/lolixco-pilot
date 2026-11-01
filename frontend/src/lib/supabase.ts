/**
 * Supabase client and anonymous session management.
 *
 * Implements passwordless, zero-friction anonymous authentication for LolixCopilot.
 * Anonymous user sessions are tied to the local browser storage.
 * Never exposes service-role keys or server secrets to client code.
 */

import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { getFrontendConfig } from "./config";

let supabaseInstance: SupabaseClient | null = null;

const LOCAL_STORAGE_ANON_ID = "lolixcopilot_anon_user_id";
const LOCAL_STORAGE_ANON_TOKEN = "lolixcopilot_anon_token";

function getDeterministicUuid(): string {
  if (typeof window !== "undefined" && window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID();
  }
  // Fallback RFC4122 v4 UUID generator
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Reset cached Supabase client (used in tests).
 */
export function resetSupabaseClient(): void {
  supabaseInstance = null;
}

/**
 * Return initialized Supabase client if public credentials are configured.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (supabaseInstance) {
    return supabaseInstance;
  }

  const { supabaseUrl, supabaseAnonKey } = getFrontendConfig();
  if (!supabaseUrl || !supabaseAnonKey) {
    return null;
  }

  try {
    supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: false,
      },
    });
    return supabaseInstance;
  } catch (err) {
    console.warn("Failed to initialize Supabase client:", err);
    return null;
  }
}

/**
 * Automatically establish or restore an anonymous session.
 *
 * If Supabase credentials are configured, uses official signInAnonymously().
 * If signInAnonymously() fails, returns a clear error and never falls back to local UUID.
 * If credentials are not configured, local anonymous identity fallback is permitted
 * ONLY when explicitly enabled via NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK in non-production.
 */
export async function getAuthToken(): Promise<string> {
  const { allowLocalAuthFallback } = getFrontendConfig();
  const client = getSupabaseClient();

  if (client) {
    try {
      const { data: sessionData, error: sessionError } = await client.auth.getSession();
      if (sessionError) {
        throw new Error(`Failed to retrieve Supabase session: ${sessionError.message}`);
      }
      if (sessionData.session?.access_token) {
        return sessionData.session.access_token;
      }

      // Establish new anonymous session
      const { data, error } = await client.auth.signInAnonymously();
      if (error) {
        throw new Error(`Supabase anonymous sign-in failed: ${error.message}`);
      }
      if (data.session?.access_token) {
        return data.session.access_token;
      }
      throw new Error("Supabase anonymous sign-in succeeded but returned no access token.");
    } catch (err) {
      // Fail closed when Supabase credentials are configured: NEVER silently create a local UUID!
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`Authentication error: ${message}`);
    }
  }

  // Supabase is NOT configured (offline / test mode)
  // Insecure local identity fallback is permitted ONLY if explicitly enabled in non-production environments.
  if (allowLocalAuthFallback) {
    if (typeof window !== "undefined" && window.localStorage) {
      let token = window.localStorage.getItem(LOCAL_STORAGE_ANON_TOKEN);
      let userId = window.localStorage.getItem(LOCAL_STORAGE_ANON_ID);

      if (!token || !userId) {
        userId = getDeterministicUuid();
        token = userId;
        window.localStorage.setItem(LOCAL_STORAGE_ANON_ID, userId);
        window.localStorage.setItem(LOCAL_STORAGE_ANON_TOKEN, token);
      }
      return token;
    }
    return "00000000-0000-0000-0000-000000000000";
  }

  throw new Error(
    "Supabase credentials are not configured and local anonymous authentication fallback is disabled."
  );
}

/**
 * Clear local anonymous session data (used for testing or resetting user state).
 */
export async function clearAnonymousSession(): Promise<void> {
  const client = getSupabaseClient();
  if (client) {
    try {
      await client.auth.signOut();
    } catch {
      // Ignore signOut errors
    }
  }

  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.removeItem(LOCAL_STORAGE_ANON_ID);
    window.localStorage.removeItem(LOCAL_STORAGE_ANON_TOKEN);
  }
}
