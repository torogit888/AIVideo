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
export const DEFAULT_CHANNEL_NAME = "白兔";
export const DEFAULT_CHANNEL_PRESETS = ["白兔", "黑貓"];
export const DEFAULT_CUSTOM_PROMPT = "開頭: 大家好~我是白兔!";

export function buildOpeningPromptLine(channelName: string): string {
  const clean = (channelName || "").trim();
  if (!clean || clean === "無自稱") {
    return "開頭: 無自稱（直接破題）";
  }
  return `開頭: 大家好~我是${clean}!`;
}

export function applyChannelPersonaToPrompt(currentPrompt: string, channelName: string): string {
  const openingLine = buildOpeningPromptLine(channelName);
  const raw = (currentPrompt || "").trim();
  if (!raw) {
    return openingLine;
  }
  const lines = raw.split("\n");
  const idx = lines.findIndex((l) => /^\s*開頭\s*[:：]/.test(l));
  if (idx >= 0) {
    lines[idx] = openingLine;
    return lines.join("\n");
  }
  return `${openingLine}\n${raw}`;
}

export function detectChannelFromPrompt(prompt: string): string {
  const raw = (prompt || "").trim();
  if (/無自稱|不自稱|直接破題/.test(raw)) {
    return "無自稱";
  }
  const m = raw.match(/我是\s*([^\s，,。！!？?~～\n]+)/);
  if (m && m[1]) {
    return m[1].trim();
  }
  return "";
}

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
