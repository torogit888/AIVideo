import { create } from "zustand";
import { api } from "./api";
import { JobSummary, NavTab, SceneSummary } from "./types";

export interface ToastItem {
  id: string;
  message: string;
  type?: "info" | "success" | "error";
}

interface StudioState {
  // 導航
  currentTab: NavTab;
  setTab: (tab: NavTab) => void;
  isSidebarExpanded: boolean;
  toggleSidebar: () => void;

  // 專案
  jobs: JobSummary[];
  selectedJobId: string | null;
  isDraftMode: boolean;
  loadJobs: () => Promise<void>;
  selectJob: (jobId: string) => void;
  startNewDraft: () => void;

  // 分鏡與右側抽屜
  scenes: SceneSummary[];
  activeSceneId: string | null;
  isInspectorOpen: boolean;
  loadScenes: (jobId: string) => Promise<void>;
  openInspector: (sceneId: string) => void;
  closeInspector: () => void;

  // 流水線即時狀態
  isPipelineRunning: boolean;
  isPipelinePaused: boolean;
  pipelineProgress: number;
  pipelineMessage: string;
  pipelineCooldown: number;
  pipelineCooldownTotal: number;
  setPipelineRunning: (
    running: boolean,
    progress?: number,
    msg?: string,
    cooldown?: number,
    cooldownTotal?: number,
    paused?: boolean
  ) => void;
  patchSceneCard: (
    sceneId: string,
    patch: Partial<SceneSummary["status"]> & {
      has_image?: boolean;
      has_audio?: boolean;
      has_pip?: boolean;
      pip_enabled?: boolean;
      pip_mode?: "pip" | "spotlight";
    }
  ) => void;

  // 全域輕量級 Toast 通知
  toasts: ToastItem[];
  showToast: (message: string, type?: "info" | "success" | "error") => void;
  removeToast: (id: string) => void;

  // 全域 AI 模型設定
  selectedAiModel: string;
  setSelectedAiModel: (model: string) => void;
  selectedImageModel: string;
  setSelectedImageModel: (model: string) => void;

  geminiOnline: boolean | null;
  comfyOnline: boolean | null;
  apiOnline: boolean | null;
  refreshConnectionLights: () => Promise<void>;
}

