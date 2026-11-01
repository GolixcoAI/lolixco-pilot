export interface MediaClip {
  id: string;
  title: string;
  type: "video" | "audio" | "image";
  duration: number; // in seconds
  size: string;
  resolution?: string;
  src?: string;
  thumbnail?: string;
  isCustom?: boolean;
  isRealUpload?: boolean;
  status?: "pending" | "uploaded" | "verified" | "failed" | "expired";
  s3Key?: string;
  expiresAt?: string;
  uploadProgress?: number;
  errorMessage?: string;
}

export type MomentTag = "HOOK" | "BUILD" | "CLIMAX" | "RESOLVE";

export interface KeyMoment {
  id: string;
  index: number;
  timecode: string;
  seconds: number;
  endSeconds?: number;
  tag: MomentTag;
  title: string;
  description: string;
  action: string;
  thumbnail?: string;
}

export interface CreativeBriefState {
  title: string;
  description: string;
  style: string;
  pacing: string;
  aspectRatio: "9:16" | "16:9" | "1:1";
  targetDuration: number;
}

export interface BlueprintScene {
  id: string;
  start_seconds: number;
  end_seconds: number;
  moment: string;
  why_it_works: string;
  editing_direction: string;
  pacing: "slow" | "medium" | "fast";
  confidence?: number | null;
  thumbnail_key?: string | null;
}

export interface EditingBlueprintData {
  title: string;
  creative_intent: string;
  summary: string;
  target_duration_seconds: number;
  aspect_ratio: string;
  hook: string;
  scenes: BlueprintScene[];
  sequence_rationale: string;
  ending_suggestion: string;
  caveats: string[];
}

export type MediaClassification =
  | "anime"
  | "movie"
  | "tv_series"
  | "game"
  | "music_video"
  | "other"
  | "unknown";

export type ConfidenceLevel = "high" | "medium" | "low" | "unrated";

export type MusicMatchStatus =
  | "confirmed_fingerprint"
  | "strong_inference"
  | "possible_match"
  | "unknown";

export interface SourceIdentificationData {
  media_type: MediaClassification;
  likely_title: string | null;
  franchise?: string | null;
  season_episode?: string | null;
  characters?: string[];
  recognizable_scenes?: string[];
  visual_evidence?: string;
  confidence: ConfidenceLevel;
  confidence_score?: number | null;
  alternative_candidates?: string[];
}

export interface AudioIntelligenceData {
  song_title: string | null;
  artist?: string | null;
  genre?: string | null;
  lyrics_or_vocal_phrases?: string[];
  mood?: string | null;
  tempo?: string | null;
  beat_changes?: string[];
  match_status: MusicMatchStatus;
  confidence_score?: number | null;
}

export interface UsageMetadataData {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  request_id?: string | null;
}

export interface UserFeedbackData {
  confirmed_by_user: boolean;
  corrected_source_title?: string | null;
  corrected_song_title?: string | null;
  notes?: string | null;
  updated_at?: string | null;
}

export type AIProviderName = "baseten" | "meta" | "mock";

export interface AnalysisResponseData {
  id: string;
  project_id: string;
  media_id: string;
  provider: string;
  model: string;
  blueprint: EditingBlueprintData;
  source_identification?: SourceIdentificationData | null;
  audio_intelligence?: AudioIntelligenceData | null;
  usage_metadata?: UsageMetadataData | null;
  user_feedback?: UserFeedbackData | null;
  created_at: string;
}
