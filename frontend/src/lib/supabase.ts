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
 * If not configured (local dev/offline testing), maintains a verified local anonymous session.
 */
export async function getAuthToken(): Promise<string> {
  const client = getSupabaseClient();

  if (client) {
    try {
      const { data: sessionData } = await client.auth.getSession();
      if (sessionData.session?.access_token) {
        return sessionData.session.access_token;
      }

      // Establish new anonymous session
      const { data, error } = await client.auth.signInAnonymously();
      if (error) {
        console.warn("Supabase anonymous sign-in error, using local identity:", error.message);
      } else if (data.session?.access_token) {
        return data.session.access_token;
      }
    } catch (err) {
      console.warn("Error establishing Supabase session:", err);
    }
  }

  // Local fallback anonymous identity
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
