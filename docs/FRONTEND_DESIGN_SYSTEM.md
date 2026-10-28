# LolixCopilot — Frontend Design System & Workstation Specification

**Source of Truth:** Official brand assets and interface mockups in `docs/reference/`
- `lolixco-icon-reference.png`
- `lolixco-wordmark-reference.png`
- `Neon AI Editing Suite Interface.png`

---

## 1. Brand Identity & Visual Geometry

### The Lolixco Icon Mark
The official Lolixco icon consists of two interlocking geometric forms set against a deep black rounded square with subtle neon yellow ambient rim lighting:
1. **Outer/Lower Angle Bracket:** A bold, forward-slanted white (`#FFFFFF`) "L" shape with chamfered corner cuts on the bottom-left and top-right tip, providing an aggressive, architectural silhouette.
2. **Inner Playhead Arrow:** A solid, vibrant neon-yellow (`#FFE600` / `#E6FF00`) equilateral right-facing triangle nested inside the vertex of the "L", symbolizing playback, forward momentum, and AI-assisted creation.

### The Wordmark & Product Titling
- **Wordmark Typography:** Distinctive futuristic bold sans-serif with rounded squircle geometry and horizontal terminal cuts (`LOLIXCO`).
- **Product Branding:** **LOLIXCO** (in crisp white `#FFFFFF`) + **PILOT** (in electric neon yellow `#FFE600` / `#E6FF00`).
- **Tagline:** *"From raw footage to a stronger cut."*
- **Tone:** Professional, desktop-first, non-linear video editing workstation (competing aesthetically with Adobe Premiere Pro and DaVinci Resolve) fused with Lolixco's high-contrast neon identity.

---

## 2. Color Palette & Design Tokens

### Core Neutral Surfaces
- **Canvas / App Root:** `#050505` (True matte black, grounding the workstation).
- **Workspace Surface / Top Command Bar:** `#0A0C0F` / `#0D0F14` (Deep charcoal, defining primary panels).
- **Secondary Surfaces / Bins / Racks:** `#11141B` / `#131720` (Subtle elevation for media bins, inspector, and timeline tracks).
- **Card & Component Surfaces:** `#181C26` / `#1A1F2B` (Interactive items, clip blocks, and dropdowns).
- **Surface Hover:** `#222838` / `#283042` (Clear tactile feedback on cursor hover).
- **Borders & Dividers:**
  - Standard border: `#202532` (Thin, razor-sharp 1px dividers between workstation docks).
  - Subtle divider: `#171B24`
  - Active / Focus border: `#FFE600` (1.5px to 2px solid with optional subtle glow).

### The Primary Accent: Lolixco Neon Yellow
- **Default Accent:** `#FFE600` (High-vibrance neon yellow with green undertone, maximum contrast on pitch black).
- **Hover Accent:** `#FFF04D` / `#E6CF00`.
- **Accent Foreground:** `#000000` (Deep black text/icons on yellow buttons).
- **Accent Muted Background:** `rgba(255, 230, 0, 0.10)` to `rgba(255, 230, 0, 0.18)` (Used for active rail icons, selection pills, and badge backgrounds).
- **Accent Border Tint:** `rgba(255, 230, 0, 0.35)` to `rgba(255, 230, 0, 0.60)`.

### Semantic Moment Tags & Status Indicators
From `Neon AI Editing Suite Interface.png`:
- **HOOK Tag:** Text `#38BDF8`, Background `rgba(56, 189, 248, 0.15)`, Border `rgba(56, 189, 248, 0.30)` (Electric Cyan).
- **BUILD Tag:** Text `#FBBF24`, Background `rgba(251, 191, 36, 0.15)`, Border `rgba(251, 191, 36, 0.30)` (Warm Amber/Gold).
- **CLIMAX Tag:** Text `#F87171`, Background `rgba(248, 113, 113, 0.15)`, Border `rgba(248, 113, 113, 0.30)` (Crimson Coral).
- **RESOLVE Tag:** Text `#4ADE80`, Background `rgba(74, 222, 128, 0.15)`, Border `rgba(74, 222, 128, 0.30)` (Emerald Green).
- **Active Track V1:** Text `#FFE600`, Border `#FFE600`, Background `rgba(255, 230, 0, 0.12)`.
- **Audio Waveform (A1):** `#FFE600` waveform curve with keyframe nodes.

