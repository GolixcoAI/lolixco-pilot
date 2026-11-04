# LolixCopilot — AWS Production Deployment Specification

**Cloud Provider:** Amazon Web Services (AWS)  
**Primary Region:** `ap-south-1` (Mumbai)  
**Application Architecture:** CloudFront HTTPS Edge -> EC2 Nginx Reverse Proxy -> Next.js 16 (Port 3000) & FastAPI (Port 8000) -> AWS Lambda & Private S3

---

## 1. Architecture Topology

```
[User Browser]
       │
       ▼ (HTTPS / TLS 1.3)
[Amazon CloudFront Distribution]
  (d2ikihwmt96m58.cloudfront.net)
       │
       ▼ (Port 80 HTTP Reverse Proxy)
[Amazon EC2 Instance: t3.small (Ubuntu 24.04 LTS)]
  ├── Nginx Reverse Proxy (Port 80)
  ├── Next.js 16 Web Workstation (127.0.0.1:3000)
  └── FastAPI Python ASGI Backend (127.0.0.1:8000)
       │
       ├── IAM Role: LolixCopilotAppRole (Instance Profile)
       │     └── AWS Secrets Manager: lolixcopilot/production/backend
       │
       ├── Asynchronous Invocation ──> [AWS Lambda: lolixcopilot-media-processor]
       │                                     └── FFmpeg 720p Proxy, Beats, Cuts
       │
       └── Presigned PUT / GET ──────> [Amazon S3: lolixcopilot-media-247673029886-ap-south-1]
                                             └── Private, Block Public Access, AES-256
```

---

## 2. Infrastructure Inventory

### 2.1 Compute: EC2 Workstation Host
- **Instance ID:** `i-06401964b15024c7e`
- **Instance Type:** `t3.small` (2 vCPUs, 2 GiB RAM + 2 GiB swap space, 30 GB gp3 root storage)
- **AMI:** Ubuntu 24.04 LTS Noble (`ami-0fc5120b2d80d4749`)
- **Public IPv4:** `3.110.25.215`
- **Public DNS:** `ec2-3-110-25-215.ap-south-1.compute.amazonaws.com`

#### Host Sizing Verification
Production telemetry confirms `t3.small` operates with significant resource headroom:
- **System Memory:** 1.9 GiB total; ~774 MiB utilized by Next.js + FastAPI + Nginx; **1.1 GiB available**.
- **Swap Space:** 2.0 GiB configured; < 1 MiB utilized.
- **Disk Storage:** 29 GiB gp3 total; 7.2 GiB utilized (26%); **21 GiB available**.
- **CPU Utilization:** Idles below 2% when not compiling; serverless workloads (FFmpeg, model inference) execute on Lambda and Modal, keeping the host completely unburdened.

### 2.2 Network and Edge Security
- **CloudFront HTTPS Distribution ID:** `E3Q0GBE3CQ8BSW`
- **Public HTTPS Domain:** `https://d2ikihwmt96m58.cloudfront.net`
- **SSL / TLS Certificate:** Valid Amazon Trust Services wildcard certificate (`*.cloudfront.net`).
- **Viewer Protocol Policy:** `redirect-to-https` (enforces encrypted transport).
- **Cache Policies:**
  - Cache Policy: `Managed-CachingDisabled` (`4135ea2d-6df8-44a3-9df3-4b5a84be39ad`) ensures dynamic API calls and workstation edits are never cached inappropriately.
  - Origin Request Policy: `Managed-AllViewerExceptHostHeader` (`b689b0a8-53d0-40ab-baf2-68738e2966ac`) forwards all authorization headers, cookies, and query strings.
- **Security Group:** `sg-05527b9af5578424f` (`lolixcopilot-web-sg`)
  - **Port 80 (HTTP):** Ingress restricted exclusively to AWS CloudFront Origin-Facing Managed Prefix List (`pl-9aa247f3`). Direct public ingress `0.0.0.0/0` is revoked; direct connection attempts to the EC2 IP time out.
  - **Port 443 (HTTPS):** Ingress revoked (CloudFront terminates TLS 1.3 at the edge; EC2 origin communication uses port 80 over the AWS backbone).
  - **Port 3000 (Next.js):** **Revoked / Closed to Internet** (bound to loopback `127.0.0.1:3000`).
  - **Port 8000 (FastAPI):** **Revoked / Closed to Internet** (bound to loopback `127.0.0.1:8000`).
  - **Port 22 (SSH):** **Closed**. Instance administration is performed via AWS Systems Manager Session Manager.

---

## 3. Automated Secrets Manager Integration

LolixCopilot eliminates plaintext credential storage in Git, deployment packages, and environment files through AWS Secrets Manager:

- **Secret ARN:** `arn:aws:secretsmanager:ap-south-1:247673029886:secret:lolixcopilot/production/backend`
- **Managed Variables:**
  - `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWKS_URL`
  - `MODEL_API_KEY` (Meta Model API)
  - `BASETEN_API_KEY`, `BASETEN_BASE_URL`, `BASETEN_MODEL`
  - `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
  - `AWS_REGION`, `AWS_S3_BUCKET`, `AWS_LAMBDA_MEDIA_FUNCTION`
- **IAM Authorization:** The EC2 instance profile (`LolixCopilotInstanceProfile`) uses role `LolixCopilotAppRole` with least-privilege permission `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:ap-south-1:247673029886:secret:lolixcopilot/production/backend*`.
- **Runtime Injection:** During service startup, the deployment loader retrieves the secret via the instance role, writes the environment configuration with strict permissions (`chmod 600`), and launches the systemd services.

---

## 4. Media Storage and Serverless Processing

### 4.1 Private Amazon S3 Storage
- **Bucket:** `s3://lolixcopilot-media-247673029886-ap-south-1`
- **Access Control:** 100% Private. Public Access Block is enabled for all four ACL and policy controls.
- **Upload Flow:** Browser uploads directly to S3 via short-lived presigned PUT URLs (15-minute validity).
- **Playback Flow:** Video and preview streams are served via short-lived presigned GET URLs.
- **Retention Lifecycle:** Objects under `users/` automatically expire and are purged by AWS S3 after 7 days (`ExpireUserFootageAfter7Days`).

### 4.2 AWS Lambda Media Processor
- **Function Name:** `lolixcopilot-media-processor`
- **Runtime:** Python 3.12 with containerized FFmpeg / ffprobe layer (`zip` package).
- **Memory & Timeout:** 2048 MB RAM, 300-second timeout, 2048 MB ephemeral storage.
- **Responsibilities:**
  - Video container inspection and metadata extraction.
  - H.264 / AAC 720p proxy generation for browser playback.
  - Audio waveform and beat transient extraction.
  - Final cut rendering with subtitle overlays burned via `libass`.

---

## 5. Systemd Service Configuration

Two persistent systemd services manage the application on EC2:

### `lolixcopilot-backend.service`
```ini
[Unit]
Description=LolixCopilot FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lolixcopilot
EnvironmentFile=/opt/lolixcopilot/.env
ExecStart=/opt/lolixcopilot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### `lolixcopilot-frontend.service`
```ini
[Unit]
Description=LolixCopilot Next.js Frontend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lolixcopilot/frontend
Environment=PORT=3000
Environment=NODE_ENV=production
Environment=NEXT_PUBLIC_API_BASE_URL=
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
