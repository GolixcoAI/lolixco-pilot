# LolixCopilot — YouTube Product Demonstration Script

**Company:** Golixco  
**Product:** LolixCopilot  
**Tagline:** From raw footage to a stronger cut.  
**Target Duration:** 3:00 - 3:30  
**Resolution:** 1080p (1920x1080) at 60 fps  
**Live Application URL:** https://d2ikihwmt96m58.cloudfront.net  
**Hackathon:** Meta Global AI Developer Hackathon (November 2026)

---

## Demonstration Objective

Demonstrate that LolixCopilot is an operational, AI-augmented video editing workstation that solves real creator workflow problems: turning hours of raw footage into a structured editing blueprint with timestamped moments, beat synchronization, multi-track timeline visualization, multi-provider AI reasoning, and rendered video exports.

---

## 10-Step Storyboard and Scene Breakdown

### Step 1: Product Introduction (0:00 - 0:25)
- **Visual:** Open on the LolixCopilot workstation in Google Chrome at 1080p.
- **Narrator Voiceover:**
  > "Video editors spend over 70% of their production time on one repetitive task: hunting through hours of raw footage for the right moment, dialogue clip, or beat drop. 
  > This is **LolixCopilot** — Golixco's AI-assisted video editing workstation built for independent video editors and creators. 
  > Our mission: **from raw footage to a stronger cut**."
- **Visual Action:** Point out the official LolixCopilot white-and-yellow brand logo in the top command bar, the dark studio workstation aesthetic, and the non-linear editing layout.

---

### Step 2: Empty Dashboard State (0:25 - 0:45)
- **Visual:** Display the clean initial state of the workstation.
- **Narrator Voiceover:**
  > "We are live on AWS ap-south-1 under secure CloudFront HTTPS. 
  > The workspace starts completely clean: an empty media bin, a clean preview monitor, an empty multi-track timeline, and the conversational AI Director ready for input."
- **Visual Action:** Highlight the empty media bin, empty timeline tracks, and the AI Director chat interface.

---

### Step 3: Footage Ingest and Cloud Storage (0:45 - 1:10)
- **Visual:** Drag and drop raw footage into the Media Bin.
- **Narrator Voiceover:**
  > "Importing footage is direct and secure. Video uploads straight from the browser to our private Amazon S3 bucket using short-lived presigned URLs. 
  > All public access is blocked. Instantly in the background, our AWS Lambda media processor generates an H.264 preview proxy and extracts audio beat waveforms."
- **Visual Action:** 
  - Show the uploaded media card with metadata (1080p, 68.08s, H.264).
  - Scrub through the Preview Monitor to show smooth 60fps playback with exact SMPTE timecode (`00:00:14:00`).
  - Demonstrate frame stepping with the player controls.

---

### Step 4: AI Director Query 1 — Editorial Review (1:10 - 1:40)
- **Visual:** Focus on the AI Director panel on the right.
- **Narrator Voiceover:**
  > "Now we ask our AI Director: 'Review my edit.' 
  > In Auto mode, LolixCopilot orchestrates across our multi-provider mesh:
  > - **Modal with physical NVIDIA H100 GPUs** running Muse Glimmer 30B for visual scene grounding.
  > - **Meta Model API with Muse Spark 1.3** for creative pacing, narrative direction, and reasoning.
  > - **Baseten** running Muse Spark Open for structured blueprint generation."
- **Visual Action:**
  - Send the query "Review my edit".
  - Show the response streaming in with:
    1. Real-time inference trace (Modal latency, Meta reasoning tokens, Baseten blueprint).
    2. 6-Scene Breakdown Card with visual thumbnails.
    3. 5 checkable editorial recommendations.

---

### Step 5: Timestamped Scene Discovery (1:40 - 1:55)
- **Visual:** Interact with the 6-Scene Breakdown Card.
- **Narrator Voiceover:**
  > "Every scene recommendation is grounded with exact timestamps. 
  > Clicking 'Jump to Moment' immediately seeks our preview monitor to the exact frame where energy spheres converge at 12.46 seconds."
- **Visual Action:** Click "Jump to Moment" on Scene 2; observe the Preview Monitor seek to 12.46s instantly.

---

### Step 6: AI Director Query 2 — Timed Title Overlay (1:55 - 2:20)
- **Visual:** Type Query 2 into the AI Director chat.
- **Narrator Voiceover:**
  > "Next, we give a creative directive: 'Add a title overlay for Hollow Purple.' 
  > The AI Director identifies the technique convergence window from 00:37 to 00:44 and injects a timed purple text overlay onto Track V2."
- **Visual Action:**
  - Send the message.
  - Show the purple title overlay appear on Track V2 from 37.00s to 44.00s.
  - Scrub playhead across 37.0s to 44.0s: show the title appearing and disappearing in the Preview Monitor with exact synchronization.

---

### Step 7: AI Director Query 3 — Non-Destructive Last-30-Seconds Trim (2:20 - 2:45)
- **Visual:** Type Query 3 into the AI Director chat.
- **Narrator Voiceover:**
  > "Now we instruct: 'Keep only the last 30 seconds.' 
  > The workstation calculates the video duration, deactivates earlier footage non-destructively with hatched visual styling, and automatically remaps the Track V2 overlay into the new export coordinate space."
- **Visual Action:**
  - Send the instruction.
  - Show Track V1 deactivate footage before 38.08s.
  - Show the timeline duration adjust to an exact 30.00 seconds.

---

### Step 8: Asynchronous Export Rendering (2:45 - 3:10)
- **Visual:** Click the neon yellow "Export" button in the Top Command Bar.
- **Narrator Voiceover:**
  > "When the editor is satisfied, clicking Export triggers an asynchronous render job on AWS Lambda. 
  > Lambda uses FFmpeg libass to burn the timed title overlay directly into the video stream while preserving synchronized audio."
- **Visual Action:**
  - Open the Export modal.
  - Show the live stage progress bar.
  - Show completion: 30.00-second cut ready with download button.
  - Click download and play back the exported cut.

---

### Step 9: Multi-Provider AI Architecture Summary (3:10 - 3:25)
- **Visual:** Pan across the AI Director provider selector and lower telemetry bar.
- **Narrator Voiceover:**
  > "Behind this experience is a transparent architecture: Meta Muse Spark 1.3 for creative direction, Muse Glimmer 30B on Modal H100 for visual grounding, Baseten for structured schema output, and physical GPU fine-tuning pipelines."

---

### Step 10: Live Deployment Showcase & Conclusion (3:25 - 3:35)
- **Visual:** Return to full workstation view with live CloudFront URL visible in address bar.
- **Narrator Voiceover:**
  > "LolixCopilot: From raw footage to a stronger cut. 
  > Live on AWS ap-south-1 right now. Thank you."

---

## Recording Checklist (For Windows Laptop Recording)

- [ ] Open Google Chrome and navigate to `https://d2ikihwmt96m58.cloudfront.net`.
- [ ] Set browser zoom to 100% and maximize the browser window (1920x1080 display).
- [ ] Ensure the default audio output is clear (OBS Studio or Windows Game Bar at 1080p 60fps).
- [ ] Verify the official LolixCopilot logo is visible in the top command bar.
- [ ] Test the prompt chip click ("Review my edit").
- [ ] Test clicking "Jump to Moment" to confirm the player seeks smoothly.
- [ ] Test Query 2 ("Add a title overlay for Hollow Purple").
- [ ] Test Query 3 ("Keep only the last 30 seconds").
- [ ] Test Export modal render and download.
