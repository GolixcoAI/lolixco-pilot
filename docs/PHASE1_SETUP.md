# LolixCopilot — Phase 1 Manual Cloud Setup Guide

This guide details the step-by-step cloud configuration required to run Phase 1 with live Amazon S3 storage and Supabase PostgreSQL with Row Level Security.

> [!NOTE]
> Automated tests and local development run out of the box with zero cloud credentials using the built-in mock storage provider and local anonymous session fallback. Follow this guide only when connecting live AWS and Supabase services.

---

## 1. Supabase Configuration

### Step 1.1: Create or select a Supabase Project
1. Log in to [supabase.com](https://supabase.com).
2. Create a project in your preferred region.

### Step 1.2: Enable Anonymous Sign-ins (No Login UI)
LolixCopilot uses anonymous authentication so editors can start importing and editing immediately without login or signup friction.

1. In the Supabase Dashboard, go to **Authentication** > **Providers**.
2. Scroll to **Anonymous Sign-ins**.
3. Toggle **Enable Anonymous Sign-ins** to **ON**.
4. Save changes.

> [!IMPORTANT]
> Anonymous projects are tied to the browser's local storage session. If an editor clears browser storage or switches devices, a new anonymous session will be established. Account linking can be enabled in a future release.

### Step 1.3: Apply Database Migrations
1. In the Supabase Dashboard, open the **SQL Editor**.
2. Open [`supabase/migrations/20261030160559_phase1_projects_and_media.sql`](file:///home/vuld0/LolixCopilot/supabase/migrations/20261030160559_phase1_projects_and_media.sql).
3. Copy and run the entire SQL script (or let Supabase CLI / GitHub integration apply it).
4. Verify that `projects`, `media`, and `analyses` tables are created with `ROW LEVEL SECURITY` enabled.

### Step 1.4: Verify Row Level Security (RLS)
The migration configures strict ownership policies:
```sql
-- Authenticated users (including anonymous users) can only access their own records:
SELECT * FROM projects WHERE auth.uid() = user_id;
SELECT * FROM media WHERE auth.uid() = user_id;
```
To test cross-user isolation in the SQL Editor:
```sql
-- Simulate User A
SET LOCAL ROLE authenticated;
SET LOCAL "request.jwt.claim.sub" = '11111111-1111-1111-1111-111111111111';
SELECT * FROM projects; -- Returns only User A projects

-- Simulate User B
SET LOCAL "request.jwt.claim.sub" = '22222222-2222-2222-2222-222222222222';
SELECT * FROM projects; -- Returns only User B projects (User A records hidden)
```

### Step 1.5: Retrieve Supabase Keys & Configure Signing
Go to **Project Settings** > **API**:
- Copy **Project URL** -> `SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_URL`
- Copy **anon public key** -> `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Signing Configuration (Automatic Asymmetric JWKS or Symmetric HS256):**
  - **Modern Supabase (Recommended / Default):** Modern Supabase projects use asymmetric key pairs (RS256/ES256). The backend automatically fetches public keys from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. No secret needs to be stored on the server!
  - **Custom JWKS URL (Optional):** If using a custom gateway or self-hosted Supabase, configure `SUPABASE_JWKS_URL`.
  - **Legacy Symmetric HS256:** If your Supabase project signs tokens using symmetric HS256, go to **Project Settings** > **API** > **JWT Settings**, copy **JWT Secret**, and set `SUPABASE_JWT_SECRET` in `.env`.
  - **Audience & Issuer:** Audience defaults to `authenticated` (`SUPABASE_JWT_AUDIENCE`). Expected issuer can be set via `SUPABASE_JWT_ISSUER`.
  - **Strict Verification:** Unverified JWT claims are strictly rejected in all environments.

---

## 2. Amazon S3 Storage Configuration

> [!NOTE]
> **Status:** The dedicated bucket `lolixcopilot-media-247673029886-ap-south-1` is **PROVISIONED & VERIFIED** in region `ap-south-1`.

### Step 2.1: Verified AWS Identity & Bucket Baseline
- **Account:** `247673029886`
- **IAM Identity:** `arn:aws:iam::247673029886:user/rohan-admin` (Standard IAM User, not root)
- **Region:** `ap-south-1` (Mumbai)
- **Dedicated Bucket:** `lolixcopilot-media-247673029886-ap-south-1`
- **Isolation Guarantee:** Completely isolated from the unrelated `golixco-registration-media-247673029886` bucket.

### Step 2.2: S3 Setup Script
The idempotent setup script is located in [`scripts/aws/setup_media_bucket.sh`](file:///home/vuld0/LolixCopilot/scripts/aws/setup_media_bucket.sh).

- **Dry-run mode (Default):**
  ```bash
  ./scripts/aws/setup_media_bucket.sh --dry-run
  ```
- **Apply mode (Mutating, requires confirmation):**
  ```bash
  ./scripts/aws/setup_media_bucket.sh --apply --bucket lolixcopilot-media-247673029886-ap-south-1 --region ap-south-1
  ```

### Step 2.3: Verified Cloud Security Settings
The bucket has been provisioned and verified with:
- **S3 Block Public Access:** All 4 settings verified `true` (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`).
- **Server-Side Encryption:** Default `SSE-S3` (`AES256`) with `BucketKeyEnabled=true`.
- **CORS Configuration:** [`scripts/aws/cors.json`](file:///home/vuld0/LolixCopilot/scripts/aws/cors.json) verified for `http://localhost:3000` and `https://*.lolixco.com` (methods `PUT`, `GET`, `HEAD`).
- **7-Day Auto-Retention:** [`scripts/aws/lifecycle.json`](file:///home/vuld0/LolixCopilot/scripts/aws/lifecycle.json) verified with active rule `ExpireUserFootageAfter7Days` expiring objects under `users/` after 7 days, and aborting incomplete multipart uploads after 1 day.
- **Resource Tags:** `Project=LolixCopilot`, `ManagedBy=setup_media_bucket.sh`, `Retention=7d`.

### Step 2.4: Least-Privilege IAM Policy Template
For future production or worker roles, use [`scripts/aws/iam_policy.json`](file:///home/vuld0/LolixCopilot/scripts/aws/iam_policy.json):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LolixCopilotMediaObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::lolixcopilot-media-247673029886-ap-south-1/users/*"
    },
    {
      "Sid": "LolixCopilotBucketMetadataInspection",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:GetBucketCORS",
        "s3:GetLifecycleConfiguration"
      ],
      "Resource": "arn:aws:s3:::lolixcopilot-media-247673029886-ap-south-1"
    }
  ]
}
```
*(Note: `s3:HeadObject` is not an IAM action; `s3:GetObject` correctly grants permissions for both object retrieval and header/metadata checks).*

### Step 2.5: Storage Key Privacy Architecture
- S3 object keys are generated as: `users/{user_id}/projects/{project_id}/media/{media_id}/{random_token}.{ext}`
- Components `{user_id}`, `{project_id}`, `{media_id}` are strictly validated UUIDs.
- `{ext}` is strictly validated against `{"mp4", "mov", "webm"}`.
- `{random_token}` is a cryptographically generated 32-character hex identifier.
- The user's original filename is **never** included in the storage key; it is stored solely in PostgreSQL metadata.

### Step 2.6: Potential AWS Costs & Credit Consumption
- **Storage:** S3 Standard storage is ~$0.023 / GB-month in `ap-south-1`.
- **Requests:** ~$0.005 per 1,000 `PUT` requests, ~$0.0004 per 1,000 `GET` requests.
- **Data Transfer OUT:** Ingress is free; internet egress is charged after the first 100 GB/month.
- **Promotional Credits:** The bucket provision itself incurred $0.00. Future uploads will draw from the account's $120 promotional credit pool. The 7-day lifecycle rule guarantees automatic cleanup.

### Step 2.7: Credential Separation
- **Local Development:** The backend automatically leverages boto3's standard credential provider chain (`~/.aws/credentials` or `AWS_PROFILE`). Developers do not need to paste raw access keys into `.env`.
- **Production / Modal:** Production workloads should use assumed IAM roles or temporary environment secrets injected securely via the cloud platform (e.g., Modal Secrets), never long-lived developer desktop credentials.

---

## 3. Local Environment Setup

Create `.env` in the repository root (ignored by git):

```bash
# Frontend public config
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Backend private secrets
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
AWS_REGION=ap-south-1
AWS_S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 4. Starting and Testing the Application

