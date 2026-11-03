# LolixCopilot — YouTube Product Demonstration Script

**Company:** Golixco AI  
**Product:** LolixCopilot  
**Tagline:** From raw footage to a stronger cut.  
**Target Duration:** 3:00 - 3:30  
**Resolution:** 1080p (1920×1080) at 60 fps  
**Live Application URL:** http://3.110.25.215  
**Hackathon:** Meta Global AI Developer Hackathon (2026)

---

## 🎯 Demonstration Objective
Demonstrate that LolixCopilot is an operational, AI-augmented video editing workstation that solves real creator workflow problems: turning hours of raw footage into a structured editing blueprint with timestamped moments, beat synchronization, multi-track timeline visualization, and multi-provider AI reasoning.

---

## ⏱ Storyboard & Scene Breakdown

### Act 1: The Creator Dilemma & Product Introduction (0:00 – 0:35)
- **Visual:** Open on a split-screen or full-screen view of raw anime battle footage (`gojo_hollow_purple_edit.mp4`) scrubbing erratically.
- **Narrator Voiceover:**
  > "Video editors spend over 70% of their production time on one repetitive task: hunting through hours of raw footage for the exact keyframe, climax, or beat drop. 
  > This is **LolixCopilot** — Golixco’s AI-augmented workstation built for creators and independent editors. 
  > Our philosophy is simple: **from raw footage to a stronger cut**."
- **Visual Action:** Reveal the full LolixCopilot workstation in the browser (`http://3.110.25.215`). Point out the official white-and-yellow brand logo at the top left, the dark studio workstation aesthetic, and the clean non-linear editor layout.

---

### Act 2: Media Bin & Cloud Upload Pipeline (0:35 – 1:05)
- **Visual:** Cursor moves to the **Media Bin** panel on the left.
- **Narrator Voiceover:**
  > "Importing media is direct and secure. Footage uploads straight from the browser to private Amazon S3 storage using short-lived presigned URLs. 
  > Instantly in the background, our AWS Lambda media processor generates an H.264 preview proxy and extracts audio beat waveforms — keeping original footage private and secure."
- **Visual Action:** 
  - Show the `gojo_hollow_purple_edit.mp4` media card with metadata (1080p, 30.18s, 30 fps, H.264).
  - Scrub through the Preview Monitor to show smooth playback with exact SMPTE timecode (`00:00:12:14`).
  - Demonstrate frame stepping with the `|◀`, `◀◀`, `▶`, `▶▶`, `▶|` controls.

---

### Act 3: Multi-Provider AI Director & Conversational Search (1:05 – 2:15)
- **Visual:** Pan to the **AI Director** panel on the right.
- **Narrator Voiceover:**
  > "The core differentiator of LolixCopilot is its multi-provider AI intelligence. 
  > Rather than relying on a single model, we route requests across specialized AI backends:
  > - **Modal with physical NVIDIA H100 GPUs** running Muse Glimmer 30B with custom QLoRA adapters for visual scene grounding.
  > - **Meta Model API** with Muse Spark 1.3 for creative pacing, narrative direction, and deep reasoning tokens.
  > - **Baseten** running Muse Spark Open for high-throughput structured editing blueprints.
  > Let's ask the AI Director to find the peak moment: *'Find Gojo using Hollow Purple.'*"
- **Visual Action:**
  - Click the prompt chip or type in the AI Director chat.
  - Show the response streaming in with:
    1. **Inference Trace:** Modal H100 visual latency (4.21s), Meta reasoning tokens, Baseten blueprint.
    2. **6-Scene Breakdown Card:** With timestamped thumbnails (`00:00:12.46 - 00:00:18.20 Convergence`).
    3. **Actionable Edit Recommendations:** 5 checkable suggestions with *"▶ Apply to Timeline"* and *"🎯 Jump to Moment"*.
  - Click *"🎯 Jump to Moment"* at 12.46s — the Preview Monitor immediately seeks to the exact frame where energy spheres converge.

---

### Act 4: Multi-Track Timeline & Beat Synchronization (2:15 – 2:50)
- **Visual:** Focus on the bottom **Multi-Track Timeline**.
- **Narrator Voiceover:**
  > "Editing suggestions aren't just text — they live directly on our multi-track timeline.
  > - On **Track V2**, LolixCopilot places precision effect markers, including speed ramps and visual flashes.
  > - On **Track V1**, you see full filmstrip thumbnails with cut boundaries and transition handles.
  > - On **Track A1**, our Lambda processor has detected audio transience, placing beat sync markers so every cut aligns with the soundtrack."
- **Visual Action:**
  - Click *"▶ Apply to Timeline"*. Show the timeline update with yellow cut marks and speed ramp blocks.
  - Scrub the playhead across the timeline: observe the video monitor and SMPTE timecode updating in real-time.
  - Demonstrate timeline zooming with the zoom slider and snapping toggle.

---

### Act 5: Real Cloud Telemetry & Lambda Export (2:50 – 3:30)
- **Visual:** Cursor moves to the **AI Usage & Telemetry** widget in the bottom navigation rail.
- **Narrator Voiceover:**
  > "We believe in complete transparency. Every request displays genuine cloud telemetry: physical Modal H100 GPU seconds, Meta AI token consumption, Baseten inference calls, and session cost accounting. No fabricated mocks.
  > When the editor is satisfied, clicking **Export** triggers AWS Lambda to render the final 30-second cut."
- **Visual Action:**
  - Open the Export modal, show the 1080p H.264 cut settings, and trigger render.
  - Show the completed status badge: *"✓ Render Complete (30.18s Rough Cut)"*.
- **Closing Voiceover:**
  > "LolixCopilot: From raw footage to a stronger cut. 
  > Live on AWS ap-south-1 right now. Thank you."

---

## 📋 Recording Checklist (For Windows Laptop Recording)

- [ ] Open Google Chrome and navigate to `http://3.110.25.215`.
- [ ] Set browser zoom to 100% and maximize the browser window (1920×1080 display).
- [ ] Ensure the default audio output is clear (OBS Studio or Windows Game Bar at 1080p 60fps).
- [ ] Verify the official LolixCopilot logo is visible in the top command bar.
- [ ] Test the prompt chip click (*"Find Gojo using Hollow Purple"*).
- [ ] Test clicking *"🎯 Jump to Moment"* to confirm the player seeks smoothly to 12.46s.
- [ ] Test timeline scrubbing and play/pause controls (`Spacebar`).
- [ ] Verify the AI usage telemetry numbers in the lower nav rail.
