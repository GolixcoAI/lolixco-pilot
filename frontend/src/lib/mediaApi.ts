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
  provider?: "baseten" | "meta" | "mock",
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

