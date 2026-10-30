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

export interface AnalysisResponseData {
  id: string;
  project_id: string;
  media_id: string;
  provider: string;
  model: string;
  blueprint: EditingBlueprintData;
  created_at: string;
}

