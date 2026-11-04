# LolixCopilot — Security Architecture Specification

This document details the security principles, access control policies, and infrastructure hardening implemented across LolixCopilot.

## 1. Zero Credential Exposure in Browser

LolixCopilot strictly separates public browser client configuration from privileged server-side secrets:

- **Browser Client Config:** Only public, non-privileged values are provided to the Next.js frontend:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (subject to Postgres Row-Level Security)
  - `NEXT_PUBLIC_API_BASE_URL`
- **Protected Server-Side Secrets:** The following credentials are never transmitted to the browser, never baked into client bundles, and never logged:
  - `MODEL_API_KEY` (Meta Model API)
  - `BASETEN_API_KEY` (Baseten Inference API)
  - `MODAL_TOKEN_ID` & `MODAL_TOKEN_SECRET` (Modal GPU Infrastructure)
  - `SUPABASE_SERVICE_ROLE_KEY`

All API keys are stored in AWS Secrets Manager (`lolixcopilot/production/backend`) and retrieved at runtime via IAM instance profiles.

---

## 2. Storage Security & Presigned URLs

- **Private S3 Bucket:** The media storage bucket (`s3://lolixcopilot-media-247673029886-ap-south-1`) enforces `BlockPublicAcls=true`, `IgnorePublicAcls=true`, `BlockPublicPolicy=true`, and `RestrictPublicBuckets=true`.
- **Short-Lived Presigned PUT URLs:** Media uploads bypass application servers and stream directly from the browser to Amazon S3 using presigned PUT URLs with a 900-second (15-minute) Time-to-Live (TTL).
- **Short-Lived Presigned GET URLs:** Video playback streams and generated proxy cuts are accessed exclusively through presigned GET URLs generated on demand with 15-minute TTLs. Presigned URLs are never stored in the database.
- **Server-Side Validation:** The backend validates file existence, byte size, duration, and codec metadata via `ffprobe` in AWS Lambda before initiating model inference.

---

## 3. Database Security & Row-Level Security (RLS)

All database tables in Supabase PostgreSQL enforce Row-Level Security:

- **`projects` Table:** Users can only query, insert, update, or delete projects where `owner_id = auth.uid()`.
- **`media_assets` Table:** Access is restricted to users who own the parent project (`auth.uid() = projects.owner_id`).
- **`analysis_jobs` Table:** Job results and editing blueprints are strictly isolated to the owning user.
- **JWT Verification:** The FastAPI backend verifies the authenticity of incoming Supabase JWT bearer tokens against the official JWKS endpoint (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`), validating issuer, audience, and signature algorithms.

---

## 4. Network and Host Hardening

- **Loopback Binding:** Both Next.js (`127.0.0.1:3000`) and FastAPI (`127.0.0.1:8000`) listen exclusively on loopback interfaces.
- **Origin Isolation via Managed Prefix List:** Port 80 ingress on the AWS Security Group (`sg-05527b9af5578424f`) is restricted exclusively to the AWS CloudFront Origin-Facing Managed Prefix List (`pl-9aa247f3`). Direct public ingress `0.0.0.0/0` on ports 80 and 443 is revoked; attempts to access the EC2 IP directly time out.
- **Closed Application Ingress:** Inbound firewall rules for ports 3000 and 8000 are revoked. Application services listen exclusively on loopback interfaces (`127.0.0.1:3000` and `127.0.0.1:8000`).
- **Edge HTTPS:** CloudFront provides TLS 1.3 encryption with automatic HTTP-to-HTTPS redirection.
- **No Open SSH Port:** Administrative access to the EC2 host is restricted to AWS Systems Manager Session Manager, eliminating public SSH exposure on port 22.
