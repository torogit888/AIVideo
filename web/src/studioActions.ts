export function srtMediaUrl(jobId: string): string {
  return `/media/jobs/${encodeURIComponent(jobId)}/compose/timeline.srt`;
}

export function asciiSlug(text: string, fallback = "story"): string {
  const cleaned = (text || "").replace(/[^A-Za-z0-9\s_-]/g, "").trim();
  const slug = cleaned.replace(/[-\s]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30);
  return slug || fallback;
}

export function primaryPipelineAction(
  imagesReady: number,
  audioReady: number,
  total: number,
  hasFilm: boolean
): { label: string; action: "images" | "tts" | "compose" | "preview" | null } {
  if (total <= 0) return { label: "生成腳本", action: null };
  if (imagesReady < total) return { label: "生成未完成畫面", action: "images" };
  if (audioReady < total) return { label: "生成配音", action: "tts" };
  if (!hasFilm) return { label: "合成 1080p", action: "compose" };
  return { label: "預覽成片", action: "preview" };
}

export const DEFAULT_VOICE_ID = "tw_female01";
export const DEFAULT_USE_PIP = true;

export const STORYBOARD_GHOST_ACTIONS = ["images", "tts", "compose"] as const;
export const STORYBOARD_OVERFLOW_ACTIONS = [
  "continuity",
  "pip",
  "clear_images",
  "clear_audio",
  "clear_all",
  "force",
] as const;
export const CONNECTION_LIGHTS = ["gemini", "comfy"] as const;

export function scriptWorkspaceMode(jobId: string | null | undefined): "new" | "edit" {
  return jobId ? "edit" : "new";
}

export function shouldPromptRecut(scriptChanged: boolean, hasScenes: boolean): boolean {
  return Boolean(scriptChanged && hasScenes);
}
