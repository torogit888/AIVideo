import { AssetStyle, AssetTone, AssetVoice, JobSummary, SceneDetail, SceneSummary } from "./types";

const BASE_URL = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API 請求失敗");
  }
  return res.json();
}

export const api = {
  // 專案
  getJobs: () => request<JobSummary[]>("/jobs"),
  getJobDetail: (id: string) => request<any>(`/jobs/${id}`),
  createJob: (data: any) => request<JobSummary>("/jobs", { method: "POST", body: JSON.stringify(data) }),
  deleteJob: (id: string) => request<any>(`/jobs/${id}`, { method: "DELETE" }),

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
  regenerateAudio: (jobId: string, sceneId: string) =>
    request<any>(`/jobs/${jobId}/scenes/${sceneId}/audio`, { method: "POST" }),

  // 腳本
  generateScript: (topic: string, toneId: string, wordCount: number) =>
    request<{ script: string; word_count: number; estimated_scenes: number }>("/script/generate", {
      method: "POST",
      body: JSON.stringify({ topic, tone_id: toneId, word_count: wordCount }),
    }),

  // 素材庫
  getStyles: () => request<AssetStyle[]>("/assets/styles"),
  getTones: () => request<AssetTone[]>("/assets/tones"),
  getVoices: () => request<AssetVoice[]>("/assets/voices"),

  // 流水線批次
  runPipeline: (jobId: string, action: string, force = false) =>
    request<any>("/pipeline/run", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, action, force, only_missing: !force }),
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
};
