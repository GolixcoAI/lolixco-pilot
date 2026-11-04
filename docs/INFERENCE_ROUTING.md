# LolixCopilot — Inference Routing and Auto Mode Specification

This document details how LolixCopilot's AI Orchestrator routes requests across providers and synthesizes results into a unified, actionable editing plan.

## Orchestration Architecture

When a user interacts with the AI Director, the request can either target a specific provider explicitly (`modal`, `meta`, or `baseten`) or execute in **Auto Mode** (`auto`).

```
                    ┌────────────────────────────┐
                    │    User Request Ingest     │
                    │  (e.g., "Review my edit")  │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │    Intent Classifier       │
                    │  (Conversational vs Edit)  │
                    └─────────────┬──────────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           ▼                                             ▼
  [Conversational]                               [Edit Operation]
  (Meta Muse Spark)                                      │
  • Responds in natural text                             ▼
  • Zero timeline mutation                 ┌────────────────────────────┐
                                           │   Auto Mode Orchestration  │
                                           └─────────────┬──────────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        ▼                                ▼                                ▼
             [Stage 1: Modal H100]             [Stage 2: Meta API]              [Stage 3: Baseten]
             • Visual frame grounding          • Creative narrative reasoning   • Structured blueprint
             • Character/action recognition    • Editorial pacing notes           synthesis
             • Peak timestamp localization     • User intent translation        • JSON schema validation
                        │                                │                                │
                        └────────────────────────────────┼────────────────────────────────┘
                                                         │
                                                         ▼
                                           ┌────────────────────────────┐
                                           │  Synthesized Blueprint     │
                                           │  • Validated Timestamps    │
                                           │  • 6-Scene Cards           │
                                           │  • 5 Recommendations       │
                                           └─────────────┬──────────────┘
                                                         │
                                                         ▼
                                           ┌────────────────────────────┐
                                           │   Workstation Application  │
                                           │   • Multi-Track Timeline   │
                                           │   • Preview Monitor Sync   │
                                           └────────────────────────────┘
```

## Step-by-Step Auto Mode Execution

1. **Visual Scene Grounding (Modal H100):**
   - The video is analyzed for key visual events, character actions, and scene transitions.
   - Outputs temporal coordinates for keyframe peaks (such as technique convergence at 00:22.80).
2. **Creative Narrative Reasoning (Meta Muse Spark 1.3):**
   - Ingests the user prompt alongside visual evidence from Stage 1.
   - Evaluates narrative pacing, tension buildup, and climax positioning.
   - Produces conversational explanations and creative rationales for each recommended cut.
3. **Structured Plan Synthesis (Baseten Muse Spark Open):**
   - Formulates the structured `EditingBlueprint` JSON schema.
   - Enforces valid SMPTE timestamps conforming to `0 <= start < end <= duration`.
   - Generates actionable timeline operations (cuts, speed ramps, title overlays).
4. **Pydantic Validation & Delivery:**
   - The backend validates the synthesized blueprint against `backend/app/models/blueprint.py`.
   - The validated blueprint is delivered to the frontend, updating the AI Director chat, scene cards, and timeline tracks simultaneously.

## Resilience and Fallback Mechanisms

If a provider encounters an outage, rate limit, or network timeout, the orchestrator executes deterministic fallback procedures:

| Failure Scenario | Primary Path | Fallback Action | Graceful Degradation |
|---|---|---|---|
| **Modal Unavailable** | H100 visual moment grounding | Baseten visual frame sampling | Generates blueprint without deep visual features |
| **Meta API Rate-Limited** | Muse Spark creative reasoning | Baseten chain-of-thought generation | Emits structured plan with concise automated notes |
| **Baseten Outage** | Muse Spark Open blueprint generation | Meta Model API structured output | Formats blueprint via Meta JSON mode |
| **Complete Provider Outage** | External cloud inference | Local deterministic rule engine | Returns safe, valid scene cuts based on FFprobe markers |

In all failure modes, the system displays an informative notification to the user and avoids producing corrupted timeline data.
