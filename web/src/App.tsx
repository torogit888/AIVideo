import React, { useEffect, useState } from "react";
import { Film, Trash2, ArrowRight, CheckCircle2, AlertCircle, Info, Copy, Check } from "lucide-react";
import { SidebarRail } from "./components/SidebarRail";
import { Topbar } from "./components/Topbar";
import { StoryboardGrid } from "./components/StoryboardGrid";
import { SceneInspector } from "./components/SceneInspector";
import { ScriptEditor } from "./components/ScriptEditor";
import { FilmViewer } from "./components/FilmViewer";
import { AssetsView } from "./components/AssetsView";
import { useStudioStore } from "./store";
import { api } from "./api";
import { AI_IMAGE_MODELS, AI_TEXT_MODELS } from "./types";
import { ConnectionLights } from "./components/ConnectionLights";

const SettingsHealthPanel: React.FC = () => {
  const { refreshConnectionLights, showToast } = useStudioStore();
  const [checking, setChecking] = useState(false);
  const [defaults, setDefaults] = useState<{
    default_voice_id?: string;
    tones?: string[];
    font_path?: string | null;
    font_ok?: boolean;
  }>({});

  useEffect(() => {
    api
      .getSystemStatus()
      .then((st: any) =>
        setDefaults({
          default_voice_id: st.default_voice_id,
          tones: st.tones,
          font_path: st.font_path,
          font_ok: st.font_ok,
        })
      )
      .catch(() => undefined);
  }, []);

  const runCheck = async (target: string) => {
    setChecking(true);
    try {
      await api.checkConnections(target);
      await refreshConnectionLights();
      showToast(target === "gemini" ? "已檢測 Gemini 憑證" : target === "comfy" ? "已檢測 Comfy" : "已檢測連線", "success");
    } catch (e: any) {
      showToast("檢測失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-cinema-text">連線與預設資產</h3>
        <ConnectionLights />
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("gemini")}
          className="h-8 px-3 rounded-lg border border-cinema-border bg-cinema-darker text-cinema-text hover:border-amber-cta/60 hover:text-amber-cta"
        >
          檢測 Gemini
        </button>
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("comfy")}
          className="h-8 px-3 rounded-lg border border-cinema-border bg-cinema-darker text-cinema-text hover:border-amber-cta/60 hover:text-amber-cta"
        >
          檢測 Comfy
        </button>
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("all")}
          className="h-8 px-3 rounded-lg bg-amber-cta text-cinema-bg font-semibold hover:bg-amber-ctaHover"
        >
          全部檢測
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px]">
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">預設發音人</div>
          <div className="font-mono text-cinema-text">{defaults.default_voice_id || "tw_female01"}</div>
        </div>
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">口吻庫</div>
          <div className="text-cinema-text">{(defaults.tones || []).join("、") || "—"}</div>
        </div>
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">字幕字型</div>
          <div className={`font-mono truncate ${defaults.font_ok ? "text-emerald-400" : "text-amber-400"}`} title={defaults.font_path || ""}>
            {defaults.font_ok ? defaults.font_path : "未找到檔案，ASS 用 Noto Sans CJK TC"}
          </div>
        </div>
      </div>
      <details className="pt-1">
        <summary className="cursor-pointer text-cinema-muted hover:text-cinema-text">開發端點</summary>
        <div className="space-y-1.5 text-cinema-muted mt-2">
          <div className="flex justify-between py-1 border-b border-cinema-border/40">
            <span>後端 API</span>
            <span className="text-cinema-text font-mono">http://localhost:8000</span>
          </div>
          <div className="flex justify-between py-1 border-b border-cinema-border/40">
            <span>靜態媒體</span>
            <span className="text-cinema-text font-mono">/media/jobs</span>
          </div>
          <div className="flex justify-between py-1">
            <span>ComfyUI</span>
            <span className="text-cinema-text font-mono">http://127.0.0.1:8188</span>
          </div>
        </div>
      </details>
    </div>
  );
};

