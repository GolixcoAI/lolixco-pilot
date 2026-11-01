# LolixCopilot — Muse Open Models Research & Experiments Analysis

**Document Purpose:** Synthesize findings from the Meta Global Hackathon Muse experiments conducted by Sinan Ozdemir ([`sinanuozdemir/ai-experiments/experiments/meta-hackathon-muse`](https://github.com/sinanuozdemir/ai-experiments/tree/main/experiments/meta-hackathon-muse)), and translate empirical insights into concrete architectural decisions for **LolixCopilot**.

---

## 1. Executive Summary & Core Insights

The reference repository evaluates **Muse Spark Open** and **Muse Glimmer** across short-answer reasoning suites, reasoning-effort sweeps, and prompt-routing tasks.

### Key Empirical Findings

1. **Reasoning-Effort Sweet Spot:** On structured short-answer tasks, Muse Spark Open peaks in performance at `reasoning_effort="low"` (**88.5%** overall accuracy).
2. **The High-Effort Truncation Trap:** Increasing reasoning effort to `high`, `xhigh`, or `max` degrades accuracy (falling to **81.8%–83.0%**). At `max`, **19 of 400 responses (4.75%) returned empty** because the model exhausted its 2,048-token generation limit entirely within intermediate reasoning before producing any final answer.
3. **No Zero-Reasoning Mode:** Muse Spark Open always engages its reasoning engine; passing `reasoning_effort="none"` is rejected by the model gateway.
4. **Head-to-Head vs DeepSeek:** At `reasoning_effort="low"`, Muse Spark Open outperforms DeepSeek V4.1 Flash (+2.0% overall across GSM8K, NQ-Open, BoolQ, and ARC-Easy). It shows notable strength in open-ended factual recall (+7.0% on NQ-Open) and numeric reasoning (+3.0% on GSM8K).
5. **Prompt Routing Feasibility & Cost:** Fine-tuning Muse Glimmer 30B as an intent/complexity router achieved 90% routing accuracy, but requires dedicated GPU-hour hosting that is economically and operationally unjustified for our hackathon scope.

---

## 2. Detailed Experiment Summaries & Numerical Results

### Experiment 1: Short-Answer Suite — Muse Spark Open vs DeepSeek V4.1 Flash

**Protocol:** 100 samples per benchmark ($n=400$ total), deterministic grading, `reasoning_effort="low"`.

| Benchmark | Task Domain | Answer Type | Muse Spark Open | DeepSeek V4.1 Flash | Delta ($\Delta$) |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **GSM8K** | Math / Numeric | Number ($\pm 1\%$) | **99.0%** | 96.0% | **+3.0%** |
| **NQ-Open** | Open Factoid | Exact String Alias | **69.0%** | 62.0% | **+7.0%** |
| **BoolQ** | Reading Comp | Boolean Yes/No | 90.0% | **91.0%** | −1.0% |
| **ARC-Easy** | Science Q&A | Multiple Choice (A–D)| 96.0% | **97.0%** | −1.0% |
| **Overall** | **Combined Suite** | **Deterministic** | **88.5%** | **86.5%** | **+2.0%** |

*Head-to-head breakdown:* Across 400 pairs, Muse won 16, DeepSeek won 8, with 376 ties. Published Specialized Intelligence Index (SII) benchmarks independently corroborate Muse's lead in domain-specialized reasoning (+12.7% on Big Finance, +8.7% on Bedside Bench, +5.6% on HealthBench Professional, +5.0% on Redline Bench).

---

### Experiment 2: Muse Reasoning-Effort Sweep

**Protocol:** Same 400-item suite evaluated solely with Muse Spark Open across all 6 supported effort tiers.

| Benchmark | `minimal` | `low` | `medium` | `high` | `xhigh` | `max` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **GSM8K** | 98.0% | **99.0%** | **99.0%** | 94.0% | 98.0% | 97.0% |
| **BoolQ** | **93.0%** | 90.0% | **93.0%** | 86.0% | 89.0% | 84.0% |
| **NQ-Open** | 64.0% | **69.0%** | 67.0% | 64.0% | 66.0% | 65.0% |
| **ARC-Easy** | 95.0% | **96.0%** | 92.0% | 83.0% | 85.0% | 86.0% |
| **Overall Accuracy** | **87.5%** | **88.5%** | **87.8%** | **81.8%** | **84.5%** | **83.0%** |
| **Empty / Truncated**| 0 / 400 | 0 / 400 | 0 / 400 | 2 / 400 | 7 / 400 | **19 / 400** |

#### Why Higher Effort Degrades Performance on Bounded Tasks
1. **Output Token Exhaustion:** Because reasoning tokens count against the `max_tokens` cap, exhaustive chain-of-thought consumes the available window before the final JSON/answer is emitted.
2. **Overthinking Simple Constraints:** The model second-guesses direct boundaries, introducing circular reasoning loops.
3. **Latency Explosion:** Higher reasoning levels dramatically increase time-to-first-token and total completion latency without accuracy gain.

---

### Experiment 3: Muse Glimmer 30B as an Intent & Route Classifier

**Protocol:** LoRA Supervised Fine-Tuning (SFT) on Muse Glimmer 30B using 600 training prompts from the SupraLabs Prompt-Routing Dataset. Evaluated on 40 held-out prompts.

| Metric | Base Model | Tuned Router | Improvement |
| :--- | :---: | :---: | :---: |
| **Route Accuracy** | 22.5% | **90.0%** | +67.5% |
| **Exact Match (all JSON fields)** | 2.5% | **57.5%** | +55.0% (McNemar $p = 4.8\times 10^{-7}$) |
| **Unterminated / Malformed JSON** | 6 / 40 | **0 / 40** | Clean termination |

**Operational Caveat:** Training and deploying a dedicated 30B routing model requires spinning up persistent GPU instances that bill per GPU-hour. For a hackathon project with a $100 credit pool, standing up an intermediary router container burns funds rapidly for zero end-user video-editing value.

---

## 3. Critical Limitations Revealed by the Research

1. **Reasoning Token Budgeting:**
   In OpenAI-compatible inference (such as Baseten's `https://inference.baseten.co/v1`), reasoning tokens are reported under `usage.completion_tokens_details.reasoning_tokens`. If `max_tokens` is set too low (e.g. 1,000–1,500), the model will run out of tokens mid-reasoning, causing a fatal JSON parse error for LolixCopilot's `EditingBlueprint`.
2. **Video Modality Differs from Text Benchmarks:**
   The reference experiments tested text-only QA. Video understanding introduces high visual token counts (up to 96 sampled frames), meaning prompt token consumption will be significantly higher (~1,500–3,000 tokens before reasoning begins).
3. **No Native Video Audio in Vision Path:**
   As verified in Baseten's official documentation, Muse Spark Open's video processing path **completely ignores the audio track** of uploaded MP4/MOV videos. Spoken words, dialogue, and audio cues are invisible to the model unless speech is separately extracted and sent as an `audio_url` content part.

---

## 4. Recommendations for LolixCopilot

Based on these findings, LolixCopilot adopts the following concrete implementation rules:

### 1. Optimal Reasoning-Effort Setting
- Explicitly target `reasoning_effort="low"` (or let Baseten use its default low-effort routing).
- **Never set `reasoning_effort="high"` or `"max"`** for editing blueprint generation, as it risks burning tokens and causing empty/truncated JSON schemas.

### 2. Generous Completion Token Budget
- Maintain `max_tokens = 2500` (or higher, up to 3,500) in `backend/app/services/ai_provider.py`.
- This ensures 500–1,000 tokens of chain-of-thought reasoning can occur without truncating a 10-scene structured `EditingBlueprint`.

### 3. Strict Deterministic JSON Enforcement
- Continue using `response_format={"type": "json_object"}`.
- Keep system prompt schema instructions concise: define clear fields (`start_seconds`, `end_seconds`, `label`, `pacing`, `reason`) and state rules explicitly rather than using lengthy conversational framing.

### 4. Direct Baseten Invocation (No Glimmer Router)
- Route all analysis requests directly to `meta-models/muse-spark-open-1026` via Baseten.
- Do not implement a multi-model routing tier (DeepSeek vs Muse); keep the architecture clean and focused on video blueprint generation.

---

## 5. Proposed Future Video-Editing Evaluation Framework

To evaluate video understanding quality systematically without manual visual inspection, LolixCopilot plans the following deterministic benchmark framework:

```
┌──────────────────────────────────────────────────────────────┐
│          LolixCopilot Video Blueprint Benchmark (VBB)        │
└──────────────────────────────┬───────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Temporal    │       │  Pacing      │       │ Narrative    │
│  Boundary    │       │  Compliance  │       │ Semantic     │
│  Accuracy    │       │  Rate        │       │ Alignment    │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ Metric: IoU  │       │ Metric: Cut  │       │ Metric: BERT │
│ vs labeled   │       │ frequency vs │       │ Score vs     │
│ scene changes│       │ target style │       │ human brief  │
└──────────────┘       └──────────────┘       └──────────────┘
```

### Proposed Benchmark Suite

1. **Temporal Boundary Intersection-over-Union (t-IoU):**
   - Compare suggested scene boundaries $[t_{\text{start}}, t_{\text{end}}]$ against ground-truth PySceneDetect cut transitions on standard 60-second clips.
   - Score: $\text{t-IoU} \ge 0.70$ counted as a detected scene hit.

2. **Pacing Compliance Score:**
   - Measure average cut duration against user creative brief pacing:
     - `fast`: Mean scene duration $1.5\text{s} - 3.0\text{s}$.
     - `balanced`: Mean scene duration $3.5\text{s} - 6.0\text{s}$.
     - `slow`: Mean scene duration $6.5\text{s} - 12.0\text{s}$.
   - Binary compliance flag (1.0 or 0.0).

3. **Narrative & Reason Coherence:**
   - LLM-as-a-judge deterministic rubric grading the `reason` field:
     - Is the reason actionable for a human editor? (1 point)
     - Does it reference visual or auditory cues? (1 point)
     - Does it align with the requested creative style? (1 point)

4. **Cacheable Evaluation Harness:**
   - Modeled after `results.jsonl` in the Sinan Ozdemir repo: store video hash, brief hash, model response, token usage, and latency. Re-running the benchmark checks cache before issuing network requests.

---

## 6. Features Postponed (Out of Scope for MVP)

To safeguard hackathon credits and ensure core stability, the following ideas from the research are explicitly **postponed**:

1. **Muse Glimmer Prompt Router:**
   - *Reason:* Unnecessary complexity. All LolixCopilot footage requires video-capable Muse Spark Open; text-only models cannot process video inputs.
2. **LoRA Fine-Tuning Pipeline:**
   - *Reason:* Serverless training and deployment incur ongoing GPU-hour costs and do not improve the primary video upload-to-blueprint user experience.
3. **Live Audio Transcribe / Multi-Modal Audio Fusion in Phase 1:**
   - *Reason:* Phase 1 focuses on video visual cut planning. Audio extraction and dual `video_url` + `audio_url` fusion will be designed for Phase 2 using serverless FFmpeg workers.
