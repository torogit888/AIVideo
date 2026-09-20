import { create } from "zustand";
import { api } from "./api";
import { JobSummary, NavTab, SceneSummary } from "./types";

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
}));
