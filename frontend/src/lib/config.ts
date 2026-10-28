/**
 * Public frontend configuration validated safely at runtime.
 * Never access private server secrets (MODEL_API_KEY, AWS credentials) from this file.
 */

export interface FrontendConfig {
  apiBaseUrl: string;
  supabaseUrl?: string;
  supabaseAnonKey?: string;
}

export function getFrontendConfig(): FrontendConfig {
  return {
    apiBaseUrl:
      process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000",
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || undefined,
    supabaseAnonKey:
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() || undefined,
  };
}
