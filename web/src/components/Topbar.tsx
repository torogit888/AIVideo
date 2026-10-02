import React, { useState } from "react";
import { Sparkles, MoreVertical, Play, Square, Loader2, Trash2, Clock } from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";

// 狀態文字智慧精簡器：將冗長的後端描述轉化為固定簡潔標籤，避免版面劇烈晃動
const formatCompactStatus = (rawMsg: string, cooldownSec: number): string => {
  if (cooldownSec > 0) return `配額冷卻 ${cooldownSec}s`;
  if (!rawMsg) return "處理中...";

  const sceneMatch = rawMsg.match(/第\s*(\d+)\s*幕/);
  const scenePrefix = sceneMatch ? `#${sceneMatch[1]} ` : "";

  if (rawMsg.includes("提示詞") || rawMsg.includes("Prompt")) return `${scenePrefix}生圖 Prompt`;
  if (rawMsg.includes("生圖") || rawMsg.includes("繪製")) return `${scenePrefix}繪製畫面`;
  if (rawMsg.includes("語音") || rawMsg.includes("TTS") || rawMsg.includes("配音")) return `${scenePrefix}合成語音`;
  if (rawMsg.includes("合成") || rawMsg.includes("1080p") || rawMsg.includes("compose")) return "合成 1080p 影片";
  if (rawMsg.includes("考據")) return `${scenePrefix}考據驗證`;
  if (rawMsg.includes("啟動")) return "啟動生成中";
  if (rawMsg.includes("冷卻")) return `配額冷卻 ${cooldownSec || ""}s`.trim();

  return rawMsg.replace(/正在|進行中|\.\.\./g, "").trim().slice(0, 14);
};

