# LolixCopilot — Jujutsu Kaisen Event-Recognition Dataset Specification

**Document Version:** 1.0.0
**Target Application:** Fine-grained anime event detection, visual moment recognition, and cut-point synchronization for LolixCopilot's AI Director.
**Demonstration Domain:** *Jujutsu Kaisen* (Iconic Combat & Technique Sequences: Gojo Satoru's Hollow Purple, Sukuna's Malevolent Shrine, Megumi's Domain Expansion).

---

## 1. Objective & Scope

General multimodal models frequently recognize general franchises (e.g., "This clip is from Jujutsu Kaisen") but struggle to identify **exact narrative moments**, **keyframe peaks**, and **precise cut boundaries** (e.g., "Gojo Satoru executing *Kyoshiki Murasaki* (Hollow Purple), peak convergence frame at 00:22.8, cut point at 00:24.0").

This dataset provides ground-truth temporal bounding and semantic descriptors to train and benchmark:
1. **Source & Event Classification:** Exact franchise, arc, episode, and named event/technique.
2. **Temporal Localization:** Start, peak, and end timestamps accurate to within $\pm 0.5$ seconds for editing sync.
3. **Evidence Grounding:** Visual and motion markers justifying the detection.
4. **Modality Separation:** Audio/soundtrack recognition is decoupled and benchmarked as a distinct task.

---

## 2. Labeled Sample Schema

Every dataset item conforms to the following strict JSON schema:

```json
{
  "sample_id": "jkk-event-001",
  "source_title": "Jujutsu Kaisen",
  "franchise": "Jujutsu Kaisen",
  "season": 1,
  "episode": 20,
  "arc": "Kyoto Goodwill Event Arc",
  "event_name": "Gojo Satoru - Hollow Purple (Kyoshiki Murasaki)",
  "approx_start_seconds": 12.40,
  "approx_end_seconds": 28.20,
  "peak_frame_timestamp": 22.80,
  "duration_seconds": 15.80,
  "representative_frames": [
    {
      "timecode": "00:14.20",
      "frame_type": "setup",
      "description": "Gojo holding out right hand generating Cursed Technique Lapse: Blue"
    },
    {
      "timecode": "00:18.50",
      "frame_type": "convergence",
      "description": "Left hand generating Cursed Technique Reversal: Red"
    },
    {
      "timecode": "00:22.80",
      "frame_type": "peak_fusion",
      "description": "Fusing Red and Blue into a luminous violet sphere, spatial distortion"
    },
    {
      "timecode": "00:26.10",
      "frame_type": "discharge",
      "description": "High-velocity purple beam carving massive trench through forest"
    }
  ],
  "visual_evidence": [
    "Converging dual energy spheres (red and blue)",
    "Blindfold removed / raised, revealing Six Eyes (Rikugan)",
    "High-contrast purple particle effects and ground trench excavation",
    "Gojo hand sign: fingertips snapping forward"
  ],
  "status": "confirmed",
  "alternative_candidates": [
    "Cursed Technique Reversal: Red",
    "Unlimited Void (Muryokusho - Domain Expansion)"
  ],
  "audio_task_reference": {
    "has_audio": true,
    "soundtrack_title": "Your Battle is My Battle",
    "artist": "Hiroaki Tsutsumi",
    "audio_match_status": "strong_inference",
    "audio_notes": "Heavy electric guitar riff coinciding with projectile release at 00:23.0"
  }
}
```

---

## 3. Dataset Construction & Sampling Strategy

### 3.1 Positive Examples (True Instances of Hollow Purple)
To ensure robustness across varied real-world creator uploads, positive samples must include:
1. **Raw Broadcast & Blu-ray Footage:** Unedited clips with native 24fps cadence and original color grading.
2. **Velocity Edits & Montages (AMVs):** Community-edited clips featuring speed ramps (twixtor), motion blur, color grading (LUTs), and letterboxing.
3. **Aspect Ratio Variations:** 16:9 widescreen, 9:16 vertical reels/TikTok crops, and 1:1 square formats.
4. **Different Angles & Encounters:**
   - Kyoto Goodwill Arc (Ep 20) vs Hanami.
   - Shibuya Incident (Season 2) vs Toji Fushiguro (Teen Gojo / Hidden Inventory Arc, Ep 28).

### 3.2 Negative Examples (Hard Distractors)
To prevent false-positive over-triggering on any purple visual effect, include:
1. **Intra-Franchise Distractors:**
   - Gojo using *Cursed Technique Lapse: Blue* alone.
   - Gojo using *Cursed Technique Reversal: Red* alone.
   - Megumi Fushiguro summoning shadows (Divine Dog / Mahoraga) with dark silhouettes.
   - Non-combat dialogue scenes featuring Gojo.
2. **Inter-Franchise Distractors:**
   - Purple energy attacks from other anime (e.g., Vegeta's Galick Gun in *Dragon Ball*, Ichigo's Getsuga Tensho in *Bleach*, Hollow energy in *Bleach*).
   - High-contrast neon fight scenes from *Cyberpunk: Edgerunners* or *Demon Slayer*.

---

## 4. Evaluation Metrics for Timestamp Accuracy

Evaluating temporal event boundaries in video editing requires tighter tolerances than generic video captioning:

### 4.1 Temporal Intersection-over-Union (tIoU)
$$\text{tIoU} = \frac{|\mathcal{I}_{\text{pred}} \cap \mathcal{I}_{\text{gt}}|}{|\mathcal{I}_{\text{pred}} \cup \mathcal{I}_{\text{gt}}|}$$
- Benchmark thresholds: **tIoU@0.3**, **tIoU@0.5**, and **tIoU@0.75**.
- An editing recommendation is considered actionable if $\text{tIoU} \ge 0.5$.

### 4.2 Peak Frame Timestamp Error ($\Delta t_{\text{peak}}$)
$$\Delta t_{\text{peak}} = |t_{\text{pred\_peak}} - t_{\text{gt\_peak}}|$$
- In video editing, cutting on the exact beat or peak impact frame is critical.
- **Success Criteria:** $\Delta t_{\text{peak}} \le 0.50\text{ seconds}$ (within 12 frames at 24fps).

### 4.3 Classification Metrics
- Standard Precision, Recall, and F1-score for event categorization:
  $$\text{F1} = \frac{2 \cdot P \cdot R}{P + R}$$

---

## 5. Separation of Audio & Soundtrack Intelligence

Soundtrack identification operates under independent constraints:
- **Audio Fingerprinting vs Multimodal Inference:** Multimodal LLMs deduce soundtrack titles through contextual training and lyrics, not exact acoustic hash matching (like ACRCloud or Shazam).
- **Decoupled Evaluation:**
  - Visual dataset benchmarks solely visual events and timing.
  - Audio evaluation benchmarks whether the system correctly detects BGM shifts, tempo changes, and song titles, labeled as `confirmed_match`, `strong_inference`, or `unconfirmed`.
