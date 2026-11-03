/**
 * Media API client for LolixCopilot video upload, verification, and playback lifecycle.
 */

import { getFrontendConfig } from "./config";
import { getAuthToken } from "./supabase";

export interface ProjectData {
  id: string;
  user_id: string;
  name: string;
  aspect_ratio: string;
  created_at: string;
  updated_at: string;
}

export interface MediaItemData {
  id: string;
  project_id: string;
  user_id: string;
  original_filename: string;
  content_type: string;
  declared_size_bytes: number;
  verified_size_bytes?: number | null;
  duration_seconds?: number | null;
  status: "pending" | "uploaded" | "verified" | "failed" | "expired";
  expires_at: string;
  created_at: string;
  updated_at: string;
  preview_url?: string | null;
}

export interface PresignResponse {
  media_id: string;
  project_id: string;
  s3_key: string;
  upload_url: string;
  expires_in: number;
}

async function getAuthHeaders(): Promise<HeadersInit> {
  const token = await getAuthToken();
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

/**
 * Fetch or create the active project for the authenticated anonymous user.
 */
export async function getOrCreateProject(): Promise<ProjectData> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  // Try listing projects first
  const listRes = await fetch(`${apiBaseUrl}/api/projects`, { headers });
  if (listRes.ok) {
    const projects: ProjectData[] = await listRes.json();
    if (projects.length > 0) {
      return projects[0];
    }
  }

  // Create default project
  const createRes = await fetch(`${apiBaseUrl}/api/projects`, {
    method: "POST",
    headers,
    body: JSON.stringify({ name: "Untitled Cut", aspect_ratio: "9:16" }),
  });

  if (!createRes.ok) {
    throw new Error(`Failed to initialize project: ${createRes.status} ${createRes.statusText}`);
  }
  return createRes.json();
}

/**
 * List all uploaded media assets for a given project.
 */
export async function listProjectMedia(projectId: string): Promise<MediaItemData[]> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media`, { headers });
  if (!res.ok) {
    throw new Error(`Failed to list project media: ${res.status}`);
  }
  return res.json();
}

/**
 * Request an authorized, short-lived presigned S3 upload URL.
 */
export async function requestPresignedUpload(
  projectId: string,
  filename: string,
  contentType: string,
  sizeBytes: number,
): Promise<PresignResponse> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media/presign-upload`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      filename,
      content_type: contentType,
      size_bytes: sizeBytes,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const detail = errorData.detail || `Upload request rejected (${res.status})`;
    throw new Error(detail);
  }
  return res.json();
}

/**
 * Direct client-to-S3 upload using XMLHttpRequest to track honest upload progress.
 */
