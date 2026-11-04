import boto3
import time
import sys

def run_deploy():
    ssm = boto3.client('ssm', region_name='ap-south-1')
    
    script_commands = [
        "#!/bin/bash",
        "set -xe",
        "exec > >(tee /var/log/lolixcopilot-deploy.log) 2>&1",
        "echo '=== Starting LolixCopilot In-Place Upgrade ==='",
        "aws s3 cp s3://lolixcopilot-media-247673029886-ap-south-1/releases/release.tar.gz /tmp/release.tar.gz --region ap-south-1",
        "tar -xzf /tmp/release.tar.gz -C /opt/lolixcopilot",
        "rm -f /tmp/release.tar.gz",
        """/opt/lolixcopilot/.venv/bin/python3 - << 'PYEOF'
import boto3, json, os

client = boto3.client('secretsmanager', region_name='ap-south-1')
resp = client.get_secret_value(SecretId='lolixcopilot/production/backend')
data = json.loads(resp['SecretString'])

commit_sha = 'd97b4313f88f28f110c793ff433433df7da4fb93'
try:
    with open('/opt/lolixcopilot/RELEASE_METADATA.json') as f:
        meta = json.load(f)
        commit_sha = meta.get('commit_sha', commit_sha)
except Exception:
    pass

with open('/opt/lolixcopilot/.env', 'w') as f:
    for k, v in data.items():
        if k not in ['MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET']:
            f.write(f'{k}={v}\\n')
    f.write(f'GIT_COMMIT_SHA={commit_sha}\\n')
os.chmod('/opt/lolixcopilot/.env', 0o600)

if data.get('MODAL_TOKEN_ID') and data.get('MODAL_TOKEN_SECRET'):
    modal_toml = f'''[golixco40]
token_id = "{data['MODAL_TOKEN_ID']}"
token_secret = "{data['MODAL_TOKEN_SECRET']}"
active = true
'''
    with open('/root/.modal.toml', 'w') as f:
        f.write(modal_toml)
    os.chmod('/root/.modal.toml', 0o600)

print('Successfully imported credentials from Secrets Manager. Commit:', commit_sha)
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
        "echo '=== Deployment Finished Successfully ==='"
    ]
    
    combined_script = "\n".join(script_commands)
    
    cmd = ssm.send_command(
        InstanceIds=['i-06401964b15024c7e'],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [combined_script]},
        TimeoutSeconds=600
    )
    cmd_id = cmd['Command']['CommandId']
    print(f"Sent SSM upgrade command: {cmd_id}")
    return cmd_id

if __name__ == '__main__':
    run_deploy()
