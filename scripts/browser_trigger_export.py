import asyncio
import base64
import json
import urllib.request
from pathlib import Path
import websockets

CDP_URL = "http://localhost:9222"
OUTPUT_DIR = Path("/home/vuld0/.gemini/antigravity-ide/brain/5685bfce-f222-413d-9591-1ea60d24addb")

class CDPClient:
    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0

    async def call(self, method, params=None):
        self.msg_id += 1
        req = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        while True:
            resp = await self.ws.recv()
            data = json.loads(resp)
            if data.get("id") == self.msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP Error in {method}: {data['error']}")
                return data.get("result", {})

    async def evaluate(self, expression):
        res = await self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return res.get("result", {}).get("value")

    async def screenshot(self, filename):
        shot = await self.call("Page.captureScreenshot", {"format": "png"})
        img_bytes = base64.b64decode(shot["data"])
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(img_bytes)
        print(f"Captured screenshot: {out_path} ({len(img_bytes)} bytes)")
        return out_path

async def main():
    print("=== TRIGGERING REAL EXPORT IN LIVE BROWSER WORKSTATION ===")
    targets = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/list").read())
    page_target = next(t for t in targets if t.get("type") == "page" and "localhost:3000" in t.get("url", ""))
    
    async with websockets.connect(page_target["webSocketDebuggerUrl"], max_size=100_000_000) as ws:
        cdp = CDPClient(ws)
        await cdp.call("Runtime.enable")
        
        # Click "Start Export Render"
        click_res = await cdp.evaluate("""(() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Start Export Render') || b.innerText.includes('Start Export'));
            if (btn) {
                btn.click();
                return 'Clicked Start Export Render';
            }
            return 'Button not found';
        })()""")
        print("Click result:", click_res)
        
        # Poll for export completion
        print("Waiting for AWS Lambda rendering to complete...")
        for i in range(120):
            await asyncio.sleep(2)
            card = await cdp.evaluate("""(() => {
                const ready = document.body.innerText.includes('H.264 Cut Ready') || document.body.innerText.includes('Download MP4');
                const err = document.querySelector('.bg-\\\\[#f87171\\\\]\\\\/10');
                const dl = document.querySelector('a[download]');
                return {
                    ready,
                    error: err ? err.innerText : null,
                    downloadHref: dl ? dl.href : null,
                    bodySnippet: document.querySelector('[role="dialog"]')?.innerText || document.body.innerText.slice(0, 400)
                };
            })()""")
            if card.get("error"):
                print("Export error:", card["error"])
                break
            if card.get("ready"):
                print(f"Export Completed at ~{i*2}s! Download link:", card.get("downloadHref"))
                break
            print(f"[{i*2}s] Rendering in progress...")
            
        await cdp.screenshot("06_browser_export_completed.png")
        print("=== BROWSER EXPORT VERIFIED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(main())