### Typography
- **Primary Interface:** Inter / Geist Sans / System UI (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
- **Timecode & Data:** Geist Mono / JetBrains Mono / SF Mono (`font-mono`), tabular numbers (`tabular-nums`) for jitter-free scrubbers.
- **Hierarchies:**
  - Workstation Headings: 13px - 14px bold, uppercase with letter-spacing `0.05em`.
  - Body / Details: 12px - 13px medium, regular.
  - Metadata / Badges / Timecodes: 10px - 11px monospace.

---

## 3. Workstation Composition & Layout Grid

The workstation is laid out as a professional docked application:

```text
+---------------------------------------------------------------------------------------------------------+
| [LOGO] LOLIXCOPILOT | Project Name ⌄        [API Status]     [Aspect 9:16 ⌄]  [Share]  [✦ Export]       | Top Command Bar (48px)
+----+----------------------+--------------------------------------------------+--------------------------+
|    | PROJECT MEDIA (+Imp) | PREVIEW MONITOR (Aspect Fit, 4K/60/HDR)          | ✦ AI DIRECTOR (Beta)     |
|    | [All] [Vid] [Aud]    |                                                  | Creative Brief           |
| N  | [Search...]          | [ Video Canvas with Real Seek / Playback ]       | [✦ Generate Blueprint →] |
| A  | +------------------+ |                                                  |                          |
| V  | | clip1    | clip2 | |                                                  | ✦ KEY MOMENTS (4)        |
|    | | [thumb]  | [thb] | +--------------------------------------------------+ | 1. 00:04.2 [HOOK] [Jump] |
| R  | +------------------+ | 00:18:24 / 00:32:16  |◀  ▶  ▶|  🔊 [---]  ⛶       | 2. 00:11.8 [BUILD][Jump] |
| A  | | clip3    | aud1  | +--------------------------------------------------+ | 3. 00:18.4 [CLIMAX][Jmp] |
| I  | | [thumb]  | [wav] | TIMELINE TOOLBAR (Undo, Redo, Split, Snap, Zoom)   | 4. 00:24.6 [RESOLVE][Jmp]|
| L  | +------------------+ |--------------------------------------------------+                          |
|    |                      | Ruler: 00:00   00:05   00:10   00:15   00:20...  | 💡 AI Suggestions        |
|    |                      | Playhead Needle (Bright Yellow)                  | ✔ Push-in before 00:04.2 |
|    |                      | [V2] [Track clips & fx]                          | ✔ Camera shake at climax |
|    |                      | [V1] [Sequenced cuts with scene thumbnails]      |                          |
|    |                      | [A1] [Neon yellow audio waveform]                |                          |
+----+----------------------+--------------------------------------------------+--------------------------+
```

### Layout Specifications
1. **Top Command Bar (Height: 48px):** Fixed top bar containing brand mark, project selector, live health telemetry badge, aspect ratio picker, share, and export CTA.
2. **Left Navigation Rail (Width: 64px):** Vertical mode switch (`Media`, `EditPilot`, `Timeline`, `Assets`).
3. **Media Bin Dock (Width: 280px - 320px):** Filterable assets with real file import, demo clips, and empty states.
4. **Center Preview Monitor (Flexible flex-1):** Responsive 16:9 / 9:16 / 1:1 viewport with standard transport controls, timecode readout, and scrubber.
5. **Right AI Director Panel (Width: 340px - 380px):** Creative brief input, constraints, one-click blueprint generation trigger, interactive key moments seeking player, and AI editorial suggestions.
6. **Bottom Timeline Dock (Height: 240px - 280px):** Full-width editing timeline with time ruler, synchronized playhead needle, multi-track channels (`V2`, `V1`, `A1`, `A2`), and clip blocks.

---

## 4. Interaction Rules & Honest States

1. **Player Synchronization:** Clicking any moment card's `[Jump]` button or clicking on the timeline ruler/clip seeks the HTML video element to that exact timestamp.
2. **Demo vs Live Separation:** When working with starter demo clips or generated blueprints, the UI explicitly labels demo moments versus uploaded content.
3. **No Fake Progress:** Buttons indicate their true capability; export and share indicate their status clearly without faking background rendering.
4. **Keyboard Accessibility:** All interactive elements support visible `:focus-visible` styling (`outline: 2px solid #FFE600`).
