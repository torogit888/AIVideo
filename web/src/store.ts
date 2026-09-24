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
  loadJobs: () => Promise<void>;
  selectJob: (jobId: string) => void;

  // 分鏡與右側抽屜
  scenes: SceneSummary[];
  activeSceneId: string | null;
  isInspectorOpen: boolean;
  loadScenes: (jobId: string) => Promise<void>;
  openInspector: (sceneId: string) => void;
  closeInspector: () => void;

  // 流水線即時狀態
  isPipelineRunning: boolean;
  pipelineProgress: number;
  pipelineMessage: string;
  setPipelineRunning: (running: boolean, progress?: number, msg?: string) => void;

  // 全域輕量級 Toast 通知
  toasts: ToastItem[];
  showToast: (message: string, type?: "info" | "success" | "error") => void;
  removeToast: (id: string) => void;

  // 全域 AI 模型設定
  selectedAiModel: string;
  setSelectedAiModel: (model: string) => void;
}

export const useStudioStore = create<StudioState>((set, get) => ({
  // 導航
  currentTab: "storyboard",
  setTab: (tab) => set({ currentTab: tab }),
  isSidebarExpanded: true,
  toggleSidebar: () => set((state) => ({ isSidebarExpanded: !state.isSidebarExpanded })),

  // 專案
  jobs: [],
  selectedJobId: null,
  loadJobs: async () => {
    try {
      const jobs = await api.getJobs();
      set({ jobs });
      if (jobs.length > 0 && !get().selectedJobId) {
        get().selectJob(jobs[0].id);
      }
    } catch (e) {
      console.error("載入專案失敗", e);
    }
  },
  selectJob: (jobId) => {
    set({ selectedJobId: jobId, activeSceneId: null, isInspectorOpen: false });
    get().loadScenes(jobId);
  },

  // 分鏡
  scenes: [],
  activeSceneId: null,
  isInspectorOpen: false,
  loadScenes: async (jobId) => {
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
  pipelineProgress: 0,
  pipelineMessage: "",
  setPipelineRunning: (running, progress = 0, msg = "") =>
    set({ isPipelineRunning: running, pipelineProgress: progress, pipelineMessage: msg }),

  // 全域輕量級 Toast 通知
  toasts: [],
  showToast: (message, type = "success") => {
    const id = Math.random().toString(36).substring(2, 9);
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      get().removeToast(id);
    }, 3200);
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
}));
