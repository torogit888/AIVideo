import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, Info, Copy, Check } from "lucide-react";
import { SidebarRail } from "./components/SidebarRail";
import { Topbar } from "./components/Topbar";
import { StoryboardGrid } from "./components/StoryboardGrid";
import { SceneInspector } from "./components/SceneInspector";
import { ScriptEditor } from "./components/ScriptEditor";
import { FilmViewer } from "./components/FilmViewer";
import { AssetsView } from "./components/AssetsView";
import { OverviewPanel } from "./components/OverviewPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { StudioConfirmModal } from "./components/StudioConfirmModal";
import { useStudioStore } from "./store";
import { api } from "./api";

export const App: React.FC = () => {
  const {
    currentTab,
    selectedJobId,
    draftResetKey,
    setPipelineRunning,
    loadScenes,
    loadJobs,
    patchSceneCard,
    toasts,
    showToast,
    removeToast,
  } = useStudioStore();

  const [copiedToastId, setCopiedToastId] = useState<string | null>(null);

  // 全域初始化：網頁開啟或重新整理時，第一時間向後端載入所有專案
  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // 監聽 SSE 串流：自動更新進度與分鏡
  useEffect(() => {
    if (!selectedJobId) return;

    let lastSceneId = "";
    let isAlreadyDone = false;
    let lastShownErrorKey = "";

    const cleanup = api.subscribePipeline(selectedJobId, (data) => {
      if (data.is_running) {
        isAlreadyDone = false;
        lastShownErrorKey = "";
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
        // 任務已結束且非正常完成（中斷、失敗或手動停止）：去重確保同一次錯誤只跳一次通知
        const errText = data.error || (data.message && data.message.includes("失敗") ? data.message : "");
        if (errText) {
          const errKey = `${data.notice_seq || 0}:${errText}`;
          if (errKey !== lastShownErrorKey) {
            lastShownErrorKey = errKey;
            showToast(errText, "error");
          }
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
            <ScriptEditor key={selectedJobId || `draft-${draftResetKey}`} />
          </div>
          {/* 成片頁改用 invisible 保留版面，避免 display:none 讓瀏覽器卸載 video 並從 0 秒重播 */}
          <div
            className={
              currentTab === "film"
                ? "relative z-10 flex-1 flex h-full min-w-0 overflow-hidden"
                : "absolute inset-0 z-0 invisible pointer-events-none flex h-full overflow-hidden"
            }
            aria-hidden={currentTab !== "film"}
          >
            <FilmViewer />
          </div>
          <div className={currentTab === "assets" ? "flex-1 flex h-full overflow-hidden" : "hidden"}>
            <AssetsView />
          </div>
          {currentTab === "overview" && <OverviewPanel />}
          {currentTab === "settings" && <SettingsPanel />}

          {/* 右側滑出抽屜 (支援分鏡頁與成片頁開啟，切換分頁時由 setTab 自動收起) */}
          {(currentTab === "storyboard" || currentTab === "film") && <SceneInspector />}
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

      {/* 全域 Studio 深色自訂確認／輸入對話框 */}
      <StudioConfirmModal />
    </div>
  );
};

export default App;
