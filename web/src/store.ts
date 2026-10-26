import { create } from "zustand";
import { api } from "./api";
import { DEFAULT_IMAGE_MODEL } from "./studioActions";
import { JobSummary, NavTab, SceneSummary } from "./types";

export interface ToastItem {
  id: string;
  message: string;
  type?: "info" | "success" | "error";
}

export interface ConfirmDialogState {
  isOpen: boolean;
  mode: "confirm" | "prompt";
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
  variant: "danger" | "primary";
  placeholder?: string;
  defaultValue?: string;
  onResolve?: (value: any) => void;
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
  draftResetKey: number;
  loadJobs: () => Promise<void>;
  selectJob: (jobId: string) => Promise<boolean>;
  deleteJob: (jobId: string, jobTitle?: string) => Promise<boolean>;
  startNewDraft: () => Promise<boolean>;
  scriptDirty: boolean;
  setScriptDirty: (dirty: boolean) => void;

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

  // 全域 Studio 自訂確認／輸入對話框（取代瀏覽器原生 window.confirm / window.prompt）
  confirmDialog: ConfirmDialogState | null;
  requestConfirm: (options: {
    title?: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    variant?: "danger" | "primary";
  } | string) => Promise<boolean>;
  requestPrompt: (options: {
    title?: string;
    message: string;
    placeholder?: string;
    defaultValue?: string;
    confirmText?: string;
    cancelText?: string;
  } | string) => Promise<string | null>;
  closeConfirmDialog: (result: any) => void;

  // 全域 AI 模型設定
  selectedAiModel: string;
  setSelectedAiModel: (model: string) => void;
  selectedImageModel: string;
  setSelectedImageModel: (model: string) => void;

