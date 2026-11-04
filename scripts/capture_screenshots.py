import asyncio
import base64
import json
import urllib.request
from pathlib import Path
import websockets

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

async def capture_at_resolution(width, height, output_path: Path):
    targets = json.loads(urllib.request.urlopen("http://localhost:9222/json/list").read())
    page_target = None
    for t in targets:
        if t.get("type") == "page":
            page_target = t
            break
    if not page_target:
        page_target = json.loads(urllib.request.urlopen("http://localhost:9222/json/new?http://localhost:3000/").read())
    
    ws_url = page_target["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url) as ws:
        await send_cdp(ws, "Page.enable", msg_id=1)
        await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": False
        }, msg_id=2)
        await send_cdp(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=3)
        await asyncio.sleep(2.5)
        
        shot = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=4)
        img_bytes = base64.b64decode(shot["data"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_bytes)
        print(f"Captured {width}x{height} -> {output_path} ({len(img_bytes)} bytes)")

async def main():
    await capture_at_resolution(1920, 1080, Path("docs/baseline_screenshots/baseline_1920x1080.png"))
    await capture_at_resolution(1440, 900, Path("docs/baseline_screenshots/baseline_1440x900.png"))

if __name__ == "__main__":
    asyncio.run(main())

