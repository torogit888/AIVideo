import {
  AssetStyle,
  AssetTone,
  AssetVoice,
  JobSummary,
  JobDetail,
  SceneDetail,
  SceneSummary,
  JobVisualAnchors,
  AnalyzeAnchorsResponse,
  YouTubeAuthStatus,
  YouTubePrepareData,
  YouTubeOptimizeResponse,
  YouTubeGenerateThumbnailResponse,
  YouTubeUploadPayload,
  YouTubeUploadStatus,
} from "./types";

const BASE_URL = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `API 請求失敗 (${res.status} ${res.statusText})`);
    }
    return res.json();
  } catch (err: any) {
    if (err.message === "Failed to fetch" || err.name === "TypeError") {
      throw new Error("無法連線至 Studio 後端服務 (Port 8000)，伺服器可能正在熱重載或尚未啟動。");
    }
    throw err;
  }
}

export const api = {
  // 系統健康
  getSystemStatus: () => request<{ gemini_configured: boolean; comfyui_url: string; comfyui_online: boolean; repo_root: string }>("/system/status"),

  // 專案
  getJobs: () => request<JobSummary[]>("/jobs"),
  getJobDetail: (id: string) => request<JobDetail>(`/jobs/${id}`),
  createJob: (data: any) => request<JobSummary>("/jobs", { method: "POST", body: JSON.stringify(data) }),
  updateJob: (
    id: string,
    patch: {
      title?: string;
      voice_id?: string;
      style_id?: string;
      image_model?: string;
      custom_prompt?: string;
      outline?: string;
      tone_id?: string;
      script?: string;
    }
  ) => request<JobSummary>(`/jobs/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteJob: (id: string) => request<any>(`/jobs/${id}`, { method: "DELETE" }),
  clearJobMedia: (id: string) => request<any>(`/jobs/${id}/clear`, { method: "POST" }),
  clearJobImages: (id: string) => request<any>(`/jobs/${id}/clear-images`, { method: "POST" }),

  // 視覺一致性與主體定裝參考 (Visual Continuity)
  analyzeAnchors: (topic: string, script: string, styleId?: string) =>
    request<AnalyzeAnchorsResponse>("/jobs/analyze-anchors", {
      method: "POST",
      body: JSON.stringify({ topic, script, style_id: styleId }),
    }),
  getJobAnchors: (jobId: string) => request<JobVisualAnchors>(`/jobs/${jobId}/anchors`),
  updateJobAnchors: (
    jobId: string,
    patch: {
      subject?: string;
      environment?: string;
      use_image_reference?: boolean;
      characters?: { id?: string; name: string; appearance: string }[];
    }
  ) =>
    request<JobVisualAnchors>(`/jobs/${jobId}/anchors`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  generateHeroAnchor: (jobId: string) =>
    request<{ success: boolean; message: string; hero_image_url: string; generated_count?: number }>(
      `/jobs/${jobId}/anchors/hero`,
      { method: "POST" }
    ),
  uploadHeroAnchor: async (jobId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/jobs/${jobId}/anchors/hero/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "定裝參考圖上傳失敗");
    }
    return res.json() as Promise<{ success: boolean; message: string; hero_image_url: string }>;
  },
  deleteHeroAnchor: (jobId: string) => request<any>(`/jobs/${jobId}/anchors/hero`, { method: "DELETE" }),
  addCharacterAnchor: (jobId: string, data: { name: string; appearance?: string }) =>
    request<JobVisualAnchors>(`/jobs/${jobId}/anchors/characters`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteCharacterAnchor: (jobId: string, charId: string) =>
    request<JobVisualAnchors>(`/jobs/${jobId}/anchors/characters/${charId}`, { method: "DELETE" }),
  generateCharacterHero: (jobId: string, charId: string) =>
    request<JobVisualAnchors>(`/jobs/${jobId}/anchors/characters/${charId}/hero`, { method: "POST" }),
  uploadCharacterHero: async (jobId: string, charId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/jobs/${jobId}/anchors/characters/${charId}/hero/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "角色定裝圖上傳失敗");
    }
    return res.json() as Promise<JobVisualAnchors>;
  },
  deleteCharacterHero: (jobId: string, charId: string) =>
    request<JobVisualAnchors>(`/jobs/${jobId}/anchors/characters/${charId}/hero`, { method: "DELETE" }),
  syncScenePrompts: (jobId: string) =>
    request<{ success: boolean; message: string; updated_count: number }>(`/jobs/${jobId}/anchors/sync-prompts`, {
      method: "POST",
    }),

  // 分鏡與右側抽屜
  getScenes: (jobId: string) => request<SceneSummary[]>(`/jobs/${jobId}/scenes`),
  getSceneDetail: (jobId: string, sceneId: string) => request<SceneDetail>(`/jobs/${jobId}/scenes/${sceneId}`),
  patchScene: (jobId: string, sceneId: string, patch: Partial<SceneDetail>) =>
    request<SceneDetail>(`/jobs/${jobId}/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  regenerateImage: (jobId: string, sceneId: string) =>
    request<any>(`/jobs/${jobId}/scenes/${sceneId}/image`, { method: "POST" }),
  clearSceneImage: (jobId: string, sceneId: string) =>
    request<SceneDetail>(`/jobs/${jobId}/scenes/${sceneId}/image`, { method: "DELETE" }),
  clearScenePip: (jobId: string, sceneId: string) =>
    request<SceneDetail>(`/jobs/${jobId}/scenes/${sceneId}/pip`, { method: "DELETE" }),
  regenerateAudio: (jobId: string, sceneId: string) =>
    request<any>(`/jobs/${jobId}/scenes/${sceneId}/audio`, { method: "POST" }),
  fetchScenePip: (jobId: string, sceneId: string, query?: string) =>
    request<any>(`/jobs/${jobId}/scenes/${sceneId}/pip`, {
      method: "POST",
      body: JSON.stringify(query ? { query } : {}),
    }),

  // 腳本與大綱
  generateOutline: (topic: string, toneId: string, model?: string, userPrompt?: string) =>
    request<{ outline: string }>("/script/generate-outline", {
      method: "POST",
      body: JSON.stringify({ topic, tone_id: toneId, model, user_prompt: userPrompt }),
    }),

  generateScript: (
    topic: string,
    toneId: string,
    wordCount: number,
    model?: string,
    notes?: string,
    userPrompt?: string
  ) =>
    request<{ script: string; word_count: number; estimated_scenes: number }>("/script/generate", {
      method: "POST",
      body: JSON.stringify({
        topic,
        tone_id: toneId,
        word_count: wordCount,
        model,
        notes,
        user_prompt: userPrompt,
      }),
    }),

  expandScript: (script: string, topic?: string, toneId?: string, targetWordCount?: number, model?: string) =>
    request<{ script: string; word_count: number; estimated_scenes: number }>("/script/expand", {
      method: "POST",
      body: JSON.stringify({
        script,
        topic: topic || "",
        tone_id: toneId || "michelin_curious",
        target_word_count: targetWordCount || 3500,
        model,
      }),
    }),

  // 素材庫
  getStyles: () => request<AssetStyle[]>("/assets/styles"),
  createStyle: (data: any) => request<AssetStyle>("/assets/styles", { method: "POST", body: JSON.stringify(data) }),
  updateStyle: (id: string, data: any) =>
    request<AssetStyle>(`/assets/styles/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteStyle: (id: string) => request<any>(`/assets/styles/${id}`, { method: "DELETE" }),

  getTones: () => request<AssetTone[]>("/assets/tones"),
  createTone: (data: any) => request<AssetTone>("/assets/tones", { method: "POST", body: JSON.stringify(data) }),
  extractAndSaveTone: (data: { text: string; tone_id?: string; auto_save?: boolean; model?: string; title?: string }) =>
    request<AssetTone>("/assets/tones/extract-and-save", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateTone: (id: string, data: any) =>
    request<AssetTone>(`/assets/tones/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTone: (id: string) => request<any>(`/assets/tones/${id}`, { method: "DELETE" }),

  getVoices: () => request<AssetVoice[]>("/assets/voices"),
  createVoice: (data: any) => request<AssetVoice>("/assets/voices", { method: "POST", body: JSON.stringify(data) }),
  updateVoice: (id: string, data: any) =>
    request<AssetVoice>(`/assets/voices/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  testVoice: (id: string, data?: { text?: string; speed?: number; position_temperature?: number; steps?: number; mode?: string }) =>
    request<{ success: boolean; test_audio_url: string; message: string }>(`/assets/voices/${id}/test`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    }),
  deleteVoice: (id: string) => request<any>(`/assets/voices/${id}`, { method: "DELETE" }),

  // 流水線批次
  runPipeline: (jobId: string, action: string, force = false, burnSubtitles?: boolean) =>
    request<any>("/pipeline/run", {
      method: "POST",
      body: JSON.stringify({
        job_id: jobId,
        action,
        force,
        only_missing: !force,
        burn_subtitles: burnSubtitles,
      }),
    }),
  stopPipeline: (jobId: string) =>
    request<any>(`/pipeline/stop?job_id=${jobId}`, { method: "POST" }),

  // SSE 即時串流
  subscribePipeline: (jobId: string, onMessage: (data: any) => void) => {
    const es = new EventSource(`${BASE_URL}/pipeline/stream?job_id=${encodeURIComponent(jobId)}`);
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error("SSE parse error", e);
      }
    };
    return () => es.close();
  },

  // YouTube 發布整合
  getYouTubeStatus: () => request<YouTubeAuthStatus>("/youtube/status"),
  uploadYouTubeSecret: (content: string) =>
    request<{ status: string; message: string }>("/youtube/auth/secret", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  getYouTubeAuthUrl: (redirectUri?: string) =>
    request<{ auth_url: string }>(`/youtube/auth/url${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ""}`),
  exchangeYouTubeCode: (code: string, redirectUri?: string) =>
    request<YouTubeAuthStatus>("/youtube/auth/exchange", {
      method: "POST",
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    }),
  prepareYouTubeUpload: (jobId: string) => request<YouTubePrepareData>(`/youtube/prepare/${encodeURIComponent(jobId)}`),
  saveYouTubeMetadata: (payload: {
    job_id: string;
    title: string;
    description?: string;
    tags?: string[];
    privacy_status?: string;
    candidate_titles?: string[];
  }) =>
    request<{ status: string; message: string }>("/youtube/metadata", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateExistingYouTubeVideo: (payload: {
    job_id: string;
    video_id?: string;
    title?: string;
    description?: string;
    tags?: string[];
    privacy_status?: string;
    upload_thumbnail?: boolean;
  }) =>
    request<any>("/youtube/update-existing", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  optimizeYouTubeMetadata: (jobId: string) =>
    request<YouTubeOptimizeResponse>("/youtube/optimize-metadata", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId }),
    }),
  generateYouTubeThumbnail: (jobId: string, title?: string, prompt?: string) =>
    request<YouTubeGenerateThumbnailResponse>("/youtube/generate-thumbnail", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, title, prompt }),
    }),
  uploadToYouTube: (payload: YouTubeUploadPayload) =>
    request<{ status: string; job_id: string; message: string }>("/youtube/upload", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getYouTubeUploadStatus: () => request<YouTubeUploadStatus>("/youtube/upload/status"),
};
