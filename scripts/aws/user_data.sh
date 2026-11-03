#!/bin/bash
set -xe
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "=== Starting LolixCopilot Deployment ==="

# 0. Set up 2GB swap space for smooth builds
fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 1. Update system packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl wget git unzip tar build-essential ffmpeg python3 python3-pip python3-venv nginx

# 1.1 Install AWS CLI v2
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    unzip -q /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
fi

# 2. Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# 3. Create app directory
mkdir -p /opt/lolixcopilot
cd /opt/lolixcopilot

# 4. Fetch release package and env from private S3 using instance IAM credentials
aws s3 cp s3://lolixcopilot-media-247673029886-ap-south-1/releases/release.tar.gz /tmp/release.tar.gz --region ap-south-1
tar -xzf /tmp/release.tar.gz -C /opt/lolixcopilot
aws s3 cp s3://lolixcopilot-media-247673029886-ap-south-1/releases/app.env /opt/lolixcopilot/.env --region ap-south-1
cp /opt/lolixcopilot/.env /opt/lolixcopilot/backend/.env
cp /opt/lolixcopilot/.env /opt/lolixcopilot/frontend/.env.production

# 5. Set up Python backend
python3 -m venv /opt/lolixcopilot/.venv
/opt/lolixcopilot/.venv/bin/pip install --upgrade pip
/opt/lolixcopilot/.venv/bin/pip install -e /opt/lolixcopilot/backend

# 6. Set up Node.js frontend
cd /opt/lolixcopilot/frontend
export NEXT_PUBLIC_API_BASE_URL=""
npm ci
npm run build

# 7. Configure Systemd Services
cat << 'EOF' > /etc/systemd/system/lolixcopilot-backend.service
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

cat << 'EOF' > /etc/systemd/system/lolixcopilot-frontend.service
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

systemctl daemon-reload
systemctl enable --now lolixcopilot-backend.service
systemctl enable --now lolixcopilot-frontend.service

# 8. Configure Nginx Reverse Proxy
cat << 'EOF' > /etc/nginx/sites-available/lolixcopilot
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 120M;

    # API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Docs Proxy
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host $host;
    }

    # Frontend Proxy
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/lolixcopilot /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

echo "=== Deployment Completed Successfully ==="
