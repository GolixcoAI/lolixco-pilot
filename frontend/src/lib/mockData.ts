import { CreativeBriefState, KeyMoment, MediaClip } from "@/types/workstation";

export const INITIAL_DEMO_CLIPS: MediaClip[] = [
  {
    id: "clip-1",
    title: "city_rooftop.mp4",
    type: "video",
    duration: 28,
    size: "120 MB",
    resolution: "4K",
  },
  {
    id: "clip-2",
    title: "intense_closeup.mov",
    type: "video",
    duration: 12,
    size: "72 MB",
    resolution: "4K",
  },
  {
    id: "clip-3",
    title: "neon_streets.mp4",
    type: "video",
    duration: 16,
    size: "98 MB",
    resolution: "4K",
  },
  {
    id: "clip-4",
    title: "character_walk.mp4",
    type: "video",
    duration: 10,
    size: "64 MB",
    resolution: "4K",
  },
  {
    id: "clip-5",
    title: "explosion_fx.mp4",
    type: "video",
    duration: 8,
    size: "45 MB",
    resolution: "4K",
  },
  {
    id: "clip-6",
    title: "ambient_music.wav",
    type: "audio",
    duration: 204, // 03:24
    size: "48 MB",
    resolution: "WAV",
  },
];

export const INITIAL_KEY_MOMENTS: KeyMoment[] = [
  {
    id: "moment-1",
    index: 1,
    timecode: "00:04.2",
    seconds: 4.2,
    tag: "HOOK",
    title: "Opening tension",
    description: "Establish the scene and mood with a strong opening shot.",
    action: "Cut on head turn, slow push in",
  },
  {
    id: "moment-2",
    index: 2,
    timecode: "00:11.8",
    seconds: 11.8,
    tag: "BUILD",
    title: "Visual reveal",
    description: "Introduce the environment and main subject.",
    action: "Match cut with horizon flare",
  },
  {
    id: "moment-3",
    index: 3,
    timecode: "00:18.4",
    seconds: 18.4,
    tag: "CLIMAX",
    title: "Peak motion",
    description: "High-energy sequence with maximum visual impact.",
    action: "Speed ramp into jump cut",
  },
  {
    id: "moment-4",
    index: 4,
    timecode: "00:24.6",
    seconds: 24.6,
    tag: "RESOLVE",
    title: "Final beat",
    description: "Slow down, emotional resolution and memorable ending.",
    action: "Hold on silhouette fade",
  },
];

export const INITIAL_BRIEF: CreativeBriefState = {
  title: "Build tension, then release",
  description:
    "Create a cinematic, fast-paced edit with a strong hook, emotional build-up, and a powerful ending.",
  style: "Cinematic",
  pacing: "Fast → Slow",
  aspectRatio: "9:16",
  targetDuration: 30,
};

export const INITIAL_AI_SUGGESTIONS = [
  "Use a slower push-in before 00:04.2 to increase tension.",
  "Add subtle camera shake during 00:18.4 – 00:22.0.",
  "Consider a slight speed ramp for a more dynamic feel.",
  "End with a clean silhouette shot and hold for 1–2 seconds.",
];
