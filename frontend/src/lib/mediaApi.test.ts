import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getOrCreateProject,
  listProjectMedia,
  requestPresignedUpload,
  confirmUpload,
  deleteMedia,
  getPreviewUrl,
  uploadFileToS3,
  analyzeMedia,
} from "./mediaApi";

describe("Media API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches or creates active project", async () => {
    const mockProject = {
      id: "proj-123",
      user_id: "user-456",
      name: "Test Project",
      aspect_ratio: "9:16",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [mockProject],
    } as Response);

    const project = await getOrCreateProject();
    expect(project.id).toBe("proj-123");
    expect(project.name).toBe("Test Project");
  });

  it("lists project media assets", async () => {
    const mockMedia = [
      {
        id: "media-1",
        project_id: "proj-123",
        original_filename: "raw.mp4",
        status: "verified",
      },
    ];

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockMedia,
    } as Response);

    const list = await listProjectMedia("proj-123");
    expect(list.length).toBe(1);
    expect(list[0].id).toBe("media-1");
  });

  it("requests presigned S3 upload URL", async () => {
    const mockPresign = {
      media_id: "media-1",
      project_id: "proj-123",
      s3_key: "users/u/projects/p/media/m/asset.mp4",
      upload_url: "https://mock-s3.localhost/uploads/asset.mp4",
      expires_in: 900,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPresign,
    } as Response);

    const res = await requestPresignedUpload("proj-123", "raw.mp4", "video/mp4", 1024);
    expect(res.upload_url).toBe(mockPresign.upload_url);
    expect(res.media_id).toBe("media-1");
  });

  it("simulates mock S3 direct upload with progress", async () => {
    const progressReports: number[] = [];
    const mockFile = new File(["test-content"], "test.mp4", { type: "video/mp4" });

    await uploadFileToS3(
      "https://mock-s3.localhost/uploads/asset.mp4",
      mockFile,
      "video/mp4",
      (pct) => progressReports.push(pct),
    );

    expect(progressReports.length).toBeGreaterThan(0);
    expect(progressReports[progressReports.length - 1]).toBe(100);
  });

  it("confirms upload with server", async () => {
    const mockConfirmed = {
      id: "media-1",
      status: "verified",
      verified_size_bytes: 1024,
      preview_url: "https://mock-s3.localhost/stream/asset.mp4",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockConfirmed,
    } as Response);

    const confirmed = await confirmUpload("proj-123", "media-1", 12.5);
    expect(confirmed.status).toBe("verified");
    expect(confirmed.preview_url).toBeDefined();
  });

  it("retrieves temporary preview URL", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        preview_url: "https://mock-s3.localhost/stream/asset.mp4?token=abc",
        expires_in: 900,
        status: "verified",
      }),
    } as Response);

    const url = await getPreviewUrl("proj-123", "media-1");
    expect(url).toContain("mock-s3.localhost");
  });

  it("deletes media asset from project", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, media_id: "media-1" }),
    } as Response);

    await expect(deleteMedia("proj-123", "media-1")).resolves.toBeUndefined();
  });

  it("submits video analysis request with Baseten authorization", async () => {
    const mockAnalysisResponse = {
      id: "analysis-999",
      project_id: "proj-123",
      media_id: "media-1",
      provider: "baseten",
      model: "meta-models/muse-spark-open-1026",
      blueprint: {
        title: "Test Cut",
        creative_intent: "High energy",
        summary: "Fast paced cut",
        target_duration_seconds: 30,
        aspect_ratio: "9:16",
        hook: "Jump cut at start",
        scenes: [],
        sequence_rationale: "Smooth build",
        ending_suggestion: "Fade out",
        caveats: [],
      },
      created_at: new Date().toISOString(),
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalysisResponse,
    } as Response);

    const res = await analyzeMedia(
      "proj-123",
      "media-1",
      {
        title: "Test Cut",
        description: "Test description",
        style: "Kinetic",
        pacing: "fast",
        aspectRatio: "9:16",
        targetDuration: 30,
      },
      true,
    );

    expect(res.id).toBe("analysis-999");
    expect(res.provider).toBe("baseten");
    expect(res.blueprint.title).toBe("Test Cut");

    const fetchCalls = vi.mocked(global.fetch).mock.calls;
    const lastCall = fetchCalls[fetchCalls.length - 1];
    expect(lastCall[0]).toContain("/api/projects/proj-123/media/media-1/analyze");
    const body = JSON.parse(lastCall[1]?.body as string);
    expect(body.confirmed_baseten_consent).toBe(true);
    expect(body.brief.title).toBe("Test Cut");
  });

  it("handles analysis error when server rejects request", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "User authorization required: you must explicitly consent" }),
    } as Response);

    await expect(
      analyzeMedia(
        "proj-123",
        "media-1",
        {
          title: "Test",
          description: "Desc",
          style: "Fast",
          pacing: "fast",
          aspectRatio: "9:16",
          targetDuration: 30,
        },
        false,
      ),
    ).rejects.toThrow("User authorization required");
  });
});

