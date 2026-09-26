import React, { useEffect, useState } from "react";
import { Image as ImageIcon, Volume2, CheckCircle2, AlertCircle, Mic, Camera, Search, Trash2, Play, Sparkles } from "lucide-react";
import { useStudioStore } from "../store";
import { SceneSummary, AssetVoice } from "../types";
import { api } from "../api";
import { VisualContinuityModal } from "./VisualContinuityModal";

export const StoryboardGrid: React.FC = () => {
  const {
    scenes,
    activeSceneId,
    openInspector,
    selectedJobId,
    setPipelineRunning,
    jobs,
    loadJobs,
    loadScenes,
    showToast,
  } = useStudioStore();

  const [voices, setVoices] = useState<AssetVoice[]>([]);
  const [isContinuityOpen, setIsContinuityOpen] = useState(false);
  const [burnSubtitles, setBurnSubtitles] = useState(false);

  useEffect(() => {
    api.getVoices().then(setVoices).catch(console.error);
  }, []);

  // 當專案存在時，確保分鏡列表自動載入
  useEffect(() => {
    if (selectedJobId) {
      loadScenes(selectedJobId);
    }
  }, [selectedJobId, loadScenes]);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  const handleBatchImages = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在批次出圖...");
    await api.runPipeline(selectedJobId, "images");
  };

  const handleBatchPip = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在跨來源檢索真實考據照片 (PiP)...");
    await api.runPipeline(selectedJobId, "pip");
  };

  const handleBatchTTS = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在批次配音...");
    await api.runPipeline(selectedJobId, "tts");
  };

  const handleCompose = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(
      true,
      10,
      burnSubtitles ? "正在合成 1080p 影片 (燒錄 ASS 字幕)..." : "正在極速合成 1080p 影片 (純淨畫面直通合流)..."
    );
    await api.runPipeline(selectedJobId, "compose", false, burnSubtitles);
  };

  const handleClearAllMedia = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm(
      `⚠️ 確定要全部清除本專案所有分鏡已生成的素材嗎？\n\n` +
        `• 將刪除：所有已生成的畫面 (image.png)、語音 (speech.wav)、考據圖 (pip.png) 與 1080p 成片。\n` +
        `• 將保留：所有分鏡的逐幕口白台詞、提示詞 (Prompt) 與各項設定。\n\n` +
        `重置後，所有分鏡卡片將回到初始「待出圖」狀態，便於全新一鍵生成。`
    );
    if (!ok) return;

    try {
      await api.clearJobMedia(selectedJobId);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast("已成功清空所有分鏡素材，所有分鏡已重置回初始待出圖狀態！", "success");
    } catch (e: any) {
      showToast("清除失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-cinema-bg">
      {/* 矮版全幽靈指揮列 */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-cinema-border/40 text-xs overflow-x-auto gap-4">
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => setIsContinuityOpen(true)}
            className="flex items-center px-3 py-1 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 transition-colors whitespace-nowrap shrink-0 font-medium"
            title="開啟視覺一致性中心：設定主體定裝參考圖 (Hero Shot) 與視覺特徵錨點"
          >
            <Sparkles className="w-3.5 h-3.5 mr-1" />
            <span>視覺一致性 (定裝圖)</span>
          </button>
          <div className="h-4 w-[1px] bg-cinema-border/60 mx-1 shrink-0" />

          <button
            onClick={handleBatchImages}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60 whitespace-nowrap shrink-0"
          >
            <ImageIcon className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>出圖</span>
          </button>
          <button
            onClick={handleBatchPip}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60 whitespace-nowrap shrink-0"
            title="依據各幕台詞自動向 NASA、維基百科檢索真實考據歷史照片"
          >
            <Camera className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>考據配圖 (PiP)</span>
          </button>
          <button
            onClick={handleBatchTTS}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60 whitespace-nowrap shrink-0"
          >
            <Volume2 className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>配音</span>
          </button>
          <button
            onClick={handleCompose}
            className="flex items-center px-3 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text hover:text-amber-cta transition-colors border border-cinema-border/60 whitespace-nowrap shrink-0"
            title={burnSubtitles ? "合成 1080p 成片（將燒錄 ASS 字幕）" : "合成 1080p 成片（免重編碼極速直通，可下載 SRT 字幕上傳 YouTube）"}
          >
            <Play className="w-3.5 h-3.5 mr-1 text-cinema-muted" />
            <span>合成</span>
          </button>
          <label
            className="flex items-center space-x-1.5 cursor-pointer text-cinema-muted hover:text-cinema-text text-[11px] select-none pl-1 shrink-0"
            title="開啟時將 ASS 字幕壓制至影片畫面內；關閉時極速合流純淨畫面（免重編碼），並產出可供 YouTube 使用的 SRT 字幕檔"
          >
            <input
              type="checkbox"
              checked={burnSubtitles}
              onChange={(e) => setBurnSubtitles(e.target.checked)}
              className="rounded border-cinema-border bg-cinema-darker text-amber-cta focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <span>燒錄字幕</span>
          </label>
          <div className="h-4 w-[1px] bg-cinema-border/60 mx-1 shrink-0" />
          <button
            onClick={handleClearAllMedia}
            className="flex items-center px-2.5 py-1 rounded bg-cinema-card hover:bg-red-950/40 text-cinema-muted hover:text-red-400 border border-cinema-border/60 hover:border-red-800/80 transition-colors whitespace-nowrap shrink-0"
            title="清空所有已生成的圖片、配音、考據圖與成片，重置為初始待出圖狀態"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1 text-red-400/80" />
            <span>全部清除</span>
          </button>

          <div className="h-4 w-px bg-cinema-border/60 mx-1 shrink-0" />

          {/* 專案預設發音人切換 */}
          <div className="flex items-center space-x-1.5 text-cinema-muted whitespace-nowrap shrink-0">
            <Mic className="w-3.5 h-3.5 text-amber-cta" />
            <span className="text-[11px] font-medium">發音人:</span>
            <select
              value={currentJob?.voice_id || "female01"}
              onChange={async (e) => {
                if (!selectedJobId) return;
                try {
                  await api.updateJob(selectedJobId, { voice_id: e.target.value });
                  await loadJobs();
                  showToast("專案發音人已更新", "success");
                } catch (err: any) {
                  showToast("更新專案發音人失敗: " + (err.message || "未知錯誤"), "error");
                }
              }}
              className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px] focus:outline-none focus:border-amber-cta cursor-pointer"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.gender})
                </option>
              ))}
            </select>
          </div>
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
                  onClick={() => {
                    const sel = window.getSelection();
                    if (sel && sel.toString().trim().length > 0) return;
                    openInspector(scene.id);
                  }}
                  className={`group relative flex flex-col rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all duration-150 ${
                    isSelected
                      ? "border-amber-cta ring-2 ring-amber-cta/30 shadow-lg"
                      : "border-cinema-border hover:border-cinema-muted/60"
                  }`}
                >
                  {/* 16:9 圖片縮圖區（支援黑底歷史聚焦與右側置中 PiP） */}
                  <div className="relative aspect-video w-full bg-black/40 overflow-hidden">
                    {scene.status.has_pip && scene.status.pip_url && scene.pip_mode === "spotlight" ? (
                      <div className="w-full h-full bg-black flex items-center justify-center overflow-hidden">
                        <img
                          src={scene.status.pip_url}
                          alt="Spotlight Archival"
                          className="max-h-[82%] max-w-[82%] object-contain rounded border border-white/80 shadow-2xl transition-transform group-hover:scale-105"
                          loading="lazy"
                        />
                        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-amber-500/90 text-black font-semibold text-[9px] z-10">
                          🏛️ 黑底歷史聚焦
                        </div>
                      </div>
                    ) : (
                      <>
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

                        {/* 右半部置中真實考據畫中畫 (PiP) 浮動預覽卡（依原照比例自適應，不裁切） */}
                        {scene.status.has_pip && scene.status.pip_url && (
                          <div
                            className="absolute top-1/2 -translate-y-1/2 right-2 max-w-[28%] max-h-[75%] rounded border-[1.5px] border-white/90 bg-black/95 p-0.5 overflow-hidden shadow-xl z-10 transition-transform group-hover:scale-105 flex items-center justify-center"
                            title={`PiP 真實考據圖 (右半部置中): ${scene.pip_query || "pip.png"}`}
                          >
                            <img
                              src={scene.status.pip_url}
                              alt="PiP Preview"
                              className="max-h-[110px] max-w-full object-contain rounded-sm"
                              loading="lazy"
                            />
                          </div>
                        )}
                      </>
                    )}

                    {/* 左上角狀態徽章 */}
                    <div className="absolute top-1.5 left-1.5 z-10">
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

                    {/* 右下角秒數標籤 */}
                    <div className="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/80 font-mono text-[10px] text-zinc-300 z-10">
                      00:{String(Math.round(scene.status.duration)).padStart(2, "0")}
                    </div>

                    {/* 左下角 PiP 考據實體標籤 */}
                    {(scene.status.has_pip || scene.pip_query || scene.pip_error) && (
                      <div className="absolute bottom-1.5 left-1.5 max-w-[62%] z-10">
                        {scene.status.has_pip ? (
                          <span
                            className="flex items-center px-1.5 py-0.5 rounded bg-purple-950/90 border border-purple-600/80 text-purple-200 text-[10px] font-mono shadow-sm truncate"
                            title={`已配真實考據照片: ${scene.pip_query || "pip.png"}`}
                          >
                            <Camera className="w-3 h-3 mr-1 text-purple-400 shrink-0" />
                            <span className="truncate">
                              {scene.pip_mode === "spotlight" ? "聚焦: " : "PiP: "}
                              {scene.pip_query || "已配圖"}
                            </span>
                          </span>
                        ) : scene.pip_error ? (
                          <span
                            className="flex items-center px-1.5 py-0.5 rounded bg-red-950/90 border border-red-700/80 text-red-300 text-[10px] font-mono shadow-sm truncate"
                            title={scene.pip_error}
                          >
                            <AlertCircle className="w-3 h-3 mr-1 text-red-400 shrink-0" />
                            <span className="truncate">考據失敗</span>
                          </span>
                        ) : (
                          <span
                            className="flex items-center px-1.5 py-0.5 rounded bg-black/85 border border-amber-cta/50 text-amber-300 text-[10px] font-mono shadow-sm truncate"
                            title={`AI 建議考據實體: ${scene.pip_query}（可點擊上方「考據配圖」一鍵下載）`}
                          >
                            <Search className="w-2.5 h-2.5 mr-1 text-amber-cta shrink-0" />
                            <span className="truncate">考據: {scene.pip_query}</span>
                          </span>
                        )}
                      </div>
                    )}
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

      {/* 視覺一致性與定裝參考中心彈窗 */}
      <VisualContinuityModal
        isOpen={isContinuityOpen}
        onClose={() => setIsContinuityOpen(false)}
      />
    </div>
  );
};
