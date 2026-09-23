import React, { useEffect } from "react";
import { Film, Trash2, ArrowRight } from "lucide-react";
import { SidebarRail } from "./components/SidebarRail";
import { Topbar } from "./components/Topbar";
import { StoryboardGrid } from "./components/StoryboardGrid";
import { SceneInspector } from "./components/SceneInspector";
import { ScriptEditor } from "./components/ScriptEditor";
import { FilmViewer } from "./components/FilmViewer";
import { AssetsView } from "./components/AssetsView";
import { useStudioStore } from "./store";
import { api } from "./api";

export const App: React.FC = () => {
  const {
    currentTab,
    selectedJobId,
    setPipelineRunning,
    loadScenes,
    loadJobs,
    jobs,
    selectJob,
    setTab,
  } = useStudioStore();

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
      alert("專案已成功刪除！");
    } catch (e: any) {
      alert("刪除專案失敗: " + (e.message || "未知錯誤"));
    }
  };

  // 監聽 SSE 串流：自動更新進度與分鏡
  useEffect(() => {
    if (!selectedJobId) return;

    const cleanup = api.subscribePipeline(selectedJobId, (data) => {
      if (data.is_running) {
        setPipelineRunning(true, data.progress, data.message);
      } else if (data.is_done) {
        setPipelineRunning(false, 100, "任務已完成");
        loadScenes(selectedJobId);
        loadJobs();
      }
    });

    return () => cleanup();
  }, [selectedJobId, setPipelineRunning, loadScenes, loadJobs]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-cinema-bg text-cinema-text">
      {/* 1. 左側窄欄導航 (220px / 64px) */}
      <SidebarRail />

      {/* 2. 右側主工作區 */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* 頂列 (48px) */}
        <Topbar />

        {/* 主畫布與右側 Inspector */}
        <div className="flex-1 flex h-[calc(100vh-48px)] overflow-hidden relative">
          {/* 依 Tab 切換主視圖 */}
          {currentTab === "storyboard" && <StoryboardGrid />}
          {currentTab === "script" && <ScriptEditor />}
          {currentTab === "film" && <FilmViewer />}
          {currentTab === "assets" && <AssetsView />}
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
                  onClick={() => setTab("script")}
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
                    onClick={() => setTab("script")}
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
                        onClick={() => selectJob(j.id)}
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
                            {isSelected && (
                              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-cta/20 text-amber-cta font-medium shrink-0">
                                當前作用中
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] font-mono text-cinema-muted truncate">
                            ID: {j.id}
                          </div>
                        </div>

                        {/* 進度指標 */}
                        <div className="grid grid-cols-3 gap-2 py-2 border-y border-cinema-border/50 text-[11px]">
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
            <div className="flex-1 p-8 space-y-4 max-w-3xl mx-auto">
              <h2 className="text-xl font-bold text-cinema-text">Studio 設定</h2>
              <div className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-3 text-xs">
                <div>外觀：近黑電影風 (Dark Cinema UI)</div>
                <div>後端 API 代理：http://localhost:8000</div>
                <div>靜態媒體掛載：/media (支援 Range 影片拖曳串流)</div>
              </div>
            </div>
          )}

          {/* 右側滑出抽屜 (當前選中鏡頭時開啟) */}
          <SceneInspector />
        </div>
      </div>
    </div>
  );
};

export default App;
