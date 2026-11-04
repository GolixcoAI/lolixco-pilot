# LolixCopilot — Operational Troubleshooting Guide

This guide outlines diagnostic procedures and resolutions for common issues encountered during local development and production deployment.

## 1. Local Development Issues

### ModuleNotFoundError When Running Pytest
- **Symptom:** `ModuleNotFoundError: No module named 'boto3'` or `No module named 'modal'` when running `pytest`.
- **Cause:** Invoking system Python rather than the project virtual environment.
- **Resolution:** Always invoke pytest through the local virtual environment:
  ```bash
  ./.venv/bin/pytest backend/tests
  ```

### Frontend Port Conflict
- **Symptom:** `Error: listen EADDRINUSE: address already in use :::3000`.
- **Cause:** Another Next.js instance or background process is occupying port 3000.
- **Resolution:** Identify and terminate the conflicting process:
  ```bash
  lsof -i :3000
  kill -9 <PID>
  npm run dev --prefix frontend
  ```

---

## 2. Production AWS Issues

### Inspecting Production Services via AWS SSM
To diagnose issues on the production EC2 host without opening SSH ports, use AWS Systems Manager:

```bash
aws ssm send-command \
  --instance-ids i-06401964b15024c7e \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["systemctl status lolixcopilot-backend lolixcopilot-frontend nginx --no-pager"]}' \
  --region ap-south-1
```

### Backend Service Restart
If backend configuration or secrets are updated:

```bash
aws ssm send-command \
  --instance-ids i-06401964b15024c7e \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["systemctl restart lolixcopilot-backend"]}' \
  --region ap-south-1
```

### Nginx Configuration Verification
If HTTP proxying returns 502 Bad Gateway:

1. Verify backend is running on `127.0.0.1:8000`:
   ```bash
   curl -I http://127.0.0.1:8000/api/health
   ```
2. Check Nginx error logs:
   ```bash
   tail -n 50 /var/log/nginx/error.log
   ```
3. Test and reload Nginx configuration:
   ```bash
   nginx -t && systemctl reload nginx
   ```

---

## 3. Media Upload and S3 Presigned URL Issues

### Presigned Upload Returns HTTP 403 Forbidden
- **Cause:** S3 bucket CORS configuration is missing the request origin, or IAM role lacks `s3:PutObject`.
- **Resolution:**
  - Verify CloudFront or localhost origin is in `scripts/aws/cors.json`.
  - Re-apply CORS policy:
    ```bash
    aws s3api put-bucket-cors --bucket lolixcopilot-media-247673029886-ap-south-1 --cors-configuration file://scripts/aws/cors.json
    ```

### Video Playback Fails with HTTP 410 Gone
- **Cause:** Media asset exceeds the 7-day retention period.
- **Resolution:** This is the intended privacy lifecycle. Upload a new copy of the source footage to generate a fresh 7-day session.
