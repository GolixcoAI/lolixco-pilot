"""LolixCopilot — Automated Production Deployment Upgrade Script.

Packages current repository state, uploads to private S3, deploys to EC2 via AWS SSM,
hydrates credentials from AWS Secrets Manager, builds frontend, restarts services,
and verifies public CloudFront health status.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import boto3
import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTANCE_ID = "i-06401964b15024c7e"
REGION = "ap-south-1"
S3_BUCKET = "lolixcopilot-media-247673029886-ap-south-1"
CLOUDFRONT_URL = "https://d2ikihwmt96m58.cloudfront.net"


def get_current_commit_sha() -> str:
    """Resolve current Git commit SHA."""
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def package_and_upload_release(commit_sha: str) -> str:
    """Create release tarball with RELEASE_METADATA.json and upload to S3."""
    print(f"Creating RELEASE_METADATA.json for commit {commit_sha}...")
    metadata = {
        "commit_sha": commit_sha,
        "branch": "feat/ai-editor-polish-aws-deploy",
        "version": "0.1.0",
        "environment": "production",
        "deployed_at": datetime.now(UTC).isoformat(),
    }
    meta_path = REPO_ROOT / "RELEASE_METADATA.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    tar_path = Path("/tmp/release.tar.gz")
    if tar_path.exists():
        tar_path.unlink()

    print("Building sanitized release tarball...")
    tar_cmd = [
        "tar",
        "-czf",
        str(tar_path),
        "--exclude=.git",
        "--exclude=.github",
        "--exclude=.next",
        "--exclude=.venv",
        "--exclude=node_modules",
        "--exclude=__pycache__",
        "--exclude=*.pyc",
        "--exclude=*.mp4",
        "--exclude=*.mov",
        "--exclude=*.webm",
        "--exclude=*.png",
        "--exclude=training/data/local_eval",
        "--exclude=training/data/raw",
        "-C",
        str(REPO_ROOT),
        ".",
    ]
    subprocess.run(tar_cmd, check=True)
    size_mb = tar_path.stat().st_size / (1024 * 1024)
    print(f"Release tarball built: {size_mb:.2f} MB")

    s3_key = "releases/release.tar.gz"
    print(f"Uploading tarball to s3://{S3_BUCKET}/{s3_key}...")
    s3 = boto3.client("s3", region_name=REGION)
    s3.upload_file(str(tar_path), S3_BUCKET, s3_key)
    print("Tarball uploaded successfully.")
    return s3_key


def deploy_via_ssm(commit_sha: str) -> None:
    """Execute in-place deployment on EC2 via SSM."""
    ssm = boto3.client("ssm", region_name=REGION)

    script_commands = [
        "#!/bin/bash",
        "set -xe",
        "exec > >(tee /var/log/lolixcopilot-deploy.log) 2>&1",
        "echo '=== Starting LolixCopilot Production Upgrade ==='",
        f"aws s3 cp s3://{S3_BUCKET}/releases/release.tar.gz /tmp/release.tar.gz --region {REGION}",
        "tar -xzf /tmp/release.tar.gz -C /opt/lolixcopilot",
        "rm -f /tmp/release.tar.gz",
        f"""/opt/lolixcopilot/.venv/bin/python3 - << 'PYEOF'
import boto3, json, os

client = boto3.client('secretsmanager', region_name='{REGION}')
resp = client.get_secret_value(SecretId='lolixcopilot/production/backend')
data = json.loads(resp['SecretString'])

commit_sha = '{commit_sha}'
try:
    with open('/opt/lolixcopilot/RELEASE_METADATA.json') as f:
        meta = json.load(f)
        commit_sha = meta.get('commit_sha', commit_sha)
except Exception:
    pass

with open('/opt/lolixcopilot/.env', 'w') as f:
    for k, v in data.items():
        if k not in ['MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET']:
            f.write(f'{{k}}={{v}}\\n')
    f.write(f'GIT_COMMIT_SHA={{commit_sha}}\\n')
os.chmod('/opt/lolixcopilot/.env', 0o600)

