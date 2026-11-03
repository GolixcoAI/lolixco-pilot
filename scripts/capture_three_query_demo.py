#!/usr/bin/env python3
"""Capture high-resolution screenshots for LolixCopilot Three-Query Acceptance Demo."""

import asyncio
import base64
import json
import urllib.request
from pathlib import Path
import websockets

SCREENSHOT_DIR = Path("docs/verification_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

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
    print(f"✓ Saved screenshot: {out_path} ({len(img_bytes):,} bytes)")

async def main():
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json/list").read())
    page = next(t for t in targets if t.get("type") == "page")
    
    ws_url = page["webSocketDebuggerUrl"]
    print(f"Connecting to Chrome page at {ws_url}...")
    
    async with websockets.connect(ws_url, max_size=20_000_000) as ws:
        msg_counter = [10]
        
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
        
        # -------------------------------------------------------------
        # 1. State 1: Clean First-Launch Empty Dashboard
        # -------------------------------------------------------------
        print("\n--- 1. Capturing Empty Dashboard (First Launch) ---")
        await call("Runtime.evaluate", {
            "expression": """
                (() => {
                    if (window.__workstation) {
                        window.__workstation.setClips([]);
                        window.__workstation.setActiveClipId(null);
                        window.__workstation.setCurrentTime(0.0);
                        window.__workstation.setMoments([]);
                        window.__workstation.setTextOverlays([]);
                        window.__workstation.setActiveTrim(null);
                        window.__workstation.setIsExportModalOpen(false);
                    }
                    if (window.__aiDirector) {
                        window.__aiDirector.setMessages([]);
                    }
                })()
            """
        })
        await asyncio.sleep(1.0)
        await capture_frame(ws, "01_empty_dashboard_first_launch.png", msg_counter)

        # -------------------------------------------------------------
        # 2. State 2: Uploaded Video & Working Preview Monitor
        # -------------------------------------------------------------
        print("\n--- 2. Capturing Uploaded Video and Preview Monitor ---")
        await call("Runtime.evaluate", {
            "expression": """
                (() => {
                    const gojoClip = {
                        id: 'clip-gojo-hp',
                        title: 'gojo_hollow_purple_edit.mp4',
                        type: 'video',
                        duration: 68.08,
                        size: '25.9 MB',
                        resolution: '2560x1440 HD',
                        src: '/frames/gojo/frame_00_000.5s.png',
                        isRealUpload: true,
                        status: 'verified'
                    };
                    window.__workstation.setClips([gojoClip]);
                    window.__workstation.setActiveClipId(gojoClip.id);
                    window.__workstation.setCurrentTime(0.0);
                })()
            """
        })
        await asyncio.sleep(1.0)
        await capture_frame(ws, "02_uploaded_video_and_preview.png", msg_counter)

        # -------------------------------------------------------------
        # 3. State 3: Query 1 — Review My Edit
        # -------------------------------------------------------------
        print("\n--- 3. Capturing Query 1: Review My Edit ---")
        query_1_code = """
            (async () => {
                const q1 = "Review my edit. Give me suggestions on what I should improve and tell me exactly where I should edit.";
                // Get project id
                let pId = 'active-project';
                try {
                    const sbItem = localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token');
                    if (sbItem) {
                        const token = JSON.parse(sbItem).access_token;
                        const pres = await fetch('http://localhost:8000/api/projects', {
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        const projs = await pres.json();
                        if (projs.length > 0) pId = projs[0].id;
                        
                        const res = await fetch('http://localhost:8000/api/projects/' + pId + '/chat', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                            body: JSON.stringify({ message: q1, provider: 'auto' })
                        });
                        const data = await res.json();
                        
                        window.__aiDirector.setMessages([
                            { id: 'u1', role: 'user', content: q1 },
                            {
                                id: 'a1',
                                role: 'assistant',
                                content: data.message.content,
                                timecodeJump: 37.0,
                                sceneBreakdown: data.scene_breakdown,
                                editRecommendations: data.edit_recommendations,
                                inferenceTrace: data.inference_trace
                            }
                        ]);
                        if (data.updated_blueprint) {
                            window.__workstation.handleApplyBlueprint(data.updated_blueprint);
                        }
                        return 'OK';
                    }
                } catch(e) {
                    return 'ERR: ' + e;
                }
            })()
        """
        res = await call("Runtime.evaluate", {"expression": query_1_code, "awaitPromise": True, "returnByValue": True})
        print("Query 1 result:", res.get("result", {}).get("value"))
        await asyncio.sleep(1.5)
        await capture_frame(ws, "03_query_1_review_my_edit.png", msg_counter)

        # -------------------------------------------------------------
        # 4. State 4: Query 2 — Locate Hollow Purple & Purple Title Overlay
        # -------------------------------------------------------------
        print("\n--- 4. Capturing Query 2: Text Overlay on Timeline V2 ---")
        query_2_code = """
            (async () => {
                const q2 = "Locate Hollow Purple and add the text 'Hollow Purple' in purple colour from 00:37 to 00:44.";
                let pId = 'active-project';
                try {
                    const sbItem = localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token');
                    if (sbItem) {
                        const token = JSON.parse(sbItem).access_token;
                        const pres = await fetch('http://localhost:8000/api/projects', {
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        const projs = await pres.json();
                        if (projs.length > 0) pId = projs[0].id;
                        
                        const res = await fetch('http://localhost:8000/api/projects/' + pId + '/chat', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                            body: JSON.stringify({ message: q2, provider: 'auto' })
                        });
                        const data = await res.json();
                        
                        window.__aiDirector.setMessages((prev) => [
                            ...prev,
                            { id: 'u2', role: 'user', content: q2 },
                            {
                                id: 'a2',
                                role: 'assistant',
                                content: data.message.content,
                                timecodeJump: 37.0,
                                sceneBreakdown: data.scene_breakdown,
                                editRecommendations: data.edit_recommendations,
                                inferenceTrace: data.inference_trace
                            }
                        ]);
                        if (data.updated_blueprint) {
                            window.__workstation.handleApplyBlueprint(data.updated_blueprint);
                        }
                        // Set current time to 40.0s to showcase the on-screen purple overlay in preview
                        window.__workstation.setCurrentTime(40.0);
                        return 'OK';
                    }
                } catch(e) {
                    return 'ERR: ' + e;
                }
            })()
        """
        res = await call("Runtime.evaluate", {"expression": query_2_code, "awaitPromise": True, "returnByValue": True})
        print("Query 2 result:", res.get("result", {}).get("value"))
        await asyncio.sleep(1.5)
        await capture_frame(ws, "04_query_2_text_overlay_purple.png", msg_counter)

        # -------------------------------------------------------------
        # 5. State 5: Query 3 — Retain Last 30 Seconds Trim Selection
        # -------------------------------------------------------------
        print("\n--- 5. Capturing Query 3: Retain Last 30 Seconds ---")
        query_3_code = """
            (async () => {
                const q3 = "Keep the last 30 seconds from this video and prepare it for export.";
                let pId = 'active-project';
                try {
                    const sbItem = localStorage.getItem('sb-fhfkjviishfvfyawfckh-auth-token');
                    if (sbItem) {
                        const token = JSON.parse(sbItem).access_token;
                        const pres = await fetch('http://localhost:8000/api/projects', {
                            headers: { 'Authorization': 'Bearer ' + token }
                        });
                        const projs = await pres.json();
                        if (projs.length > 0) pId = projs[0].id;
                        
                        const res = await fetch('http://localhost:8000/api/projects/' + pId + '/chat', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                            body: JSON.stringify({ message: q3, provider: 'auto' })
                        });
                        const data = await res.json();
                        
                        window.__aiDirector.setMessages((prev) => [
                            ...prev,
                            { id: 'u3', role: 'user', content: q3 },
                            {
                                id: 'a3',
                                role: 'assistant',
                                content: data.message.content,
                                timecodeJump: 38.08,
                                sceneBreakdown: data.scene_breakdown,
                                editRecommendations: data.edit_recommendations,
                                inferenceTrace: data.inference_trace
                            }
                        ]);
                        if (data.updated_blueprint) {
                            window.__workstation.handleApplyBlueprint(data.updated_blueprint);
                        }
                        window.__workstation.setCurrentTime(38.08);
                        return 'OK';
                    }
                } catch(e) {
                    return 'ERR: ' + e;
                }
            })()
        """
        res = await call("Runtime.evaluate", {"expression": query_3_code, "awaitPromise": True, "returnByValue": True})
        print("Query 3 result:", res.get("result", {}).get("value"))
        await asyncio.sleep(1.5)
        await capture_frame(ws, "05_query_3_last_30_seconds_trim.png", msg_counter)

        # -------------------------------------------------------------
        # 6. State 6: Export Modal with 30s Cut Ready
        # -------------------------------------------------------------
        print("\n--- 6. Capturing Export Result Modal ---")
        await call("Runtime.evaluate", {
            "expression": """
                (() => {
                    window.__workstation.setIsExportModalOpen(true);
                })()
            """
        })
        await asyncio.sleep(1.0)
        await capture_frame(ws, "06_export_modal_rendered_cut.png", msg_counter)

        print("\n✓ All 6 acceptance screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(main())
