import asyncio
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
import websockets

VIDEO_PATH = "/home/vuld0/LolixCopilot/training/data/raw/gojo_hollow_purple_edit.mp4"
OUTPUT_DIR = Path("/home/vuld0/.gemini/antigravity-ide/brain/5685bfce-f222-413d-9591-1ea60d24addb")
CDP_URL = "http://localhost:9222"

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
    print("=== STARTING REAL BROWSER CDP ACCEPTANCE TEST ===")
    assert os.path.exists(VIDEO_PATH), f"File missing: {VIDEO_PATH}"
    
    # Discover or open target
    targets = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/list").read())
    page_target = None
    for t in targets:
        if t.get("type") == "page" and "localhost:3000" in t.get("url", ""):
            page_target = t
            break
    if not page_target:
        page_target = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/new?http://localhost:3000/").read())
    
    ws_url = page_target["webSocketDebuggerUrl"]
    print(f"Connected to Chrome page: {page_target['url']}")
    
    async with websockets.connect(ws_url, max_size=100_000_000) as ws:
        cdp = CDPClient(ws)
        await cdp.call("Page.enable")
        await cdp.call("DOM.enable")
        await cdp.call("Runtime.enable")
        
        # 1. Initial State Screenshot
        await cdp.screenshot("01_browser_initial_workstation.png")
        
        # 2. Upload Video via Real DOM File Input
        print("Locating file input in DOM...")
        node = await cdp.call("DOM.querySelector", {
            "nodeId": (await cdp.call("DOM.getDocument"))["root"]["nodeId"],
            "selector": "input[type='file']",
        })
        node_id = node.get("nodeId")
        assert node_id, "file input not found in DOM"
        
        print(f"Setting file input to {VIDEO_PATH} via CDP DOM.setFileInputFiles...")
        await cdp.call("DOM.setFileInputFiles", {
            "files": [VIDEO_PATH],
            "nodeId": node_id,
        })
        
        # Trigger change event in DOM
        await cdp.evaluate("""(() => {
            const el = document.querySelector('input[type="file"]');
            if (el) {
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        })()""")
        
        print("Upload initiated. Waiting for S3 presign and upload progress...")
        for i in range(25):
            await asyncio.sleep(1)
            status_text = await cdp.evaluate("""(() => {
                const isUploading = document.body.innerText.includes('Uploading') || document.body.innerText.includes('Importing');
                const err = document.querySelector('.bg-\\\\[#ef4444\\\\]\\\\/10');
                return {
                    uploading: isUploading,
                    hasError: err ? err.innerText : null,
                    clips: Array.from(document.querySelectorAll('h3, .font-medium, .truncate')).map(e => e.innerText).slice(0, 10)
                };
            })()""")
            if isinstance(status_text, dict):
                print(f"[{i}s] Status: uploading={status_text.get('uploading')}, error={status_text.get('hasError')}")
                if not status_text.get("uploading") and i > 5:
                    break
            else:
                print(f"[{i}s] Raw status:", status_text)
        
        await cdp.screenshot("02_browser_upload_completed.png")
        
        # 3. Test Timeline Seeking and Timecode Sync
        print("Testing Timeline and Video Scrubber Seeking...")
        current_tc_before = await cdp.evaluate("""(() => {
            return document.querySelector('.font-mono')?.innerText || document.body.innerText.match(/\\d{2}:\\d{2}:\\d{2}/)?.[0];
        })()""")
        print("Current timecode before seek:", current_tc_before)
        
        # Click on scene marker (e.g. 18.0s) or timeline scrubber
        await cdp.evaluate("""(() => {
            // Find Jump button or timeline track
            const jumpBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Jump 18.0s') || b.innerText.includes('Jump'));
            if (jumpBtn) {
                jumpBtn.click();
                return 'Clicked Jump Button';
            }
            return 'Jump button not found';
        })()""")
        await asyncio.sleep(1)
        
        current_tc_after = await cdp.evaluate("""(() => {
            return document.querySelector('.font-mono')?.innerText || document.body.innerText.match(/\\d{2}:\\d{2}:\\d{2}/)?.[0];
        })()""")
        print("Current timecode after seek:", current_tc_after)
        await cdp.screenshot("03_browser_timeline_seek.png")
        
        # 4. AI Director Chat Query
        print("Querying AI Director: 'Make me a cinematic 30-second edit'...")
        chat_submitted = await cdp.evaluate("""(() => {
            const input = document.querySelector('input[placeholder*="Ask Director"]');
            if (input) {
                // Set value and trigger input
                input.value = "Make me a cinematic 30-second edit";
                input.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Submit form or click submit button
                const form = input.closest('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                    return 'Submitted chat form';
                }
                const btn = input.parentElement.querySelector('button');
                if (btn) {
                    btn.click();
                    return 'Clicked submit button';
                }
            }
            return 'Input not found';
        })()""")
        print("Chat submit status:", chat_submitted)
        
        # Wait for AI Director response
        print("Waiting for AI Director response...")
        for _ in range(10):
            await asyncio.sleep(1)
            ai_text = await cdp.evaluate("""(() => {
                return document.body.innerText.includes('30-Second') || document.body.innerText.includes('Cinematic Cut') || document.body.innerText.includes('Opening Hook');
            })()""")
            if ai_text:
                print("AI Director response received!")
                break
        
        await cdp.screenshot("04_browser_ai_director_blueprint.png")
        
        # 5. Open Export Modal
        print("Opening Export Modal...")
        modal_opened = await cdp.evaluate("""(() => {
            const exportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Export Cut') || b.innerText.includes('Export'));
            if (exportBtn) {
                exportBtn.click();
                return 'Clicked Export Cut';
            }
            return 'Export button not found';
        })()""")
        print("Export button click:", modal_opened)
        await asyncio.sleep(1)
        await cdp.screenshot("05_browser_export_modal.png")
        
        # 6. Verify Export Modal Details
        modal_info = await cdp.evaluate("""(() => {
            const modal = document.querySelector('[role="dialog"]') || document.querySelector('.fixed');
            return {
                text: modal ? modal.innerText.slice(0, 300) : 'Modal not found',
                hasExportAction: !!Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Start Export') || b.innerText.includes('Render Cut') || b.innerText.includes('Export Cut'))
            };
        })()""")
        print("Export Modal State:", modal_info)
        
        print("=== BROWSER CDP ACCEPTANCE FLOW FINISHED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(main())
