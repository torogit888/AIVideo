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
  hasFilm: boolean,
  filmStale = false
): { label: string; action: "all" | "images" | "tts" | "compose" | "preview" | null } {
  if (total <= 0) return { label: "生成腳本", action: null };
  if (imagesReady < total || audioReady < total || !hasFilm || filmStale) {
    return { label: "一鍵全流程", action: "all" };
  }
  return { label: "預覽成片", action: "preview" };
}

export const DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image";
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

export function formatDurationClock(sec: number): string {
  const total = Math.max(0, Math.round(sec || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}:${String(remM).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function estimateJobDuration(
  scenes: { status: { has_audio: boolean; duration?: number } }[],
  fallbackEstimatedSec?: number,
  fallbackTotalScenes?: number
): {
  totalScenes: number;
  readyAudioCount: number;
  totalAudioSec: number;
  estimatedTotalSec: number;
  isAllAudioDone: boolean;
  formattedDuration: string;
  tooltip: string;
} {
  const totalScenes = scenes.length || fallbackTotalScenes || 0;
  const readyAudioScenes = scenes.filter((s) => s.status.has_audio && (s.status.duration || 0) > 0);
  const readyAudioCount = scenes.filter((s) => s.status.has_audio).length;
  const totalAudioSec = readyAudioScenes.reduce((sum, s) => sum + (s.status.duration || 0), 0);

  let estimatedTotalSec = 0;
  if (readyAudioScenes.length === totalScenes && totalScenes > 0 && totalAudioSec > 0) {
    estimatedTotalSec = totalAudioSec;
  } else if (readyAudioScenes.length > 0 && totalScenes > 0) {
    const avgSec = totalAudioSec / readyAudioScenes.length;
    estimatedTotalSec = totalAudioSec + avgSec * (totalScenes - readyAudioScenes.length);
  } else if (fallbackEstimatedSec && fallbackEstimatedSec > 0) {
    estimatedTotalSec = fallbackEstimatedSec;
  } else if (totalScenes > 0) {
    estimatedTotalSec = totalScenes * 5.5;
  }

  const isAllAudioDone = readyAudioCount === totalScenes && totalScenes > 0;
  const formattedDuration = formatDurationClock(estimatedTotalSec);
  const tooltip = isAllAudioDone
    ? `全部分鏡已完成配音，成片總長度預計為 ${formattedDuration} (${Math.round(totalAudioSec)} 秒)`
    : readyAudioScenes.length > 0
    ? `已完成 ${readyAudioCount}/${totalScenes} 幕配音 (${formatDurationClock(totalAudioSec)})，依平均時長預估全片長度約 ${formattedDuration}`
    : `尚未生成語音，依標準每幕 5.5 秒預估全片長度約 ${formattedDuration}`;

  return {
    totalScenes,
    readyAudioCount,
    totalAudioSec,
    estimatedTotalSec,
    isAllAudioDone,
    formattedDuration,
    tooltip,
  };
}