export function uploadFileToS3(
  uploadUrl: string,
  file: File,
  contentType: string,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    // If testing with mock endpoint, simulate upload completion
    if (uploadUrl.includes("mock-s3.localhost")) {
      let progress = 0;
      const interval = setInterval(() => {
        progress += 25;
        if (onProgress) onProgress(Math.min(progress, 100));
        if (progress >= 100) {
          clearInterval(interval);
          resolve();
        }
      }, 50);
      return;
    }

    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl, true);
    xhr.setRequestHeader("Content-Type", contentType);

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (onProgress) onProgress(100);
        resolve();
      } else {
        reject(new Error(`S3 upload failed with status ${xhr.status}: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during S3 direct video upload. Check CORS settings."));
    };

    xhr.send(file);
  });
}

/**
 * Confirm upload completion and verify S3 object metadata server-side.
 */
export async function confirmUpload(
  projectId: string,
  mediaId: string,
  durationSeconds?: number,
): Promise<MediaItemData> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/confirm`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      duration_seconds: durationSeconds || null,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload verification failed (${res.status})`);
  }
  return res.json();
}

/**
 * Fetch a temporary authorized preview/playback URL for an uploaded video.
 */
export async function getPreviewUrl(projectId: string, mediaId: string): Promise<string> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/preview-url`, {
    headers,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to obtain preview URL (${res.status})`);
  }
  const data = await res.json();
  return data.preview_url;
}

/**
 * Permanently delete a media asset and its underlying S3 object.
 */
export async function deleteMedia(projectId: string, mediaId: string): Promise<void> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}`, {
    method: "DELETE",
    headers,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Delete failed (${res.status})`);
  }
}

/**
 * Request AI video understanding analysis and generation of an Editing Blueprint.
 * Supports configurable model provider (baseten, meta, or mock).
 */
export async function analyzeMedia(
  projectId: string,
  mediaId: string,
  brief: {
    title: string;
    description: string;
    style: string;
    pacing: string;
    aspectRatio: string;
    targetDuration: number;
  },
  confirmedConsent: boolean,
  provider?: import("@/types/workstation").AIProviderName,
): Promise<import("@/types/workstation").AnalysisResponseData> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/analyze`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      brief: {
        title: brief.title,
        description: brief.description,
        style: brief.style,
        pacing: brief.pacing,
        aspect_ratio: brief.aspectRatio,
        target_duration: brief.targetDuration,
      },
      provider: provider || "baseten",
      confirmed_consent: confirmedConsent,
      confirmed_baseten_consent: confirmedConsent,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Analysis request failed (${res.status})`);
  }
  return res.json();
}

/**
 * Retrieve the latest persistent media intelligence and blueprint for an asset.
 */
export async function getLatestAnalysis(
  projectId: string,
  mediaId: string,
): Promise<import("@/types/workstation").AnalysisResponseData | null> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(
    `${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/analyze/latest`,
    { headers },
  );

  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch latest analysis (${res.status})`);
  }
  return res.json();
}

/**
 * Submit user validation or corrections for source identification and soundtrack.
 */
export async function submitAnalysisFeedback(
  projectId: string,
  mediaId: string,
  feedback: {
    confirmed_by_user: boolean;
    corrected_source_title?: string | null;
    corrected_song_title?: string | null;
    notes?: string | null;
  },
  analysisId?: string,
): Promise<import("@/types/workstation").AnalysisResponseData> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const url = analysisId
    ? `${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/analyze/feedback?analysis_id=${encodeURIComponent(analysisId)}`
    : `${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/analyze/feedback`;

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(feedback),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to submit feedback (${res.status})`);
  }
  return res.json();
}

/**
 * Fetch a temporary browser-compatible H.264 preview proxy playback URL.
 */
export async function getProxyPlaybackUrl(
  projectId: string,
  mediaId: string,
): Promise<string> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(
    `${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/proxy-url`,
    { headers },
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch proxy URL (${res.status})`);
  }
  const data = await res.json();
  return data.proxy_url;
}

export interface ChatDirectorEvidence {
  timestamp_seconds: number;
  timecode: string;
  title: string;
  description: string;
  confidence: string;
  phase: string;
  thumbnail_url?: string | null;
}

export interface ChatSceneBreakdown {
  id: string;
  start_seconds: number;
  end_seconds: number;
  timecode_range: string;
  title: string;
  description: string;
  thumbnail_url: string;
  editing_direction?: string | null;
}

export interface ChatEditRecommendation {
  id: string;
  text: string;
  checked: boolean;
  action_type: string;
  timestamp_seconds?: number | null;
}

export interface ChatInferenceTrace {
  provider: string;
  model: string;
  task: string;
  status: string;
  latency_ms: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cost_usd?: number | null;
}

export interface ChatDirectorMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  timecode_jump?: number | null;
  suggested_action?: string | null;
  evidence_cards?: ChatDirectorEvidence[];
  scene_breakdown?: ChatSceneBreakdown[];
  edit_recommendations?: ChatEditRecommendation[];
  inference_trace?: ChatInferenceTrace[];
}

export interface ChatDirectorResponse {
  message: ChatDirectorMessage;
  provider_used?: string;
  model_used?: string;
  inference_trace?: ChatInferenceTrace[];
  scene_breakdown?: ChatSceneBreakdown[];
  edit_recommendations?: ChatEditRecommendation[];
  updated_blueprint?: Record<string, unknown>;
}