1. **Start backend server:**
   ```bash
   .venv/bin/uvicorn app.main:app --app-dir backend --port 8000 --reload
   ```

2. **Start frontend development server:**
   ```bash
   npm --prefix frontend run dev
   ```

3. **Verify Upload & Persistence Flow:**
   - Open [http://localhost:3000](http://localhost:3000).
   - Click **+ Import** in the Project Media bin.
   - Choose a video file (`.mp4`, `.mov`, `.webm`, under 100 MB).
   - Observe real honest upload progress percentage in the clip thumbnail.
   - Once verified, observe the clip loaded into the central 4K monitor.
   - Click **Play** or press `Space` to preview.
   - Refresh the browser (`F5` / `Ctrl+R`): observe that the project and uploaded video metadata restore automatically.
   - Click the trash icon on the clip: verify the asset and S3 object are deleted.

---

## 5. Automated Tests Without Cloud Credentials

All automated tests use dependency injection test doubles:
- Authentication is verified using synthetic test JWTs and mocked tokens.
- Storage operations use `MockStorageService` in memory.
- Zero network requests are made to AWS or Supabase during test runs.

Run all tests anytime:
```bash
npm run check:all
```

---

## 6. Baseten AI Provider Setup & Controlled First Smoke Test

LolixCopilot integrates Baseten ($100 promotional credits) as the primary provider for Meta's `meta-models/muse-spark-open-1026`.

### Step 6.1: Server-Side Configuration

In your server `.env` (never commit secrets to Git or frontend bundles):
```bash
# Enable Baseten inference
AI_PROVIDER=baseten
BASETEN_API_KEY=your_baseten_api_key_here
BASETEN_BASE_URL=https://inference.baseten.co/v1
BASETEN_MODEL=meta-models/muse-spark-open-1026
AI_REQUEST_TIMEOUT_SECONDS=120
AI_MAX_RETRIES=2
```

> [!IMPORTANT]
> Keep `AI_PROVIDER=mock` during automated tests and initial development to avoid consuming credits. Only set `AI_PROVIDER=baseten` when explicitly conducting a live inference test.

### Step 6.2: Controlled First Smoke Test Procedure

To verify live model inference without credit waste:
1. **Prepare short, non-sensitive test media:**
   Use a short 5-15 second video under 15 MB.
2. **Start the backend server locally:**
   ```bash
   .venv/bin/uvicorn app.main:app --app-dir backend --port 8000
   ```
3. **Verify provider initialization via health/options check:**
   Ensure no 500 startup errors are emitted.
4. **Issue a single, controlled test request using the client or curl:**
   - Verify the short-lived S3 URL resolves.
   - Send `confirmed_baseten_consent: true`.
   - Observe request latency, token consumption, and response structure.
5. **Verify structured response validation:**
   Confirm that Baseten returns a valid JSON string adhering to the `EditingBlueprint` schema.
6. **Check Baseten Dashboard:**
   Inspect credit usage and latency metrics in the Baseten console.

---

## 7. Supabase GitHub Integration & Multi-Region Topology

### Step 7.1: Supabase GitHub Integration Settings

LolixCopilot repository is configured for native Supabase integration via the root `supabase/` directory:

- **Supabase Project Reference:** `fhfkjviishfvfyawfckh`
- **GitHub Repository:** `GolixcoAI/lolixco-pilot`
- **Working Directory:** `.` (repository root)
- **Production Branch:** `main`
- **Automatic Production Deployment:** Initially disabled (enable only after manual migration review).
- **Migration Directory:** `supabase/migrations/`
- **Canonical Migration:** `supabase/migrations/20261030160559_phase1_projects_and_media.sql`
- **Project Configuration:** `supabase/config.toml` (contains project reference, enables anonymous sign-ins, and enforces 100MiB storage limits without raw secrets).

### Step 7.2: Region Decision — Final (Singapore + Mumbai)

LolixCopilot intentionally retains the existing Supabase project in Singapore with AWS S3 in Mumbai:

- **Supabase Project:** Singapore (`ap-southeast-1`), Project ID `fhfkjviishfvfyawfckh`
- **AWS S3 Storage:** Mumbai (`ap-south-1`), Bucket `lolixcopilot-media-247673029886-ap-south-1`

#### Latency & Data-Transfer Analysis
- **Metadata Traffic:** Supabase handles authentication and structured project metadata (small JSON documents, typically 2-10 KB). The round-trip ping between Mumbai and Singapore is ~30-50 ms, which is negligible for UI responsiveness.
- **Media Binary Traffic:** Heavy video files (10-100 MB) are uploaded directly from the browser to the dedicated private S3 bucket in Mumbai via presigned PUT URLs, and streamed directly from S3 via presigned GET URLs.
- **Cost & Performance Protection:** No video binary data ever traverses cloud regions or passes through Supabase database connections. There are zero inter-region data transfer egress penalties for video media.

### Step 7.3: GitHub HTTP 403 Permission Resolution

The previous local attempt to push to `origin/main` (`https://github.com/GolixcoAI/lolixco-pilot.git`) returned:
`HTTP 403: Permission to GolixcoAI/lolixco-pilot.git denied to Golixco`

This occurred because the local Git credentials (`Golixco`) lacked `Write` collaborator permissions on the repository `GolixcoAI/lolixco-pilot`.

**Safest Resolution Options (User-Managed):**
1. **GitHub Collaborator Invite (Recommended):**
   In the GitHub repository settings for `GolixcoAI/lolixco-pilot` (`Settings` > `Collaborators` or Organization team settings), grant `Write` or `Admin` role to the GitHub user `Golixco`.
2. **Personal Access Token (PAT) Scope:**
   If using a personal access token for `Golixco`, verify that the token has the `repo` scope enabled (`Contents: Read and write`).
3. **SSH Remote:**
   If the organization requires SSH keys, configure an SSH key with write permissions and update the remote:
   ```bash
   git remote set-url origin git@github.com:GolixcoAI/lolixco-pilot.git
   ```
*Note: Under zero-credit-consumption rules, no credentials or force-pushes will ever be generated or attempted automatically.*