export const App: React.FC = () => {
  const {
    currentTab,
    selectedJobId,
    setPipelineRunning,
    loadScenes,
    loadJobs,
    patchSceneCard,
    jobs,
    selectJob,
    setTab,
    toasts,
    showToast,
    removeToast,
    selectedAiModel,
    setSelectedAiModel,
    selectedImageModel,
    setSelectedImageModel,
    startNewDraft,
  } = useStudioStore();

  const [copiedToastId, setCopiedToastId] = useState<string | null>(null);

  const handleDeleteJobFromList = async (jobId: string, jobTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmDelete = window.confirm(
      `確定要徹底刪除專案【${jobTitle || jobId}】嗎？\n\n此操作將永久刪除此專案的所有分鏡、生圖、配音與成片，無法復原！`
    );
    if (!confirmDelete) return;

    try {
      await api.deleteJob(jobId);
      const remainingJobs = await api.getJobs();
      useStudioStore.setState({ jobs: remainingJobs });
      if (selectedJobId === jobId) {
        if (remainingJobs.length > 0) {
          selectJob(remainingJobs[0].id);
        } else {
          useStudioStore.setState({ selectedJobId: null, scenes: [], activeSceneId: null });
        }
      }
      showToast("專案已成功刪除！", "success");
    } catch (e: any) {
      showToast("刪除專案失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  // 全域初始化：網頁開啟或重新整理時，第一時間向後端載入所有專案
  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // 監聽 SSE 串流：自動更新進度與分鏡
  useEffect(() => {
    if (!selectedJobId) return;

    let lastSceneId = "";
    let isAlreadyDone = false;

    const cleanup = api.subscribePipeline(selectedJobId, (data) => {
      if (data.is_running) {
        isAlreadyDone = false;
        setPipelineRunning(
          true,
          data.progress,
          data.message,
          data.cooldown_remaining || 0,
          data.cooldown_total || 0,
          Boolean(data.is_paused)
        );
        if (data.scene_id) {
          patchSceneCard(data.scene_id, {
            has_image: data.has_image,
            has_audio: data.has_audio,
          });
          if (data.scene_id !== lastSceneId) {
            if (lastSceneId) {
              // 上一幕已全線完成，即時刷新全畫布分鏡狀態
              loadScenes(selectedJobId);
            }
            lastSceneId = data.scene_id;
          }
        }
      } else if (data.is_done) {
        if (!isAlreadyDone) {
          isAlreadyDone = true;
          setPipelineRunning(false, 100, "任務已完成", 0, 0);
          loadScenes(selectedJobId);
          loadJobs();
        }
      } else {
        // 任務已結束且非正常完成（中斷、失敗或手動停止）
        if (data.error || (data.message && data.message.includes("失敗"))) {
          showToast(data.error || data.message, "error");
        }
        setPipelineRunning(
          false,
          0,
          data.message || data.error || "任務已結束",
          0,
          0
        );
      }
    });

    return () => cleanup();
  }, [selectedJobId, setPipelineRunning, loadScenes, loadJobs, patchSceneCard, showToast]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-cinema-bg text-cinema-text">
      {/* 1. 左側窄欄導航 (220px / 64px) */}
      <SidebarRail />

      {/* 2. 右側主工作區 */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* 頂列 (智能感知按需渲染：分鏡常駐 / 其他頁面背景生成時輕量浮現) */}
        <Topbar />

        {/* 主畫布與右側 Inspector (自適應 100% 滿版高度) */}
        <div className="flex-1 flex min-h-0 overflow-hidden relative">
          {/* 依 Tab 切換主視圖（常駐掛載，保留各分頁已調整之狀態與滾動位置） */}
          <div className={currentTab === "storyboard" ? "flex-1 flex h-full overflow-hidden" : "hidden"}>
            <StoryboardGrid />
          </div>
          <div className={currentTab === "script" ? "flex-1 flex h-full overflow-hidden" : "hidden"}>
            <ScriptEditor />
          </div>
          <div className={currentTab === "film" ? "flex-1 flex h-full overflow-hidden" : "hidden"}>
            <FilmViewer />
          </div>
          <div className={currentTab === "assets" ? "flex-1 flex h-full overflow-hidden" : "hidden"}>
            <AssetsView />
          </div>
          {currentTab === "overview" && (
            <div className="flex-1 p-8 space-y-6 max-w-5xl mx-auto overflow-y-auto">
              <div className="flex justify-between items-end border-b border-cinema-border pb-4">
                <div>
                  <h2 className="text-xl font-bold text-cinema-text">專案總覽與管理</h2>
                  <p className="text-xs text-cinema-muted mt-1">
                    快速檢視所有影片專案製作進度、切換工作階段或清理已完成專案。
                  </p>
                </div>
                <button
                  onClick={() => startNewDraft()}
                  className="px-3.5 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs transition-colors shadow"
                >
                  + 新建專案
                </button>
              </div>

              {jobs.length === 0 ? (
                <div className="p-12 text-center rounded-lg bg-cinema-card border border-cinema-border space-y-3">
                  <Film className="w-8 h-8 text-cinema-muted/50 mx-auto" />
                  <p className="text-xs text-cinema-muted">目前尚無任何專案</p>
                  <button
                    onClick={() => startNewDraft()}
                    className="text-xs text-amber-cta hover:underline font-medium"
                  >
                    立即點此建立第一個說書故事
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {jobs.map((j) => {
                    const isSelected = selectedJobId === j.id;
                    const total = j.progress.scenes_count;
                    const imgReady = j.progress.images_ready;
                    const audReady = j.progress.audio_ready;
                    const filmReady = j.progress.film_ready;

                    return (
                      <div
                        key={j.id}
                        onClick={() => {
                          selectJob(j.id);
                          setTab("storyboard");
                        }}
                        className={`p-4 rounded-lg bg-cinema-card border cursor-pointer transition-all space-y-3 flex flex-col justify-between ${
                          isSelected
                            ? "border-amber-cta ring-2 ring-amber-cta/30"
                            : "border-cinema-border hover:border-cinema-muted"
                        }`}
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="text-sm font-semibold text-cinema-text truncate" title={j.title}>
                              {j.title}
                            </h3>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {j.progress.youtube_published && (
                                <a
                                  href={j.progress.youtube_video_url || `https://youtu.be/${j.progress.youtube_video_id}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="text-[10px] px-2 py-0.5 rounded bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 font-medium flex items-center gap-1 transition-colors"
                                  title={`已於 ${j.progress.youtube_uploaded_at || "YouTube"} 發布，點擊前往觀看`}
                                >
                                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                                  <span>YouTube 已上架</span>
                                </a>
                              )}
                              {isSelected && (
                                <span className="text-[10px] px-2 py-0.5 rounded bg-amber-cta/20 text-amber-cta font-medium">
                                  當前作用中
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="text-[11px] font-mono text-cinema-muted truncate">
                            ID: {j.id}
                          </div>
                        </div>

                        {/* 進度指標 (4 欄位：畫面、配音、成片、YouTube) */}
                        <div className="grid grid-cols-4 gap-2 py-2 border-y border-cinema-border/50 text-[11px]">
                          <div>
                            <span className="text-cinema-muted block text-[10px]">畫面產出</span>
                            <span className={`font-semibold ${imgReady === total && total > 0 ? "text-emerald-400" : "text-cinema-text"}`}>
                              {imgReady} / {total}
                            </span>
                          </div>
                          <div>
                            <span className="text-cinema-muted block text-[10px]">語音配音</span>
                            <span className={`font-semibold ${audReady === total && total > 0 ? "text-emerald-400" : "text-cinema-text"}`}>
                              {audReady} / {total}
                            </span>
                          </div>
                          <div>
                            <span className="text-cinema-muted block text-[10px]">成片狀態</span>
                            <span className={`font-semibold ${filmReady ? "text-emerald-400" : "text-amber-500"}`}>
                              {filmReady ? "已合成" : "待合成"}
                            </span>
                          </div>
                          <div>
                            <span className="text-cinema-muted block text-[10px]">YouTube</span>
                            <span className={`font-semibold ${j.progress.youtube_published ? "text-red-400" : "text-cinema-muted"}`}>
                              {j.progress.youtube_published ? "已發布" : "未發布"}
                            </span>
                          </div>
                        </div>

                        {/* 操作列 */}
                        <div className="flex items-center justify-between pt-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              selectJob(j.id);
                              setTab("storyboard");
                            }}
                            className="flex items-center text-xs text-amber-cta hover:text-amber-ctaHover font-medium"
                          >
                            <span>進入故事板</span>
                            <ArrowRight className="w-3.5 h-3.5 ml-1" />
                          </button>
                          <button
                            onClick={(e) => handleDeleteJobFromList(j.id, j.title, e)}
                            title="刪除此專案"
                            className="p-1.5 rounded hover:bg-red-950/60 text-cinema-muted hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
          {currentTab === "settings" && (
            <div className="flex-1 p-8 space-y-6 max-w-3xl mx-auto overflow-y-auto">
              <div>
                <h2 className="text-xl font-bold text-cinema-text">Studio 設定</h2>
                <p className="text-xs text-cinema-muted mt-1">管理全域 AI 文本生成核心、環境端點與渲染管線配置。</p>
              </div>

              {/* AI 模型設定卡片 */}
              <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4">
                <div className="flex items-center justify-between border-b border-cinema-border/60 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-cinema-text flex items-center">
                      <span className="text-amber-cta mr-2">⚡</span>
                      Google Cloud Vertex AI 核心大模型
                    </h3>
                    <p className="text-xs text-cinema-muted mt-0.5">
                      驅動故事發想長篇寫作、說書人口吻特徵萃取、AI 分鏡切鏡與英文電影提示詞生成。
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                  {AI_TEXT_MODELS.map((m) => {
                    const isSelected = selectedAiModel === m.id;
                    return (
                      <div
                        key={m.id}
                        onClick={() => {
                          setSelectedAiModel(m.id);
                          showToast(`已切換全域核心 AI 模型為 ${m.name}`, "success");
                        }}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? "border-amber-cta bg-amber-cta/10 ring-1 ring-amber-cta/30"
                            : "border-cinema-border bg-cinema-darker/60 hover:border-cinema-muted"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-semibold ${isSelected ? "text-amber-cta" : "text-cinema-text"}`}>
                            {m.name}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                            isSelected ? "bg-amber-cta text-cinema-bg font-bold" : "bg-cinema-card text-cinema-muted"
                          }`}>
                            {m.badge}
                          </span>
                        </div>
                        <div className="text-[11px] text-cinema-muted mt-1">{m.tag}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4">
                <div className="border-b border-cinema-border/60 pb-3">
                  <h3 className="text-sm font-semibold text-cinema-text">生圖模型</h3>
                  <p className="text-xs text-cinema-muted mt-0.5">分鏡出圖使用的 Gemini／Imagen 模型。</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {AI_IMAGE_MODELS.map((m) => {
                    const isSelected = selectedImageModel === m.id;
                    return (
                      <div
                        key={m.id}
                        onClick={async () => {
                          setSelectedImageModel(m.id);
                          if (selectedJobId) {
                            try {
                              await api.updateJob(selectedJobId, { image_model: m.id });
                              await loadJobs();
                            } catch {
                              /* 預設仍寫入本機 */
                            }
                          }
                          showToast(`已切換生圖模型為 ${m.name}`, "success");
                        }}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? "border-amber-cta bg-amber-cta/10 ring-1 ring-amber-cta/30"
                            : "border-cinema-border bg-cinema-darker/60 hover:border-cinema-muted"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-semibold ${isSelected ? "text-amber-cta" : "text-cinema-text"}`}>
                            {m.name}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                            isSelected ? "bg-amber-cta text-cinema-bg font-bold" : "bg-cinema-card text-cinema-muted"
                          }`}>
                            {m.badge}
                          </span>
                        </div>
                        <div className="text-[11px] text-cinema-muted mt-1">{m.tag}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <SettingsHealthPanel />
            </div>
          )}

          {/* 右側滑出抽屜 (當前選中鏡頭時開啟) */}
          <SceneInspector />
        </div>
      </div>

      {/* 浮動輕量級通知 (Toast 零彈窗提示) */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col space-y-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => removeToast(t.id)}
            className={`pointer-events-auto flex items-center px-4 py-2.5 rounded-lg shadow-2xl border text-xs font-medium tracking-wide transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 cursor-pointer ${
              t.type === "error"
                ? "bg-red-950/95 border-red-700 text-red-200"
                : t.type === "info"
                ? "bg-sky-950/95 border-sky-700 text-sky-200"
                : "bg-cinema-card/95 border-amber-cta/60 text-cinema-text glow-amber"
            }`}
          >
            {t.type === "error" ? (
              <AlertCircle className="w-4 h-4 text-red-400 mr-2 flex-shrink-0" />
            ) : t.type === "info" ? (
              <Info className="w-4 h-4 text-sky-400 mr-2 flex-shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-amber-cta mr-2 flex-shrink-0" />
            )}
            <span className="flex-1 pr-1 break-words">{t.message}</span>
            {t.type === "error" && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(t.message);
                  setCopiedToastId(t.id);
                  setTimeout(() => setCopiedToastId(null), 1500);
                }}
                title="複製錯誤訊息"
                className="ml-2 px-1.5 py-0.5 rounded bg-red-900/80 hover:bg-red-800 text-[10px] text-red-200 border border-red-700/80 flex items-center shrink-0 transition-colors"
              >
                {copiedToastId === t.id ? (
                  <>
                    <Check className="w-3 h-3 mr-1 text-emerald-400" />
                    <span>已複製</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 mr-1" />
                    <span>複製</span>
                  </>
                )}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
