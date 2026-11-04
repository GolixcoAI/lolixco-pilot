#!/usr/bin/env python3
"""LolixCopilot — Live Production AWS Deployment Acceptance Verification Script.

Tests the live CloudFront HTTPS production deployment:
URL: https://d2ikihwmt96m58.cloudfront.net
"""

import asyncio
import base64
import json
import urllib.request
from pathlib import Path
import websockets

SCREENSHOT_DIR = Path("docs/production_verification")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

PROD_URL = "https://d2ikihwmt96m58.cloudfront.net"

async def send_cdp(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            if "error" in data:
                raise RuntimeError(f"CDP Error in {method}: {data['error']}")
            return data.get("result", {})

async def capture_frame(ws, output_filename: str, msg_counter: list):
    msg_counter[0] += 1
    shot = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_counter[0])
    img_bytes = base64.b64decode(shot["data"])
    out_path = SCREENSHOT_DIR / output_filename
    out_path.write_bytes(img_bytes)
    print(f"  ✓ Saved screenshot: {out_path} ({len(img_bytes):,} bytes)")
    return out_path

async def main():
    print("=" * 70)
    print("LOLIXCOPILOT — LIVE AWS CLOUDFRONT HTTPS ACCEPTANCE TEST")
    print(f"Target URL: {PROD_URL}")
    print("=" * 70)

    # 1. Connect to Chrome page
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json/list").read())
    page = next(t for t in targets if t.get("type") == "page")
    ws_url = page["webSocketDebuggerUrl"]
    print(f"Connected to Chrome page: {ws_url}")

    async with websockets.connect(ws_url, max_size=30_000_000) as ws:
        msg_counter = [100]

        async def call(method, params=None):
            msg_counter[0] += 1
            return await send_cdp(ws, method, params, msg_id=msg_counter[0])

        await call("Page.enable")
        await call("Runtime.enable")
        await call("Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False
        })

        # 2. Navigate to Production CloudFront URL
        print("\n[Step 1] Navigating to Production CloudFront HTTPS URL...")
        await call("Page.navigate", {"url": PROD_URL})
        await asyncio.sleep(4.0)

        # 3. Check page title and document readiness
        res = await call("Runtime.evaluate", {
            "expression": "document.title",
            "returnByValue": True
        })
        page_title = res.get("result", {}).get("value", "")
        print(f"  ✓ Page Title: '{page_title}'")

        # 4. Check Logo and Command Bar
        res = await call("Runtime.evaluate", {
            "expression": "!!document.querySelector('header svg')",
            "returnByValue": True
        })
        has_logo = res.get("result", {}).get("value", False)
        print(f"  ✓ Brand SVG Logo rendered: {has_logo}")

        # 5. Check API Health Check & Git Commit SHA
        res = await call("Runtime.evaluate", {
            "expression": """
                (async () => {
                    const r = await fetch('/api/health');
                    return await r.json();
                })()
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        health_data = res.get("result", {}).get("value", {})
        print(f"  ✓ Live Health Check: status='{health_data.get('status')}', commit_sha='{health_data.get('commit_sha')}'")
        assert health_data.get("status") == "healthy", "Production health check failed"

        # Capture Clean First Launch
        await capture_frame(ws, "01_prod_clean_first_launch.png", msg_counter)

        # 6. Verify Ordinary Conversation ("Hi")
        print("\n[Step 2] Testing Ordinary Conversation ('Hi')...")
        res = await call("Runtime.evaluate", {
            "expression": """
                (async () => {
                    const item = JSON.parse(localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token'));
                    const token = item.access_token;
                    const r = await fetch('/api/projects/default/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
                        body: JSON.stringify({ message: 'Hi', provider: 'auto' })
                    });
                    return await r.json();
                })()
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        chat_val = res.get("result", {}).get("value", {})
        msg_obj = chat_val.get("message", {})
        content = msg_obj.get("content", "")
        print(f"  ✓ AI Director greeting received: {len(content)} chars")
        print(f"  ✓ Message snippet: {content[:80]}...")
        recs = chat_val.get("edit_recommendations") or []
        print(f"  ✓ Recommendations count: {len(recs)} (must be 0)")
        assert len(recs) == 0

        # 7. Verify AI Director Query 1 (Review my edit)
        print("\n[Step 3] Testing AI Director Query 1 ('Review my edit')...")
        q1_text = "Review my edit. Give me suggestions on what I should improve and tell me exactly where I should edit."
        res = await call("Runtime.evaluate", {
            "expression": f"""
                (async () => {{
                    const item = JSON.parse(localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token'));
                    const token = item.access_token;
                    const r = await fetch('/api/projects/default/chat', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                        body: JSON.stringify({{ message: '{q1_text}', provider: 'auto' }})
                    }});
                    return await r.json();
                }})()
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        q1_data = res.get("result", {}).get("value", {})
        scenes = q1_data.get("scene_breakdown") or []
        recs1 = q1_data.get("edit_recommendations") or []
        traces = q1_data.get("inference_trace") or []
        print(f"  ✓ Scenes returned: {len(scenes)}")
        print(f"  ✓ Recommendations returned: {len(recs1)}")
        print(f"  ✓ Multi-Provider Traces: {[t.get('provider') for t in traces]}")
        assert len(scenes) == 6
        assert len(recs1) == 5

        # 8. Verify AI Director Query 2 (Hollow Purple title overlay)
        print("\n[Step 4] Testing AI Director Query 2 ('Add a title overlay for Hollow Purple')...")
        q2_text = "Locate Hollow Purple and add the text 'Hollow Purple' in purple colour from 00:37 to 00:44."
        res = await call("Runtime.evaluate", {
            "expression": f"""
                (async () => {{
                    const item = JSON.parse(localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token'));
                    const token = item.access_token;
                    const r = await fetch('/api/projects/default/chat', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                        body: JSON.stringify({{ message: \"{q2_text}\", provider: 'auto' }})
                    }});
                    return await r.json();
                }})()
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        q2_data = res.get("result", {}).get("value", {})
        bp2 = q2_data.get("updated_blueprint") or {}
        print(f"  ✓ Blueprint Action: {bp2.get('action')}")
        overlay = bp2.get("overlay") or {}
        print(f"  ✓ Overlay details: text='{overlay.get('text')}', range=[{overlay.get('start_seconds')}s, {overlay.get('end_seconds')}s], color='{overlay.get('color')}'")
        assert bp2.get("action") == "add_text_overlay"
        assert overlay.get("color") == "#a855f7"

        # 9. Verify AI Director Query 3 (Keep last 30s)
        print("\n[Step 5] Testing AI Director Query 3 ('Keep only the last 30 seconds')...")
        q3_text = "Keep the last 30 seconds from this video and prepare it for export."
        res = await call("Runtime.evaluate", {
            "expression": f"""
                (async () => {{
                    const item = JSON.parse(localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token'));
                    const token = item.access_token;
                    const r = await fetch('/api/projects/default/chat', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                        body: JSON.stringify({{ message: '{q3_text}', provider: 'auto' }})
                    }});
                    return await r.json();
                }})()
            """,
            "awaitPromise": True,
            "returnByValue": True
        })
        q3_data = res.get("result", {}).get("value", {})
        bp3 = q3_data.get("updated_blueprint") or {}
        print(f"  ✓ Blueprint Action: {bp3.get('action')}")
        print(f"  ✓ Active trim calculated: start={bp3.get('trim_start')}s, end={bp3.get('trim_end')}s")
        assert bp3.get("action") == "trim_selection"
        assert abs(float(bp3.get("trim_start", 0)) - 38.08) < 0.05
        assert abs(float(bp3.get("trim_end", 0)) - 68.08) < 0.05

        print("\n" + "=" * 70)
        print("ALL LIVE AWS PRODUCTION ACCEPTANCE CHECKS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
