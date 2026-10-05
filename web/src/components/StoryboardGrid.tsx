import React, { useEffect, useState } from "react";
import { Image as ImageIcon, Volume2, CheckCircle2, AlertCircle, Camera, Search, Play, Sparkles, Clock, Lock } from "lucide-react";
import { useStudioStore } from "../store";
import { SceneSummary } from "../types";
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

  const [isContinuityOpen, setIsContinuityOpen] = useState(false);
  const [burnSubtitles, setBurnSubtitles] = useState(false);
  const [dismissSetup, setDismissSetup] = useState(false);
  const [hasHeroImage, setHasHeroImage] = useState<boolean | null>(null);

  const checkAnchorsStatus = async () => {
    if (!selectedJobId) {
      setHasHeroImage(null);
      return;
    }
    try {
      const anchors = await api.getJobAnchors(selectedJobId);
      const isConfigured = Boolean(
        anchors.has_hero_image || (anchors.characters && anchors.characters.some((c) => c.has_image))
      );
      setHasHeroImage(isConfigured);
    } catch {
      setHasHeroImage(null);
    }
  };

  useEffect(() => {
    const open = () => setIsContinuityOpen(true);
    const burn = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail;
      if (typeof detail === "boolean") setBurnSubtitles(detail);
    };
    window.addEventListener("aivideo:open-continuity", open);
    window.addEventListener("aivideo:burn-subtitles", burn as EventListener);
    window.addEventListener("aivideo:anchors-updated", checkAnchorsStatus);
    return () => {
      window.removeEventListener("aivideo:open-continuity", open);
      window.removeEventListener("aivideo:burn-subtitles", burn as EventListener);
      window.removeEventListener("aivideo:anchors-updated", checkAnchorsStatus);
    };
  }, [selectedJobId]);

  useEffect(() => {
    if (!selectedJobId) return;
    setDismissSetup(localStorage.getItem(`aivideo_continuity_dismissed_${selectedJobId}`) === "1");
    checkAnchorsStatus();
  }, [selectedJobId]);

  // 當專案存在時，確保分鏡列表自動載入
  useEffect(() => {
    if (selectedJobId) {
      loadScenes(selectedJobId);
    }
  }, [selectedJobId, loadScenes]);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  // 依據目前分鏡語音時間加總並預估成片時間
  const totalScenes = scenes.length;
  const readyAudioScenes = scenes.filter((s) => s.status.has_audio && (s.status.duration || 0) > 0);
  const totalAudioSec = readyAudioScenes.reduce((sum, s) => sum + (s.status.duration || 0), 0);

  let estimatedTotalSec = 0;
  if (readyAudioScenes.length === totalScenes && totalScenes > 0 && totalAudioSec > 0) {
    estimatedTotalSec = totalAudioSec;
  } else if (readyAudioScenes.length > 0 && totalScenes > 0) {
    const avgSec = totalAudioSec / readyAudioScenes.length;
    estimatedTotalSec = totalAudioSec + avgSec * (totalScenes - readyAudioScenes.length);
  } else if (currentJob?.progress.estimated_duration_sec) {
    estimatedTotalSec = currentJob.progress.estimated_duration_sec;
  } else if (totalScenes > 0) {
    estimatedTotalSec = totalScenes * 5.5;
  }

  const formatTime = (sec: number): string => {
    const total = Math.round(sec);
    const m = Math.floor(total / 60);
    const s = total % 60;
    if (m >= 60) {
      const h = Math.floor(m / 60);
      const remM = m % 60;
      return `${h}:${String(remM).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const isAllAudioDone = readyAudioScenes.length === totalScenes && totalScenes > 0;
  const durationTooltip = isAllAudioDone
    ? `全部分鏡已完成配音，成片總長度預計為 ${formatTime(estimatedTotalSec)} (${Math.round(totalAudioSec)} 秒)`
    : readyAudioScenes.length > 0
    ? `已完成 ${readyAudioScenes.length}/${totalScenes} 幕配音 (${formatTime(totalAudioSec)})，依平均時長預估全片長度約 ${formatTime(estimatedTotalSec)}`
    : `尚未生成語音，依標準每幕 5.5 秒預估全片長度約 ${formatTime(estimatedTotalSec)}`;

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
    setPipelineRunning(
      true,
      10,
      burnSubtitles ? "正在合成 1080p 影片 (燒錄 ASS 字幕)..." : "正在極速合成 1080p 影片 (純淨畫面直通合流)..."
    );
    await api.runPipeline(selectedJobId, "compose", false, burnSubtitles);
  };

  const handleTogglePip = async (on: boolean) => {
    if (!selectedJobId) return;
    try {
      await api.updateJob(selectedJobId, { use_pip: on });
      await loadJobs();
      showToast(on ? "已開啟本片考據 PiP" : "已關閉本片考據 PiP", "success");
    } catch (e: any) {
      showToast("更新 PiP 開關失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const showSetupBanner =
    Boolean(selectedJobId) && totalScenes > 0 && !dismissSetup && hasHeroImage === false;

  const actCount = new Set(scenes.map((s) => s.act_index || 0).filter((n) => n > 0)).size;
  const groups: { key: string; title: string; items: SceneSummary[] }[] = [];
  for (const scene of scenes) {
    const idx = scene.act_index || 0;
    const title = idx
      ? `第 ${idx} 幕 · ${scene.act_title || "鏡頭"}`
      : "鏡頭";
    const last = groups[groups.length - 1];
    if (last && last.key === String(idx)) last.items.push(scene);
    else groups.push({ key: String(idx), title, items: [scene] });
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-cinema-bg">
      {showSetupBanner && (
        <div className="flex items-center justify-between px-5 py-2 border-b border-amber-cta/30 bg-amber-cta/8 text-xs">
          <div className="flex items-center text-amber-cta">
            <Sparkles className="w-3.5 h-3.5 mr-2" />
            <span>尚未定裝。先為角色產出參考圖，後面出圖才會長得像同一個人。</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsContinuityOpen(true)}
              className="h-7 px-3 rounded bg-amber-cta text-cinema-bg font-semibold"
            >
              開始定裝
            </button>
            <button
              onClick={() => {
                if (selectedJobId) {
                  localStorage.setItem(`aivideo_continuity_dismissed_${selectedJobId}`, "1");
                }
                setDismissSetup(true);
              }}
              className="h-7 px-2 text-cinema-muted hover:text-cinema-text"
            >
              略過
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between px-5 py-2 border-b border-cinema-border/50 text-xs overflow-x-auto gap-4 bg-cinema-bg/95 backdrop-blur-sm">
        <div className="flex items-center space-x-2.5 shrink-0">
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
              title={burnSubtitles ? "合成 1080p 成片（將燒錄 ASS 字幕）" : "合成 1080p 成片"}
            >
              <Play className="w-3 h-3 mr-1 fill-current text-amber-cta" />
              <span>合成</span>
            </button>
          </div>

          <label
            className="flex items-center space-x-1.5 cursor-pointer text-cinema-muted hover:text-cinema-text text-[11px] select-none px-1.5 shrink-0"
            title="Job 級考據開關。預設關閉；打開後一鍵 all 才會跑考據"
          >
            <input
              type="checkbox"
              checked={Boolean(currentJob?.use_pip)}
              onChange={(e) => handleTogglePip(e.target.checked)}
              className="rounded border-cinema-border bg-cinema-darker text-amber-cta focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <span>考據 PiP</span>
          </label>

          {totalScenes > 0 && (
            <div className="hidden sm:flex items-center h-7 px-2.5 rounded-md text-[11px] text-cinema-muted shrink-0">
              大綱 {actCount || "—"} 幕 · 鏡頭 {totalScenes} 張
            </div>
          )}

          {totalScenes > 0 && (
            <div
              className="flex items-center h-7 px-2.5 rounded-md bg-cinema-card/70 border border-cinema-border/70 text-cinema-muted space-x-1.5 shrink-0 select-none"
              title={durationTooltip}
            >
              <Clock className="w-3.5 h-3.5 text-amber-cta" />
              <span className="text-[11px]">預估片長</span>
              <span className="font-mono font-semibold text-cinema-text text-[11px]">
                {isAllAudioDone ? "" : "~"}
                {formatTime(estimatedTotalSec)}
              </span>
            </div>
          )}
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
          <div className="space-y-8">
            {groups.map((group) => (
              <section key={group.key} className="space-y-3">
                {groups.length > 1 && (
                  <div className="flex items-baseline justify-between px-0.5">
                    <h3 className="text-sm font-semibold text-cinema-text">{group.title}</h3>
                    <span className="text-[11px] text-cinema-muted font-mono">{group.items.length} 鏡</span>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {group.items.map((scene: SceneSummary) => {
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
                    {/* 右上角黑底歷史聚焦常駐標籤（需同時滿足已啟用考據，無論有無出圖皆可辨識） */}
                    {scene.pip_enabled && scene.pip_mode === "spotlight" && (
                      <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-amber-500/95 text-black font-semibold text-[9px] z-20 shadow-md flex items-center">
                        <span>🏛️ 黑底歷史聚焦</span>
                      </div>
                    )}

                    {scene.pip_enabled && scene.status.has_pip && scene.status.pip_url && scene.pip_mode === "spotlight" ? (
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
                        ) : scene.pip_enabled && scene.pip_mode === "spotlight" ? (
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

                        {/* 右半部置中真實考據畫中畫 (PiP) 浮動預覽卡（白底拍立得/博物館實體卡片風格，黑底聚焦保持黑底） */}
                        {scene.pip_enabled && scene.status.has_pip && scene.status.pip_url && (
                          <div
                            className="absolute top-1/2 -translate-y-1/2 right-2 max-w-[30%] max-h-[75%] rounded-[6px] border-[2px] border-white/95 bg-white p-1 overflow-hidden shadow-2xl z-10 transition-transform group-hover:scale-105 flex items-center justify-center"
                            title={`PiP 真實考據圖 (白底卡片): ${scene.pip_query || "pip.png"}`}
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
                        scene.pip_enabled && scene.pip_mode === "spotlight" ? (
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
                      {formatTime(scene.status.duration)}
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
                      {(scene.locks?.image || scene.locks?.speech) && (
                        <span title="已鎖定">
                          <Lock className="w-3 h-3 text-amber-cta shrink-0" />
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-cinema-muted line-clamp-2 leading-relaxed">
                      {scene.narration}
                    </p>
                  </div>
                </div>
              );
            })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      {/* 定裝參考中心彈窗 */}
      <VisualContinuityModal
        isOpen={isContinuityOpen}
        onClose={() => setIsContinuityOpen(false)}
      />
    </div>
  );
};
