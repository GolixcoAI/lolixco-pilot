# LolixCopilot — Privacy and Data Retention Policy

This document outlines LolixCopilot's data governance principles, user media protections, and cloud retention policies.

## 1. Core Privacy Commitments

1. **User Ownership:** Creators retain complete ownership and intellectual property rights over all raw footage, audio tracks, editing blueprints, and exported videos processed within LolixCopilot.
2. **Zero Automated Training:** LolixCopilot does not train, fine-tune, or adapt any AI models using user video footage or uploaded media without explicit, written opt-in consent.
3. **Data Minimization:** We collect and store only the minimal operational metadata required to deliver the video editing workstation experience (clip durations, resolutions, frame rates, and scene markers).

---

## 2. Retention and Automated Deletion

To protect creator privacy and maintain cost hygiene, LolixCopilot enforces an automated 7-day data retention lifecycle:

- **Database Expiration:** Every uploaded media asset records an `expires_at` timestamp set to `created_at + 7 days`. Once this boundary passes, the API returns HTTP 410 Gone for playback requests.
- **Automated S3 Purge:** An automated Amazon S3 Lifecycle Rule (`ExpireUserFootageAfter7Days`) permanently deletes raw video assets, proxy cuts, and audio stems from the private S3 bucket 7 days after upload.
- **Manual Deletion:** Creators can delete projects and associated media at any time from the workstation. Deletion immediately invalidates database records and schedules underlying S3 objects for immediate removal.

---

## 3. Third-Party Model Provider Disclosures

In accordance with the Meta Global AI Developer Hackathon guidelines and API provider policies:

- **Meta Model API:** When utilizing free developer credits on the Meta Model API, user requests may be processed under Meta's developer terms. A visible disclosure notice is presented in the workstation prior to media ingestion, advising creators not to upload sensitive, proprietary, or personal health footage during evaluation.
- **Modal and Baseten:** Footage processed through Modal and Baseten executes in ephemeral worker containers and is discarded immediately after keyframe analysis and audio extraction complete.
- **Telemetry and Logging:** Backend logs record operational performance metrics (inference latency, token counts, error status) but strictly redact video content, raw frame buffers, presigned URLs, and authentication tokens.