export const useStudioStore = create<StudioState>((set, get) => ({
  // 導航（支援本地儲存記憶，重新整理不迷路）
  currentTab:
    typeof window !== "undefined"
      ? (localStorage.getItem("aivideo_current_tab") as NavTab) || "storyboard"
      : "storyboard",
  setTab: (tab) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_current_tab", tab);
    }
    set({ currentTab: tab });
  },
  isSidebarExpanded: true,
  toggleSidebar: () => set((state) => ({ isSidebarExpanded: !state.isSidebarExpanded })),

  // 專案
  jobs: [],
  selectedJobId:
    typeof window !== "undefined" ? localStorage.getItem("aivideo_selected_job") || null : null,
  isDraftMode: false,
  loadJobs: async () => {
    try {
      const jobs = await api.getJobs();
      set({ jobs });
      if (get().isDraftMode) {
        return;
      }
      const savedJobId = typeof window !== "undefined" ? localStorage.getItem("aivideo_selected_job") : null;
      const currentSelected = get().selectedJobId || savedJobId;
      if (jobs.length > 0) {
        if (currentSelected && jobs.some((j) => j.id === currentSelected)) {
          if (get().selectedJobId !== currentSelected) {
            get().selectJob(currentSelected);
          }
        } else {
          get().selectJob(jobs[0].id);
        }
      } else {
        set({ selectedJobId: null, scenes: [] });
      }
    } catch (e) {
      console.error("載入專案失敗", e);
    }
  },
  selectJob: (jobId) => {
    if (typeof window !== "undefined" && jobId) {
      localStorage.setItem("aivideo_selected_job", jobId);
    }
    const targetJob = get().jobs.find((j) => j.id === jobId);
    if (targetJob?.image_model) {
      if (typeof window !== "undefined") {
        localStorage.setItem("aivideo_selected_image_model", targetJob.image_model);
      }
      set({ selectedImageModel: targetJob.image_model });
    }
    set({ selectedJobId: jobId, isDraftMode: false, activeSceneId: null, isInspectorOpen: false });
    get().loadScenes(jobId);
  },
  startNewDraft: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("aivideo_selected_job");
    }
    set({
      selectedJobId: null,
      isDraftMode: true,
      scenes: [],
      activeSceneId: null,
      isInspectorOpen: false,
    });
    get().setTab("script");
  },

  // 分鏡
  scenes: [],
  activeSceneId: null,
  isInspectorOpen: false,
  loadScenes: async (jobId) => {
    if (!jobId || !jobId.trim()) {
      set({ scenes: [] });
      return;
    }
    try {
      const scenes = await api.getScenes(jobId);
      set({ scenes });
    } catch (e) {
      console.error("載入分鏡失敗", e);
    }
  },
  openInspector: (sceneId) => set({ activeSceneId: sceneId, isInspectorOpen: true }),
  closeInspector: () => set({ isInspectorOpen: false }),

  // 流水線
  isPipelineRunning: false,
  isPipelinePaused: false,
  pipelineProgress: 0,
  pipelineMessage: "",
  pipelineCooldown: 0,
  pipelineCooldownTotal: 0,
  setPipelineRunning: (running, progress = 0, msg = "", cooldown = 0, cooldownTotal = 0, paused = false) =>
    set({
      isPipelineRunning: running,
      isPipelinePaused: Boolean(paused),
      pipelineProgress: progress,
      pipelineMessage: msg,
      pipelineCooldown: cooldown,
      pipelineCooldownTotal: cooldownTotal,
    }),
  patchSceneCard: (sceneId, patch) =>
    set((state) => {
      const jobId = state.selectedJobId;
      const encodedJob = jobId ? encodeURIComponent(jobId) : "";
      return {
        scenes: state.scenes.map((s) => {
          if (s.id !== sceneId) return s;
          const hasImage = patch.has_image ?? s.status.has_image;
          const hasAudio = patch.has_audio ?? s.status.has_audio;
          const hasPip = patch.has_pip ?? s.status.has_pip;
          const pipEnabled = patch.pip_enabled ?? s.pip_enabled;
          const pipMode = patch.pip_mode ?? s.pip_mode;

          // 若有新圖或已出圖但原本無 url，自動組裝帶時間戳的 URL 擊破瀏覽器快取
          let imgUrl = patch.image_url ?? s.status.image_url;
          if (hasImage && (!imgUrl || patch.has_image)) {
            imgUrl = `/media/jobs/${encodedJob}/scenes/${sceneId}/image.png?t=${Date.now()}`;
          }

          let audUrl = patch.audio_url ?? s.status.audio_url;
          if (hasAudio && (!audUrl || patch.has_audio)) {
            audUrl = `/media/jobs/${encodedJob}/scenes/${sceneId}/speech.wav?t=${Date.now()}`;
          }

          let pipUrl = patch.pip_url ?? s.status.pip_url;
          if (hasPip && (!pipUrl || patch.has_pip)) {
            pipUrl = `/media/jobs/${encodedJob}/scenes/${sceneId}/pip.png?t=${Date.now()}`;
          }

          return {
            ...s,
            pip_enabled: pipEnabled,
            pip_mode: pipMode,
            status: {
              ...s.status,
              has_image: hasImage,
              has_audio: hasAudio,
              has_pip: hasPip,
              image_url: imgUrl,
              audio_url: audUrl,
              pip_url: pipUrl,
              duration: patch.duration ?? s.status.duration,
            },
          };
        }),
      };
    }),

  // 全域輕量級 Toast 通知
  toasts: [],
  showToast: (message, type = "success") => {
    const id = Math.random().toString(36).substring(2, 9);
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    // 錯誤訊息停留 8 秒（讓使用者有充足時間閱讀與複製），一般成功提示停留 3.5 秒
    const duration = type === "error" ? 8000 : 3500;
    setTimeout(() => {
      get().removeToast(id);
    }, duration);
  },
  removeToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },

  // 全域 AI 模型設定 (持久化存入 localStorage)
  selectedAiModel:
    typeof window !== "undefined"
      ? localStorage.getItem("aivideo_selected_model") || "gemini-3.8-flash"
      : "gemini-3.8-flash",
  setSelectedAiModel: (model) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_selected_model", model);
    }
    set({ selectedAiModel: model });
  },

  // 全域 生圖 AI 模型設定 (持久化存入 localStorage)
  selectedImageModel:
    typeof window !== "undefined"
      ? localStorage.getItem("aivideo_selected_image_model") || "gemini-3.1-flash-image"
      : "gemini-3.1-flash-image",
  setSelectedImageModel: (model) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_selected_image_model", model);
    }
    set({ selectedImageModel: model });
  },

  geminiOnline: null,
  comfyOnline: null,
  apiOnline: null,
  refreshConnectionLights: async () => {
    try {
      const st = await api.getSystemStatus();
      set({
        apiOnline: true,
        geminiOnline: Boolean(st.gemini_configured),
        comfyOnline: Boolean(st.comfyui_online),
      });
    } catch {
      set({ apiOnline: false, geminiOnline: false, comfyOnline: false });
    }
  },
}));
