/**
 * Public frontend configuration validated safely at runtime.
 * Never access private server secrets (MODEL_API_KEY, AWS credentials) from this file.
 */

export interface FrontendConfig {
  apiBaseUrl: string;
  supabaseUrl?: string;
  supabaseAnonKey?: string;
  allowLocalAuthFallback: boolean;
}

export function getFrontendConfig(): FrontendConfig {
  const isProduction = process.env.NODE_ENV === "production";
  const allowLocalAuthFallback =
    !isProduction &&
    process.env.NEXT_PUBLIC_ALLOW_LOCAL_AUTH_FALLBACK === "true";

  // In production or inside HTTPS browser runtimes, always default to relative paths ("")
  // so requests route through CloudFront and Nginx without Mixed Content or localhost connection errors.
  const isBrowser = typeof window !== "undefined";
  const isHttps = isBrowser && window.location.protocol === "https:";
  const rawApiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  let apiBaseUrl = "";
  if (isProduction || isHttps) {
    // Only use rawApiBase if it is an explicit non-localhost absolute URL or relative path
    if (rawApiBase && !rawApiBase.includes("localhost") && !rawApiBase.includes("127.0.0.1")) {
      apiBaseUrl = rawApiBase;
    } else {
      apiBaseUrl = "";
    }
  } else {
    apiBaseUrl = rawApiBase || "http://localhost:8000";
  }

  return {
    apiBaseUrl,
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || undefined,
    supabaseAnonKey:
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ||
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ||
      undefined,
    allowLocalAuthFallback,
  };
}
