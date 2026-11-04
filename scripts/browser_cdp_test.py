import asyncio
import base64
import json
import urllib.request
from pathlib import Path
import websockets

TARGET_URL = "http://localhost:3000/"
OUTPUT_DIR = Path("/home/vuld0/.gemini/antigravity-ide/brain/5685bfce-f222-413d-9591-1ea60d24addb")

async def send_cdp(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def main():
    # 1. Discover target
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json/list").read())
    page_target = None
    for t in targets:
        if t.get("type") == "page" and "localhost:3000" in t.get("url", ""):
            page_target = t
            break
    if not page_target:
        page_target = json.loads(urllib.request.urlopen("http://localhost:9222/json/new?http://localhost:3000/").read())
    
    ws_url = page_target["webSocketDebuggerUrl"]
    print(f"Connecting to CDP: {ws_url}")
    
    async with websockets.connect(ws_url) as ws:
        # Enable domains
        await send_cdp(ws, "Page.enable", msg_id=1)
        await send_cdp(ws, "Runtime.enable", msg_id=2)
        await send_cdp(ws, "DOM.enable", msg_id=3)
        
        # Wait for page load
        await asyncio.sleep(2)
        
        # Take screenshot of home workstation
        shot = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=4)
        img_bytes = base64.b64decode(shot["data"])
        out_path = OUTPUT_DIR / "browser_real_workstation.png"
        out_path.write_bytes(img_bytes)
        print(f"Screenshot written to {out_path} ({len(img_bytes)} bytes)")
        
        # Get document title and main header
        eval_res = await send_cdp(ws, "Runtime.evaluate", {
            "expression": "document.title + ' | ' + (document.querySelector('h1')?.innerText || document.querySelector('header')?.innerText || 'No header')"
        }, msg_id=5)
        print("DOM State:", eval_res.get("result", {}).get("value"))

if __name__ == "__main__":
    asyncio.run(main())
