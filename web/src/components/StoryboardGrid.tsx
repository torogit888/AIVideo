import React from "react";
import { Image as ImageIcon, Volume2, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { useStudioStore } from "../store";
import { SceneSummary } from "../types";
import { api } from "../api";

export const StoryboardGrid: React.FC = () => {
  const { scenes, activeSceneId, openInspector, selectedJobId, setPipelineRunning } = useStudioStore();

  const handleBatchImages = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在批次出圖...");
    await api.runPipeline(selectedJobId, "images");
  };

  const handleBatchTTS = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在批次配音...");
    await api.runPipeline(selectedJobId, "tts");
  };

  const handleCompose = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在合成 1080p 影片...");
    await api.runPipeline(selectedJobId, "compose");
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-cinema-bg">
      {/* 矮版全幽靈指揮列 */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-cinema-border/40 text-xs">
        <div className="flex items-center space-x-2">
          <button
            onClick={handleBatchImages}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60"
          >
            <ImageIcon className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>出圖</span>
          </button>
          <button
            onClick={handleBatchTTS}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60"
          >
            <Volume2 className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>配音</span>
          </button>
          <button
            onClick={handleCompose}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60"
          >
            <Sparkles className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>合成</span>
          </button>
        </div>
        <div className="text-cinema-muted text-[11px]">
          點擊卡片選取開啟右側精修抽屜
        </div>
      </div>

      {/* 16:9 卡片網格主畫布 */}
      <div className="flex-1 overflow-y-auto p-6">
        {scenes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-cinema-muted text-sm">
            <ImageIcon className="w-12 h-12 mb-3 stroke-1 text-cinema-muted/40" />
            <p>目前尚無分鏡資料，請先至「腳本」頁面建立專案。</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {scenes.map((scene: SceneSummary) => {
              const isSelected = activeSceneId === scene.id;
              const hasImg = scene.status.has_image;
              const hasAud = scene.status.has_audio;
              const isFullyDone = hasImg && hasAud;

              return (
                <div
                  key={scene.id}
                  onClick={() => openInspector(scene.id)}
                  className={`group relative flex flex-col rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all duration-150 ${
                    isSelected
                      ? "border-amber-cta ring-2 ring-amber-cta/30 shadow-lg"
                      : "border-cinema-border hover:border-cinema-muted/60"
                  }`}
                >
                  {/* 16:9 圖片縮圖區 */}
                  <div className="relative aspect-video w-full bg-black/40 overflow-hidden">
                    {hasImg && scene.status.image_url ? (
                      <img
                        src={scene.status.image_url}
                        alt={scene.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted/40">
                        <ImageIcon className="w-8 h-8 stroke-1 mb-1" />
                        <span className="text-[10px]">待出圖</span>
                      </div>
                    )}

                    {/* 右下角秒數標籤 */}
                    <div className="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/80 font-mono text-[10px] text-zinc-300">
                      00:{String(Math.round(scene.status.duration)).padStart(2, "0")}
                    </div>

                    {/* 右上角狀態徽章 */}
                    <div className="absolute top-1.5 right-1.5">
                      {isFullyDone ? (
                        <span className="flex items-center px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 text-[10px]">
                          <CheckCircle2 className="w-3 h-3 mr-0.5" />
                          <span>已完成</span>
                        </span>
                      ) : !hasImg ? (
                        <span className="flex items-center px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-800 text-amber-400 text-[10px]">
                          <AlertCircle className="w-3 h-3 mr-0.5" />
                          <span>缺圖</span>
                        </span>
                      ) : (
                        <span className="flex items-center px-1.5 py-0.5 rounded bg-sky-950/80 border border-sky-800 text-sky-400 text-[10px]">
                          <AlertCircle className="w-3 h-3 mr-0.5" />
                          <span>缺聲</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 卡片底部短標題與幕次 */}
                  <div className="p-3">
                    <div className="flex items-baseline space-x-2">
                      <span className="font-mono text-xs text-amber-cta font-medium">
                        {String(scene.index).padStart(2, "0")}
                      </span>
                      <h4 className="text-xs font-medium text-cinema-text truncate" title={scene.title}>
                        {scene.title}
                      </h4>
                    </div>
                    <p className="mt-1 text-[11px] text-cinema-muted line-clamp-2 leading-relaxed">
                      {scene.narration}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
