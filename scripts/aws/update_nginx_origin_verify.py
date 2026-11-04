"""Configure Nginx to validate CloudFront custom origin header X-Lolix-Origin-Verify."""

import time
import boto3

def main():
    ssm = boto3.client("ssm", region_name="ap-south-1")
    instance_id = "i-06401964b15024c7e"

    script = """#!/bin/bash
set -xe
cat << 'EOF' > /etc/nginx/sites-available/lolixcopilot
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 120M;

    # Check CloudFront origin verification header (defense-in-depth)
    if ($http_x_lolix_origin_verify != "lolix_prod_edge_ap_south_1_v1") {
        return 403 "Forbidden: Direct origin access is not permitted.\\n";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

nginx -t
systemctl reload nginx
echo "Nginx updated and reloaded with X-Lolix-Origin-Verify check."
"""

    res = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script]}
    )
    cmd_id = res["Command"]["CommandId"]
    print("Sent SSM command:", cmd_id)

    for _ in range(12):
        time.sleep(2)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        status = inv["Status"]
        print("SSM Status:", status)
        if status in ("Success", "Failed", "TimedOut"):
            if status != "Success":
                print("STDOUT:\n", inv.get("StandardOutputContent"))
                print("STDERR:\n", inv.get("StandardErrorContent"))
                raise RuntimeError("Failed to update Nginx")
            print("Output:\n", inv.get("StandardOutputContent"))
            break

if __name__ == "__main__":
    main()

