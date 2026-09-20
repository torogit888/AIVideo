import React, { useEffect } from "react";
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
  const { currentTab, selectedJobId, setPipelineRunning, loadScenes, loadJobs } = useStudioStore();

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
            <div className="flex-1 p-8 space-y-4 max-w-4xl mx-auto">
              <h2 className="text-xl font-bold text-cinema-text">專案總覽</h2>
              <p className="text-xs text-cinema-muted">
                快速檢視專案健康度，點選左側「分鏡」進入主工作台。
              </p>
              <div className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-2">
                <div className="text-xs text-amber-cta font-medium">當前作用中專案</div>
                <div className="text-base font-semibold text-cinema-text font-mono">{selectedJobId || "尚未選擇"}</div>
              </div>
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
