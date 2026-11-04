# LolixCopilot — AI Director Architecture and Workflow

The AI Director is the primary creative interface of LolixCopilot. It translates natural-language editorial intent into grounded video understanding, actionable recommendations, timeline operations, and rendered exports.

## Core Responsibilities

1. **Conversational Understanding:** Distinguishes casual user dialogue (such as greetings, questions, or clarification requests) from concrete editing directives.
2. **Temporal Grounding:** Correlates semantic concepts (such as character abilities, high-energy combat, or scene transitions) to exact start and end timestamps in the uploaded video.
3. **Structured Blueprint Generation:** Formulates a strictly validated `EditingBlueprint` JSON schema with scene breakdowns, editorial justifications, and recommended actions.
4. **Interactive Timeline Synchronization:** Allows one-click application of edit recommendations to the multi-track timeline, including non-destructive trims, cuts, and timed text overlays.
5. **Execution Manifest Synthesis:** Compiles approved timeline state into an FFmpeg rendering recipe executed asynchronously on AWS Lambda.

## Conversational Editing Workflow

```
[User Chat Input] ──> [AI Director Dispatcher]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Casual Dialogue]               [Creative Instruction]
            │                                 │
     (Plain Markdown)              [Multi-Provider Routing]
            │                                 │
     (Returns text,            ┌──────────────┼──────────────┐
      no timeline mod)         ▼              ▼              ▼
                            [Modal]        [Meta]        [Baseten]
                            (Visual)     (Narrative)   (Blueprint)
                               └──────────────┬──────────────┘
                                              ▼
                                 [EditingBlueprint Validation]
                                              │
                                              ▼
                                [Streamed Assistant Response]
                                ├── Reasoning Markdown
                                ├── 6-Scene Breakdown Card
                                └── 5 Actionable Recommendations
                                              │
                                   [Apply to Timeline]
                                              │
                                              ▼
                                 [Timeline Tracks Updated]
                                 ├── V2: Text / Title Overlays
                                 ├── V1: Video Cuts & Trims
                                 └── A1: Synchronized Audio
```

## The Three Demonstrator Queries

LolixCopilot's AI Director is verified against three representative creator workflows:

### Query 1: Comprehensive Editorial Review

- **User Prompt:** "Review my edit."
- **Model Processing:** Analyzes overall pacing, scene progression, and narrative arc across the full video duration (00:00 to 01:08.08).
- **Output:**
  - 6 distinct scene breakdown items with timecode ranges, descriptive labels, and direct seek buttons.
  - 5 checkable recommendations covering hook enhancement, energy transitions, climax framing, and resolution timing.
  - Interactive "Jump to Moment" actions that seek the Preview Monitor instantly to the relevant frame.

### Query 2: Timed Text Overlay Injection

- **User Prompt:** "Add a title overlay for Hollow Purple."
- **Model Processing:** Grounds the user's semantic request to the visual event window where the technique converges (00:37.00 to 00:44.00).
- **Output:**
  - Injects a timed text overlay on Track V2 with text "Hollow Purple", start timestamp 37.00s, end timestamp 44.00s, centered positioning, and signature purple styling (`#a855f7`).
  - The overlay renders live in the Preview Monitor and burns into the final export via FFmpeg `libass` subtitles filtering.

### Query 3: Non-Destructive Last-30-Seconds Trim

- **User Prompt:** "Keep only the last 30 seconds."
- **Model Processing:** Calculates total video duration (68.08s) and determines the active range `[38.08s, 68.08s]`.
- **Output:**
  - Deactivates earlier footage non-destructively on Track V1 using hatched visual styling.
  - Remaps Track V2 overlays into the trimmed export coordinate space (Hollow Purple title shifts to `[0.00s, 5.92s]`).
  - Configures the export engine to produce an exact 30.00s output cut with synchronized audio.

## Telemetry and Latency Tracking

Every AI Director interaction tracks and surfaces real-world execution metrics:
- Provider utilized (`meta`, `modal`, `baseten`, or `auto`).
- Round-trip inference latency in seconds.
- Token consumption (prompt tokens, reasoning tokens, completion tokens).
- Estimated compute cost in USD.