/**
 * Send natural creator query to the AI Director assistant.
 */
export async function sendChatMessage(
  projectId: string,
  message: string,
  mediaId?: string,
  provider: string = "auto",
): Promise<ChatDirectorResponse> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      media_id: mediaId || null,
      provider: provider || "auto",
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Chat query failed (${res.status})`);
  }
  return res.json();
}

/**
 * Fetch live AI and cloud infrastructure usage metrics.
 */
export async function fetchUsageTelemetry(): Promise<{
  total_ai_calls: number;
  estimated_total_cost_usd: number;
  modal: {
    calls: number;
    tokens_prompt: number;
    tokens_completion: number;
    total_tokens: number;
    compute_seconds: number;
    estimated_cost_usd: number;
    last_model_used: string | null;
    last_call_at: string | null;
  };
  meta: {
    calls: number;
    tokens_prompt: number;
    tokens_completion: number;
    total_tokens: number;
    compute_seconds: number;
    estimated_cost_usd: number;
    last_model_used: string | null;
    last_call_at: string | null;
  };
  baseten: {
    calls: number;
    tokens_prompt: number;
    tokens_completion: number;
    total_tokens: number;
    compute_seconds: number;
    estimated_cost_usd: number;
    last_model_used: string | null;
    last_call_at: string | null;
  };
  lambda_processor: {
    calls: number;
    tokens_prompt: number;
    tokens_completion: number;
    total_tokens: number;
    compute_seconds: number;
    estimated_cost_usd: number;
    last_model_used: string | null;
    last_call_at: string | null;
  };
  session_started_at: string;
  last_updated_at: string;
}> {
  const { apiBaseUrl } = getFrontendConfig();
  const res = await fetch(`${apiBaseUrl}/api/v1/telemetry/usage`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Telemetry fetch failed (${res.status})`);
  }
  return res.json();
}

/**
 * Analyze audio track beats, energy curve, and musical downbeats.
 */
export async function getAudioAnalysis(
  projectId: string,
  mediaId: string,
): Promise<{
  media_id: string;
  duration_seconds: number;
  sample_rate: number;
  peak_dbfs: number;
  mean_dbfs: number;
  estimated_bpm: number;
  beat_timestamps: number[];
  energy_timeline: Array<{ timestamp: number; normalized_energy: number }>;
  has_speech: boolean;
}> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(
    `${apiBaseUrl}/api/projects/${projectId}/media/${mediaId}/audio-analysis`,
    { headers },
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Audio beat analysis failed (${res.status})`);
  }
  return res.json();
}

export interface ExportSegmentRequest {
  start_seconds: number;
  end_seconds: number;
  title?: string;
  speed_multiplier?: number;
}

export interface ExportCutResponse {
  job_id: string;
  media_id: string;
  export_object_key: string;
  download_url: string;
  duration_seconds: number;
  file_size_bytes: number;
  segment_count: number;
  resolution: string;
  status: "completed" | "failed";
  rendered_at: string;
  expires_in_seconds: number;
}

export interface ExportTextOverlayRequest {
  text: string;
  color?: string;
  start_seconds: number;
  end_seconds: number;
  font_size?: number;
  position?: string;
}

/**
 * Render approved editing blueprint into trimmed, concatenated H.264 MP4 export.
 */
export async function renderExportCut(
  projectId: string,
  request: {
    media_id: string;
    segments: ExportSegmentRequest[];
    resolution?: "1080p" | "720p" | "source";
    include_audio?: boolean;
    text_overlays?: ExportTextOverlayRequest[];
  },
): Promise<ExportCutResponse> {
  const { apiBaseUrl } = getFrontendConfig();
  const headers = await getAuthHeaders();

  const res = await fetch(`${apiBaseUrl}/api/projects/${projectId}/export`, {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Export cut render failed (${res.status})`);
  }
  return res.json();
}
