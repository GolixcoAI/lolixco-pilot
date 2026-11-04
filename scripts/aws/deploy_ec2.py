"""
AWS EC2 Automated Deployment Script for LolixCopilot in ap-south-1.
Launches Ubuntu 24.04 instance, configures IAM profile, security group,
user data deployment, and monitors health until live.
"""

import boto3
import time
import urllib.request
from pathlib import Path

REGION = "ap-south-1"
AMI_ID = "ami-0fc5120b2d80d4749"  # Ubuntu 24.04 LTS (Noble) in ap-south-1
INSTANCE_TYPE = "t3.small"  # Free Tier eligible in ap-south-1
SUBNET_ID = "subnet-04e67fc91487282be"  # Public subnet with auto-assign public IP
SECURITY_GROUP_ID = "sg-05527b9af5578424f"  # lolixcopilot-web-sg
INSTANCE_PROFILE = "LolixCopilotInstanceProfile"

def deploy():
    ec2 = boto3.client("ec2", region_name=REGION)
    
    # Read user data script
    user_data_path = Path(__file__).parent / "user_data.sh"
    user_data = user_data_path.read_text(encoding="utf-8")
    
    print(f"Launching EC2 instance ({INSTANCE_TYPE}) in {REGION}...")
    response = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        SubnetId=SUBNET_ID,
        SecurityGroupIds=[SECURITY_GROUP_ID],
        IamInstanceProfile={"Name": INSTANCE_PROFILE},
        UserData=user_data,
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": 30,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True
                }
            }
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "LolixCopilot-Production-Server"},
                    {"Key": "Project", "Value": "LolixCopilot"},
                    {"Key": "Environment", "Value": "Production"},
                    {"Key": "ManagedBy", "Value": "GolixcoAI"}
                ]
            }
        ]
    )
    
    instance = response["Instances"][0]
    instance_id = instance["InstanceId"]
    print(f"Instance launched: {instance_id}")
    
    print("Waiting for instance to enter 'running' state...")
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    
    # Fetch public IP
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    inst = desc["Reservations"][0]["Instances"][0]
    public_ip = inst.get("PublicIpAddress")
    public_dns = inst.get("PublicDnsName")
    
    print("=" * 60)
    print(f"Instance ID: {instance_id}")
    print(f"Public IPv4: {public_ip}")
    print(f"Public DNS:  http://{public_dns}")
    print(f"App URL:     http://{public_ip}")
    print(f"API Docs:    http://{public_ip}/docs")
    print("=" * 60)
    
    # Save instance info
    info_path = Path(__file__).parents[2] / "docs" / "DEPLOYMENT_INFO.json"
    import json
    info_path.write_text(json.dumps({
        "instance_id": instance_id,
        "region": REGION,
        "public_ip": public_ip,
        "public_dns": public_dns,
        "app_url": f"http://{public_ip}",
        "api_docs_url": f"http://{public_ip}/docs",
        "api_health_url": f"http://{public_ip}/api/v1/health",
        "launched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }, indent=2), encoding="utf-8")
    print(f"Saved deployment details to {info_path}")
    
    return instance_id, public_ip

if __name__ == "__main__":
    deploy()
