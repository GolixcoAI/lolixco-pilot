export interface MediaClip {
  id: string;
  title: string;
  type: "video" | "audio" | "image";
  duration: number; // in seconds
  size: string;
  resolution?: string;
  src?: string;
  thumbnail?: string;
  isCustom?: boolean;
}

export type MomentTag = "HOOK" | "BUILD" | "CLIMAX" | "RESOLVE";

export interface KeyMoment {
  id: string;
  index: number;
  timecode: string;
  seconds: number;
  endSeconds?: number;
  tag: MomentTag;
  title: string;
  description: string;
  action: string;
  thumbnail?: string;
}

export interface CreativeBriefState {
  title: string;
  description: string;
  style: string;
  pacing: string;
  aspectRatio: "9:16" | "16:9" | "1:1";
  targetDuration: number;
}
