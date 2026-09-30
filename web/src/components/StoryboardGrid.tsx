import React, { useEffect, useState } from "react";
import { Image as ImageIcon, ImageOff, Volume2, CheckCircle2, AlertCircle, Mic, Camera, Search, Trash2, Play, Sparkles } from "lucide-react";
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

  const handleClearImagesOnly = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm(
      `⚠️ 確定要清空本專案所有分鏡已生成的圖片嗎？\n\n` +
        `• 將刪除：所有已生成的畫面 (image.png) 與歷史圖片 Takes。\n` +
        `• 將保留：所有分鏡的語音 (speech.wav)、考據圖 (pip.png)、逐幕口白台詞與提示詞 (Prompt)。\n\n` +
        `重置後，所有分鏡將回到初始「待出圖」狀態，您可以更換生圖風格或模型後重新一鍵出圖。`
    );
    if (!ok) return;

    try {
      await api.clearJobImages(selectedJobId);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast("已成功清空所有分鏡圖片！語音配音與台詞已完整保留。", "success");
    } catch (e: any) {
      showToast("清空圖片失敗: " + (e.message || "未知錯誤"), "error");
    }
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
      <div className="flex items-center justify-between px-5 py-2 border-b border-cinema-border/50 text-xs overflow-x-auto gap-4 bg-cinema-bg/95 backdrop-blur-sm">
        {/* 左側：管線工具分組 */}
        <div className="flex items-center space-x-2.5 shrink-0">
          {/* 群組 1: 視覺一致性 (定裝圖) */}
          <button
            onClick={() => setIsContinuityOpen(true)}
            className="flex items-center h-7 px-3 rounded-md bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 hover:border-amber-cta transition-all whitespace-nowrap shrink-0 font-medium shadow-sm"
            title="開啟視覺一致性中心：設定主體定裝參考圖 (Hero Shot) 與各角色視覺特徵錨點"
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            <span>視覺一致性</span>
          </button>

          <div className="h-4 w-[1px] bg-cinema-border/60 shrink-0" />

          {/* 群組 2: 分段式管線操作 (Segmented Pipeline Buttons) */}
          <div className="flex items-center bg-cinema-card/70 rounded-md border border-cinema-border/70 p-0.5 space-x-0.5">
            <button
              onClick={handleBatchImages}
              className="flex items-center h-6 px-2.5 rounded text-cinema-muted hover:text-amber-cta hover:bg-cinema-card transition-colors whitespace-nowrap text-[11px] font-medium"
              title="批次為未出圖分鏡生成畫面"
            >
              <ImageIcon className="w-3 h-3 mr-1" />
              <span>出圖</span>
            </button>
            <button
              onClick={handleBatchPip}
              className="flex items-center h-6 px-2.5 rounded text-cinema-muted hover:text-amber-cta hover:bg-cinema-card transition-colors whitespace-nowrap text-[11px] font-medium"
              title="依據台詞自動向維基與 NASA 檢索真實歷史考據原照 (PiP)"
            >
              <Camera className="w-3 h-3 mr-1" />
              <span>考據 (PiP)</span>
            </button>
            <button
              onClick={handleBatchTTS}
              className="flex items-center h-6 px-2.5 rounded text-cinema-muted hover:text-amber-cta hover:bg-cinema-card transition-colors whitespace-nowrap text-[11px] font-medium"
              title="批次為未配音分鏡合成語音"
            >
              <Volume2 className="w-3 h-3 mr-1" />
              <span>配音</span>
            </button>
            <button
              onClick={handleCompose}
              className="flex items-center h-6 px-2.5 rounded text-cinema-text hover:text-amber-cta hover:bg-cinema-card transition-colors whitespace-nowrap text-[11px] font-medium"
              title={burnSubtitles ? "合成 1080p 成片（將燒錄 ASS 字幕）" : "合成 1080p 成片（極速直通，可下載 SRT 字幕）"}
            >
              <Play className="w-3 h-3 mr-1 fill-current text-amber-cta" />
              <span>合成</span>
            </button>
          </div>

          {/* 燒錄字幕開關 */}
          <label
            className="flex items-center space-x-1.5 cursor-pointer text-cinema-muted hover:text-cinema-text text-[11px] select-none px-1.5 shrink-0"
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

          <div className="h-4 w-[1px] bg-cinema-border/60 shrink-0" />

          {/* 專案預設發音人切換 */}
          <div className="flex items-center space-x-1 text-cinema-muted whitespace-nowrap shrink-0">
            <Mic className="w-3.5 h-3.5 text-amber-cta" />
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
              className="h-7 px-2 rounded-md bg-cinema-card border border-cinema-border text-cinema-text text-[11px] focus:outline-none focus:border-amber-cta cursor-pointer font-medium"
              title="切換專案預設發音人"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.gender})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 右側：提示與危險操作 */}
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={handleClearImagesOnly}
            className="flex items-center h-6 px-2 rounded hover:bg-amber-950/40 text-cinema-muted/80 hover:text-amber-400 border border-transparent hover:border-amber-900/60 transition-colors whitespace-nowrap text-[11px]"
            title="僅清空所有分鏡已生成的畫面圖片，保留語音配音、考據圖與台詞"
          >
            <ImageOff className="w-3 h-3 mr-1 text-amber-400/80" />
            <span>清空圖片</span>
          </button>
          <button
            onClick={handleClearAllMedia}
            className="flex items-center h-6 px-2 rounded hover:bg-red-950/40 text-cinema-muted/60 hover:text-red-400 border border-transparent hover:border-red-900/60 transition-colors whitespace-nowrap text-[11px]"
            title="清空所有已生成的圖片、配音、考據圖與成片，重置為初始待出圖狀態"
          >
            <Trash2 className="w-3 h-3 mr-1 text-red-400/70" />
            <span>清空素材</span>
          </button>
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
                    {/* 右上角黑底歷史聚焦常駐標籤（無論有無出圖，皆一眼可辨識） */}
                    {scene.pip_mode === "spotlight" && (
                      <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-amber-500/95 text-black font-semibold text-[9px] z-20 shadow-md flex items-center">
                        <span>🏛️ 黑底歷史聚焦</span>
                      </div>
                    )}

                    {scene.status.has_pip && scene.status.pip_url && scene.pip_mode === "spotlight" ? (
                      <div className="w-full h-full bg-black flex items-center justify-center overflow-hidden">
                        <img
                          src={scene.status.pip_url}
                          alt="Spotlight Archival"
                          className="max-h-[82%] max-w-[82%] object-contain rounded border border-white/80 shadow-2xl transition-transform group-hover:scale-105"
                          loading="lazy"
                        />
                      </div>
                    ) : (
                      <>
                        {hasImg && scene.status.image_url ? (
                          <img
                            key={scene.status.image_url}
                            src={scene.status.image_url}
                            alt={scene.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                          />
                        ) : scene.pip_mode === "spotlight" ? (
                          /* 黑底歷史聚焦的空狀態：純黑底 + 金色考據相機圖示 + 清楚標明免 AI 生圖 */
                          <div className="flex flex-col items-center justify-center w-full h-full bg-black text-amber-cta/90 p-2 text-center select-none">
                            <Camera className="w-7 h-7 stroke-1 mb-1 text-amber-cta" />
                            <span className="text-[11px] font-semibold text-amber-cta">待抓取黑底考據圖</span>
                            <span className="text-[9px] text-cinema-muted mt-0.5">免 AI 出圖 · 真實原照慢推</span>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted/40">
                            <ImageIcon className="w-8 h-8 stroke-1 mb-1" />
                            <span className="text-[10px]">待出圖</span>
                          </div>
                        )}

                        {/* 右半部置中真實考據畫中畫 (PiP) 浮動預覽卡（依原照比例自適應，不裁切） */}
                        {scene.pip_enabled && scene.status.has_pip && scene.status.pip_url && (
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
                        scene.pip_mode === "spotlight" ? (
                          <span className="flex items-center px-1.5 py-0.5 rounded bg-amber-950/90 border border-amber-600/80 text-amber-300 text-[10px] shadow-sm">
                            <Camera className="w-3 h-3 mr-0.5 text-amber-400" />
                            <span>待考據</span>
                          </span>
                        ) : (
                          <span className="flex items-center px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-800 text-amber-400 text-[10px]">
                            <AlertCircle className="w-3 h-3 mr-0.5" />
                            <span>缺圖</span>
                          </span>
                        )
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
                    {scene.pip_enabled && (scene.status.has_pip || scene.pip_query || scene.pip_error) && (
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
                            className={`flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono shadow-sm truncate ${
                              scene.pip_mode === "spotlight"
                                ? "bg-black/90 border border-amber-cta/70 text-amber-300"
                                : "bg-black/85 border border-purple-500/50 text-purple-200"
                            }`}
                            title={`考據檢索詞: ${scene.pip_query} (${scene.pip_mode === "spotlight" ? "黑底聚焦模式" : "畫中畫小卡模式"})`}
                          >
                            {scene.pip_mode === "spotlight" ? (
                              <Camera className="w-2.5 h-2.5 mr-1 text-amber-cta shrink-0" />
                            ) : (
                              <Search className="w-2.5 h-2.5 mr-1 text-purple-400 shrink-0" />
                            )}
                            <span className="truncate">
                              {scene.pip_mode === "spotlight" ? "聚焦: " : "PiP: "}
                              {scene.pip_query}
                            </span>
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