if data.get('MODAL_TOKEN_ID') and data.get('MODAL_TOKEN_SECRET'):
    modal_toml = f'''[golixco40]
token_id = "{{data['MODAL_TOKEN_ID']}}"
token_secret = "{{data['MODAL_TOKEN_SECRET']}}"
active = true
'''
    with open('/root/.modal.toml', 'w') as f:
        f.write(modal_toml)
    os.chmod('/root/.modal.toml', 0o600)

print(f'Successfully imported credentials from Secrets Manager. Target Commit: {{commit_sha}}')
PYEOF
""",
        "cd /opt/lolixcopilot",
        "/opt/lolixcopilot/.venv/bin/pip install -e /opt/lolixcopilot/backend",
        "cd /opt/lolixcopilot/frontend",
        "export NEXT_PUBLIC_API_BASE_URL=\"\"",
        "export NODE_PATH=/opt/lolixcopilot/frontend/node_modules",
        "unset NODE_ENV",
        "npm install --include=dev",
        "npm run build",
        """cat << 'EOF' > /etc/systemd/system/lolixcopilot-backend.service
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
EOF
""",
        """cat << 'EOF' > /etc/systemd/system/lolixcopilot-frontend.service
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
EOF
""",
        "systemctl daemon-reload",
        "systemctl restart lolixcopilot-backend",
        "systemctl restart lolixcopilot-frontend",
        "systemctl restart nginx",
        "sleep 4",
        "curl -s http://127.0.0.1:8000/api/health",
        "echo ''",
        "echo '=== Deployment Finished Successfully ==='",
    ]

    combined_script = "\n".join(script_commands)
    print(f"Triggering SSM RunShellScript on instance {INSTANCE_ID}...")
    cmd = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [combined_script]},
        TimeoutSeconds=600,
    )
    cmd_id = cmd["Command"]["CommandId"]
    print(f"SSM Command sent: {cmd_id}")

    # Wait for completion
    print("Waiting for deployment command to finish on EC2...")
    while True:
        time.sleep(5)
        res = ssm.get_command_invocation(
            CommandId=cmd_id,
            InstanceId=INSTANCE_ID,
        )
        status = res["Status"]
        print(f"SSM Status: {status}")
        if status in ("Success", "Failed", "TimedOut", "Cancelled"):
            if status != "Success":
                print("STDOUT:\n", res.get("StandardOutputContent", ""))
                print("STDERR:\n", res.get("StandardErrorContent", ""))
                raise RuntimeError(f"SSM execution failed with status: {status}")
            print("Deployment command succeeded on EC2.")
            print("Execution summary:\n", res.get("StandardOutputContent", "")[-500:])
            break


def verify_live_health(expected_sha: str) -> None:
    """Verify that CloudFront serves the expected commit SHA."""
    print(f"Verifying live CloudFront health endpoint at {CLOUDFRONT_URL}/api/health...")
    for attempt in range(1, 10):
        try:
            resp = httpx.get(f"{CLOUDFRONT_URL}/api/health", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                reported_sha = data.get("commit_sha", "")
                print(f"Attempt {attempt}: Received health response:")
                print(json.dumps(data, indent=2))
                if reported_sha == expected_sha:
                    print(f"SUCCESS: Reported commit SHA matches expected commit {expected_sha}!")
                    return
                print(f"Mismatch: reported {reported_sha} != expected {expected_sha}. Waiting 4s...")
            else:
                print(f"Attempt {attempt}: HTTP {resp.status_code}")
        except Exception as exc:
            print(f"Attempt {attempt} failed: {exc}")
        time.sleep(4)
    raise RuntimeError(f"Health verification failed: expected commit {expected_sha}")


def main() -> None:
    commit_sha = get_current_commit_sha()
    print(f"=== LOLIXCOPILOT UPGRADE SCRIPT ===")
    print(f"Current Git Commit: {commit_sha}")
    package_and_upload_release(commit_sha)
    deploy_via_ssm(commit_sha)
    verify_live_health(commit_sha)
    print("=== UPGRADE AND VERIFICATION COMPLETE ===")


if __name__ == "__main__":
    main()