export const Topbar: React.FC = () => {
  const {
    currentTab,
    jobs,
    selectedJobId,
    scenes,
    isPipelineRunning,
    pipelineProgress,
    pipelineMessage,
    pipelineCooldown,
    setPipelineRunning,
    setTab,
    showToast,
    selectJob,
  } = useStudioStore();

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  // 狀態計算
  const totalScenes = scenes.length || currentJob?.progress.scenes_count || 0;
  const readyImages = scenes.filter((s) => s.status.has_image).length;
  const readyAudio = scenes.filter((s) => s.status.has_audio).length;
  const hasFilm = currentJob?.progress.film_ready ?? false;

  // 依據目前分鏡語音時間加總並預估成片時間
  const readyAudioScenes = scenes.filter((s) => s.status.has_audio && (s.status.duration || 0) > 0);
  const totalAudioSec = readyAudioScenes.reduce((sum, s) => sum + (s.status.duration || 0), 0);

  let estimatedTotalSec = 0;
  if (readyAudio === totalScenes && totalScenes > 0 && totalAudioSec > 0) {
    estimatedTotalSec = totalAudioSec;
  } else if (readyAudioScenes.length > 0 && totalScenes > 0) {
    const avgSec = totalAudioSec / readyAudioScenes.length;
    estimatedTotalSec = totalAudioSec + avgSec * (totalScenes - readyAudioScenes.length);
  } else if (currentJob?.progress.estimated_duration_sec) {
    estimatedTotalSec = currentJob.progress.estimated_duration_sec;
  } else if (totalScenes > 0) {
    estimatedTotalSec = totalScenes * 5.5;
  }

  const formatDurationText = (sec: number): string => {
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

  const isAllAudioDone = readyAudio === totalScenes && totalScenes > 0;
  const durationTooltip = isAllAudioDone
    ? `全部分鏡已完成配音，成片總長度預計為 ${formatDurationText(estimatedTotalSec)} (${Math.round(totalAudioSec)} 秒)`
    : readyAudioScenes.length > 0
    ? `已完成 ${readyAudio}/${totalScenes} 幕配音 (${formatDurationText(totalAudioSec)})，依平均時長預估全片長度約 ${formatDurationText(estimatedTotalSec)}`
    : `尚未生成語音，依標準每幕 5.5 秒預估全片長度約 ${formatDurationText(estimatedTotalSec)}`;

  const cooldownRemaining =
    pipelineCooldown > 0
      ? pipelineCooldown
      : Number((pipelineMessage || "").match(/冷卻(?:倒數)?\s*(\d+)/)?.[1] || 0);

  // 頂列唯一主按鈕狀態機
  const handlePrimaryAction = async () => {
    if (!selectedJobId) return;

    if (readyImages < totalScenes || readyAudio < totalScenes) {
      setPipelineRunning(true, 5, "正在啟動一鍵逐幕生成（生圖 ➔ 配音 ➔ 考據）...");
      await api.runPipeline(selectedJobId, "all");
    } else if (!hasFilm) {
      setPipelineRunning(true, 10, "正在合成 1080p 影片...");
      await api.runPipeline(selectedJobId, "compose");
    } else {
      setTab("film");
    }
  };

  const handleStopPipeline = async () => {
    if (selectedJobId) {
      await api.stopPipeline(selectedJobId);
      setPipelineRunning(false, 0, "任務已中止");
    }
  };

  const handleDeleteJob = async () => {
    if (!selectedJobId) return;
    const confirmDelete = window.confirm(
      `確定要徹底刪除專案【${currentJob?.title || selectedJobId}】嗎？\n\n此操作將永久刪除此專案的所有分鏡、生圖、配音與成片，無法復原！`
    );
    if (!confirmDelete) return;

    try {
      await api.deleteJob(selectedJobId);
      setIsDropdownOpen(false);
      const remainingJobs = await api.getJobs();
      useStudioStore.setState({ jobs: remainingJobs });
      if (remainingJobs.length > 0) {
        selectJob(remainingJobs[0].id);
      } else {
        useStudioStore.setState({ selectedJobId: null, scenes: [], activeSceneId: null });
      }
      showToast("專案已成功刪除！", "success");
    } catch (e: any) {
      showToast("刪除專案失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  // 智能感知模式：非分鏡分頁時的處理
  if (currentTab !== "storyboard") {
    // 平時完全不渲染 Topbar，讓總覽、腳本、成片與素材庫獲得 100% 滿版高度
    if (!isPipelineRunning) return null;

    // 若背景正在生成，以輕量橫幅浮現，顯示進度與快速回到分鏡按鈕
    return (
      <header className="flex h-9 items-center justify-between px-4 border-b border-amber-cta/30 bg-cinema-darker/95 backdrop-blur select-none">
        <div className="flex items-center space-x-2 text-xs">
          <span className="flex items-center text-amber-cta font-medium">
            <span className="w-2 h-2 rounded-full mr-2 bg-amber-cta animate-ping" />
            背景生成進行中
          </span>
          <span className="text-cinema-border">·</span>
          <span className="text-cinema-muted truncate max-w-[200px]">
            {currentJob?.title || selectedJobId}
          </span>
          <button
            onClick={() => setTab("storyboard")}
            className="text-[11px] text-amber-cta/80 hover:text-amber-cta underline ml-1 cursor-pointer transition-colors"
          >
            前往分鏡看板 ➔
          </button>
        </div>

        {/* 右側：防抖狀態膠囊 + 停止按鈕 */}
        <div className="flex items-center space-x-2">
          <div
            className="flex items-center w-[230px] h-7 px-2.5 rounded-lg bg-cinema-card border border-amber-cta/40 shadow-sm shrink-0 select-none overflow-hidden"
            title={`當前完整狀態: ${pipelineMessage || "處理中..."} (${Math.round(pipelineProgress)}%)`}
          >
            <div className="w-4 h-4 flex items-center justify-center shrink-0 mr-1.5">
              {cooldownRemaining > 0 ? (
                <span className="w-3 h-3 rounded-full border-2 border-amber-cta/30 border-t-amber-cta animate-spin" />
              ) : (
                <Loader2 className="w-3 h-3 animate-spin text-amber-cta" />
              )}
            </div>
            <div className="flex-1 min-w-0 text-left">
              <span className="block truncate text-[11px] text-amber-cta font-medium">
                {formatCompactStatus(pipelineMessage, cooldownRemaining)}
              </span>
            </div>
            <div className="w-9 text-right font-mono text-[11px] font-bold text-cinema-text shrink-0 pl-1 border-l border-cinema-border/60">
              {cooldownRemaining > 0 ? `${cooldownRemaining}s` : `${Math.min(100, Math.round(pipelineProgress))}%`}
            </div>
          </div>
          <button
            onClick={handleStopPipeline}
            className="flex items-center justify-center h-7 px-2.5 rounded-lg bg-red-950/70 hover:bg-red-900 border border-red-800/80 text-[11px] text-red-200 transition-colors shrink-0"
            title="中止當前流水線任務"
          >
            <Square className="w-2.5 h-2.5 mr-1 fill-current" />
            <span>停止</span>
          </button>
        </div>
      </header>
    );
  }

  // 分鏡看板專用完整 Topbar (48px)
  return (
    <header className="flex h-12 items-center justify-between px-4 border-b border-cinema-border bg-cinema-darker select-none">
      {/* 左：當前專案標題與 ID (精緻簡潔) */}
      <div className="flex items-center space-x-2.5">
        <div
          onClick={() => setTab("overview")}
          title="點擊前往專案總覽"
          className="flex items-center space-x-2 cursor-pointer group"
        >
          <span className="text-xs font-semibold text-cinema-text group-hover:text-amber-cta transition-colors tracking-wide max-w-[220px] truncate">
            {currentJob?.title || "未選取專案"}
          </span>
          {selectedJobId && (
            <span className="text-[10px] font-mono text-cinema-muted/70 bg-cinema-card px-2 py-0.5 rounded border border-cinema-border/50 truncate max-w-[160px]">
              {selectedJobId}
            </span>
          )}
        </div>
      </div>

      {/* 中：完成度膠囊指標 */}
      <div className="hidden md:flex items-center select-none">
        {totalScenes === 0 ? (
          <span className="text-cinema-muted text-xs font-mono">尚無分鏡資料</span>
        ) : (
          <div className="flex items-center bg-cinema-card/60 border border-cinema-border/60 rounded-full px-3 py-1 space-x-2.5 text-[11px] text-cinema-muted">
            <span className="flex items-center">
              <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-amber-cta/80" />
              <span className="text-cinema-muted mr-1">圖</span>
              <span className={`font-mono font-semibold ${readyImages === totalScenes && totalScenes > 0 ? "text-emerald-400" : "text-cinema-text"}`}>
                {readyImages}/{totalScenes}
              </span>
            </span>
            <span className="text-cinema-border/80">·</span>
            <span className="flex items-center">
              <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-sky-400/80" />
              <span className="text-cinema-muted mr-1">聲</span>
              <span className={`font-mono font-semibold ${readyAudio === totalScenes && totalScenes > 0 ? "text-emerald-400" : "text-cinema-text"}`}>
                {readyAudio}/{totalScenes}
              </span>
            </span>
            <span className="text-cinema-border/80">·</span>
            <span className="flex items-center" title={durationTooltip}>
              <Clock className="w-3 h-3 mr-1 text-amber-cta/80" />
              <span className="text-cinema-muted mr-1">片長</span>
              <span className="font-mono font-semibold text-cinema-text">
                {isAllAudioDone ? "" : "~"}{formatDurationText(estimatedTotalSec)}
              </span>
            </span>
            <span className="text-cinema-border/80">·</span>
            <span className={`flex items-center font-medium ${hasFilm ? "text-emerald-400" : "text-amber-500"}`}>
              {hasFilm ? "🟢 1080p 已成片" : "⏳ 待合成"}
            </span>
          </div>
        )}
      </div>

      {/* 右：定寬防抖狀態膠囊 + 實心主 CTA + ⋯ 選單 */}
      <div className="flex items-center space-x-2.5">
        {isPipelineRunning ? (
          <div className="flex items-center space-x-2">
            {/* 絕對鎖定寬度 (240px)，中間平滑截斷，數字等寬，杜絕任何晃動 */}
            <div
              className="flex items-center w-[240px] h-8 px-2.5 rounded-lg bg-cinema-card border border-amber-cta/40 shadow-sm shrink-0 select-none overflow-hidden"
              title={`當前完整狀態: ${pipelineMessage || "處理中..."} (${Math.round(pipelineProgress)}%)`}
            >
              {/* 左側固定寬度圖示槽 */}
              <div className="w-5 h-5 flex items-center justify-center shrink-0 mr-1.5">
                {cooldownRemaining > 0 ? (
                  <span className="w-3.5 h-3.5 rounded-full border-2 border-amber-cta/30 border-t-amber-cta animate-spin" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-cta" />
                )}
              </div>

              {/* 中間文字槽：自適應佔滿、平滑截斷 */}
              <div className="flex-1 min-w-0 text-left">
                <span className="block truncate text-xs text-amber-cta font-medium">
                  {formatCompactStatus(pipelineMessage, cooldownRemaining)}
                </span>
              </div>

              {/* 右側固定寬度等寬數值槽 (38px)：鎖定寬度不抖動 */}
              <div className="w-9 text-right font-mono text-xs font-bold text-cinema-text shrink-0 pl-1 border-l border-cinema-border/60">
                {cooldownRemaining > 0 ? `${cooldownRemaining}s` : `${Math.min(100, Math.round(pipelineProgress))}%`}
              </div>
            </div>

            <button
              onClick={handleStopPipeline}
              className="flex items-center justify-center h-8 px-2.5 rounded-lg bg-red-950/70 hover:bg-red-900 border border-red-800/80 text-xs text-red-200 transition-colors shrink-0"
              title="中止當前流水線任務"
            >
              <Square className="w-3 h-3 mr-1 fill-current" />
              <span>停止</span>
            </button>
          </div>
        ) : (
          <button
            onClick={handlePrimaryAction}
            className="flex items-center h-8 px-3.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow-sm glow-amber active:scale-95 shrink-0"
          >
            {readyImages < totalScenes || readyAudio < totalScenes ? (
              <>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>一鍵生成 (圖+聲+考據)</span>
              </>
            ) : !hasFilm ? (
              <>
                <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                <span>合成 1080p</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                <span>預覽成片</span>
              </>
            )}
          </button>
        )}

        {/* ⋯ 選單 */}
        <div className="relative shrink-0">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="p-1.5 rounded-lg hover:bg-cinema-card text-cinema-muted hover:text-cinema-text transition-colors"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {isDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-44 rounded-md bg-cinema-card border border-cinema-border shadow-xl py-1 z-50 text-xs text-cinema-text"
              onMouseLeave={() => setIsDropdownOpen(false)}
            >
              <a
                href={selectedJobId ? `/media/jobs/${encodeURIComponent(selectedJobId)}/compose/film.mp4` : "#"}
                download
                className="block px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
              >
                下載 1080p MP4
              </a>
              <a
                href={selectedJobId ? `/media/jobs/${encodeURIComponent(selectedJobId)}/compose/film.srt` : "#"}
                download
                className="block px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
              >
                下載 SRT 字幕 (YouTube)
              </a>
              <a
                href={selectedJobId ? `/media/jobs/${encodeURIComponent(selectedJobId)}/preview.html` : "#"}
                target="_blank"
                rel="noreferrer"
                className="block px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
              >
                開啟 HTML 故事板
              </a>
              <div className="my-1 border-t border-cinema-border" />
              <button
                onClick={handleDeleteJob}
                className="w-full text-left flex items-center px-3 py-1.5 text-red-400 hover:bg-red-950/40 hover:text-red-300 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5 mr-2" />
                <span>刪除此專案</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