  // 跨元件共用狀態（取代瀏覽器 CustomEvent 廣播）
  burnSubtitles: boolean;
  setBurnSubtitles: (burn: boolean) => void;
  isContinuityOpen: boolean;
  setContinuityOpen: (open: boolean) => void;
  anchorsRevision: number;
  bumpAnchorsRevision: () => void;

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
    set({ currentTab: tab, isInspectorOpen: false });
  },
  isSidebarExpanded: true,
  toggleSidebar: () => set((state) => ({ isSidebarExpanded: !state.isSidebarExpanded })),

  // 專案
  jobs: [],
  selectedJobId:
    typeof window !== "undefined" ? localStorage.getItem("aivideo_selected_job") || null : null,
  isDraftMode: false,
  draftResetKey: 0,
  scriptDirty: false,
  setScriptDirty: (dirty) => set({ scriptDirty: dirty }),
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
          const matched = jobs.find((j) => j.id === currentSelected);
          if (matched && typeof matched.burn_subtitles === "boolean") {
            set({ burnSubtitles: matched.burn_subtitles });
          }
          if (get().selectedJobId !== currentSelected) {
            await get().selectJob(currentSelected);
          } else {
            const jobModel = matched?.image_model || DEFAULT_IMAGE_MODEL;
            if (get().selectedImageModel !== jobModel) {
              set({ selectedImageModel: jobModel });
            }
          }
        } else {
          await get().selectJob(jobs[0].id);
        }
      } else {
        set({ selectedJobId: null, scenes: [] });
      }
    } catch (e) {
      console.error("載入專案失敗", e);
    }
  },
  selectJob: async (jobId) => {
    if (!jobId) return false;
    if (get().scriptDirty && get().selectedJobId !== jobId) {
      const ok = await get().requestConfirm({
        title: "口白尚未儲存",
        message: "這份口白有修改還沒按儲存。換專案後這些修改會消失。",
        confirmText: "放棄修改",
        cancelText: "留在這裡",
        variant: "danger",
      });
      if (!ok) return false;
      set({ scriptDirty: false });
    }
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_selected_job", jobId);
    }
    const targetJob = get().jobs.find((j) => j.id === jobId);
    const jobModel = targetJob?.image_model || DEFAULT_IMAGE_MODEL;
    set({
      selectedJobId: jobId,
      selectedImageModel: jobModel,
      isDraftMode: false,
      scenes: get().selectedJobId === jobId ? get().scenes : [],
      activeSceneId: null,
      isInspectorOpen: false,
      burnSubtitles: Boolean(targetJob?.burn_subtitles),
    });
    return true;
  },
  deleteJob: async (jobId, jobTitle) => {
    if (!jobId) return false;
    const title = jobTitle || get().jobs.find((j) => j.id === jobId)?.title || jobId;
    const confirmDelete = await get().requestConfirm({
      title: "刪除專案確認",
      message: `確定要徹底刪除專案【${title}】嗎？\n\n此操作將永久刪除此專案的所有分鏡、生圖、配音與成片，無法復原！`,
      confirmText: "徹底刪除",
      variant: "danger",
    });
    if (!confirmDelete) return false;

    try {
      await api.deleteJob(jobId);
      const wasSelected = get().selectedJobId === jobId;
      if (wasSelected) {
        set({ scriptDirty: false });
      }
      const remainingJobs = await api.getJobs();
      set({ jobs: remainingJobs });
      if (wasSelected) {
        if (remainingJobs.length > 0) {
          await get().selectJob(remainingJobs[0].id);
        } else {
          if (typeof window !== "undefined") {
            localStorage.removeItem("aivideo_selected_job");
          }
          set({ selectedJobId: null, scenes: [], activeSceneId: null, isInspectorOpen: false });
        }
      }
      get().showToast("專案已成功刪除！", "success");
      return true;
    } catch (e: any) {
      get().showToast("刪除專案失敗: " + (e.message || "未知錯誤"), "error");
      return false;
    }
  },
  startNewDraft: async () => {
    if (get().scriptDirty) {
      const ok = await get().requestConfirm({
        title: "口白尚未儲存",
        message: "這份口白有修改還沒按儲存。開新草稿後這些修改會消失。",
        confirmText: "放棄修改",
        cancelText: "留在這裡",
        variant: "danger",
      });
      if (!ok) return false;
      set({ scriptDirty: false });
    }
    if (typeof window !== "undefined") {
      localStorage.removeItem("aivideo_selected_job");
      localStorage.removeItem("aivideo_draft_custom_prompt");
      localStorage.removeItem("aivideo_draft_outline");
    }
    const draftImage =
      typeof window !== "undefined"
        ? localStorage.getItem("aivideo_selected_image_model") || DEFAULT_IMAGE_MODEL
        : DEFAULT_IMAGE_MODEL;
    set((state) => ({
      selectedJobId: null,
      selectedImageModel: draftImage,
      isDraftMode: true,
      draftResetKey: state.draftResetKey + 1,
      scenes: [],
      activeSceneId: null,
      isInspectorOpen: false,
      scriptDirty: false,
    }));
    get().setTab("script");
    return true;
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
      if (get().selectedJobId !== jobId) return;
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

  // 全域 Studio 自訂確認／輸入對話框
  confirmDialog: null,
  requestConfirm: (options) =>
    new Promise<boolean>((resolve) => {
      const prev = get().confirmDialog;
      if (prev?.isOpen && prev.onResolve) {
        prev.onResolve(prev.mode === "prompt" ? null : false);
      }
      const opts = typeof options === "string" ? { message: options } : options;
      const isDanger = opts.variant === "danger";
      set({
        confirmDialog: {
          isOpen: true,
          mode: "confirm",
          title: opts.title || (isDanger ? "確認執行此操作" : "操作確認"),
          message: opts.message,
          confirmText: opts.confirmText || (isDanger ? "確定執行" : "確定"),
          cancelText: opts.cancelText || "取消",
          variant: isDanger ? "danger" : "primary",
          onResolve: (val: boolean) => resolve(Boolean(val)),
        },
      });
    }),
  requestPrompt: (options) =>
    new Promise<string | null>((resolve) => {
      const prev = get().confirmDialog;
      if (prev?.isOpen && prev.onResolve) {
        prev.onResolve(prev.mode === "prompt" ? null : false);
      }
      const opts = typeof options === "string" ? { message: options } : options;
      set({
        confirmDialog: {
          isOpen: true,
          mode: "prompt",
          title: opts.title || "輸入資訊",
          message: opts.message,
          placeholder: opts.placeholder || "",
          defaultValue: opts.defaultValue || "",
          confirmText: opts.confirmText || "確定",
          cancelText: opts.cancelText || "取消",
          variant: "primary",
          onResolve: (val: string | null) => resolve(val),
        },
      });
    }),
  closeConfirmDialog: (result) => {
    const current = get().confirmDialog;
    if (current?.onResolve) {
      current.onResolve(result);
    }
    set({ confirmDialog: null });
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
    set({ selectedImageModel: model });
    if (!get().selectedJobId && typeof window !== "undefined") {
      localStorage.setItem("aivideo_selected_image_model", model);
    }
  },

  // 跨元件共用狀態
  burnSubtitles: false,
  setBurnSubtitles: (burn) => set({ burnSubtitles: burn }),
  isContinuityOpen: false,
  setContinuityOpen: (open) => set({ isContinuityOpen: open }),
  anchorsRevision: 0,
  bumpAnchorsRevision: () => set((state) => ({ anchorsRevision: state.anchorsRevision + 1 })),

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
