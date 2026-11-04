"""LolixCopilot — Live Production Chat & AI Director Verification Script.

Tests conversational intent, editorial review, editing instructions,
and auto provider routing through public CloudFront HTTPS endpoint.
"""

from __future__ import annotations

import json
import time
import boto3
import httpx

CLOUDFRONT_BASE = "https://d2ikihwmt96m58.cloudfront.net"
REGION = "ap-south-1"


def get_auth_token() -> str:
    """Fetch anonymous user token from Supabase using public production credentials."""
    sm = boto3.client("secretsmanager", region_name=REGION)
    resp = sm.get_secret_value(SecretId="lolixcopilot/production/backend")
    secrets = json.loads(resp["SecretString"])

    supabase_url = secrets["SUPABASE_URL"]
    anon_key = secrets["SUPABASE_PUBLISHABLE_KEY"]

    auth_resp = httpx.post(
        f"{supabase_url}/auth/v1/signup",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"data": {}},
        timeout=15.0,
    )
    data = auth_resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Failed to obtain auth token: {auth_resp.text}")
    return token


def run_chat_query(
    token: str,
    prompt: str,
    provider: str = "auto",
    project_id: str = "proj-hollow-purple",
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "project_id": project_id,
        "message": prompt,
        "provider": provider,
        "playhead_seconds": 38.08,
    }
    t0 = time.time()
    resp = httpx.post(
        f"{CLOUDFRONT_BASE}/api/projects/{project_id}/chat",
        headers=headers,
        json=payload,
        timeout=60.0,
    )
    dur_ms = round((time.time() - t0) * 1000, 1)

    print(f"\n" + "=" * 60)
    print(f"QUERY: '{prompt}' (Provider: {provider})")
    print(f"STATUS: {resp.status_code} | LATENCY: {dur_ms}ms")

    if resp.status_code != 200:
        print(f"ERROR: {resp.text}")
        return {"status": resp.status_code, "error": resp.text}

    data = resp.json()
    msg = data.get("message", {})
    traces = data.get("inference_trace", [])

    print(f"PROVIDER USED: {data.get('provider_used')}")
    print(f"MODEL USED: {data.get('model_used')}")
    print(f"TIME JUMP: {msg.get('timecode_jump')}")
    print(f"SUGGESTED ACTION: {msg.get('suggested_action')}")
    if traces:
        for t in traces:
            print(f"TRACE: provider={t.get('provider')}, model={t.get('model')}, status={t.get('status')}, latency={t.get('latency_ms')}ms")
    print(f"CONTENT:\n{msg.get('content')}")

    if data.get("updated_blueprint"):
        bp = data["updated_blueprint"]
        print(f"BLUEPRINT UPDATED: cuts={len(bp.get('cuts', []))}, titles={len(bp.get('titles', []))}, duration={bp.get('total_duration')}s")

    return data


def main() -> None:
    print("LolixCopilot — Live AI Director Production Verification")
    token = get_auth_token()
    print("Obtained authenticated anonymous Supabase token.")

    queries = [
        ("HI", "auto"),
        ("HELLO", "auto"),
        ("What can you do?", "auto"),
        ("Review my edit.", "auto"),
        ("Add the title Hollow Purple from 37 to 44 seconds.", "auto"),
        ("Keep the last 30 seconds.", "auto"),
    ]

    for q, p in queries:
        run_chat_query(token, q, provider=p)


if __name__ == "__main__":
    main()
