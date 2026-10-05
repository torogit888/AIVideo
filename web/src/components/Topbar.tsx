import React, { useEffect, useState } from "react";
import {
  Sparkles,
  MoreVertical,
  Play,
  Square,
  Pause,
  Loader2,
  Trash2,
  Clock,
  RefreshCw,
  Camera,
  ImageOff,
  MicOff,
  Plus,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { srtMediaUrl } from "../studioActions";
import { ConnectionLights } from "./ConnectionLights";

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
    isPipelinePaused,
    pipelineProgress,
    pipelineMessage,
    pipelineCooldown,
    setPipelineRunning,
    setTab,
    showToast,
    selectJob,
    startNewDraft,
    loadJobs,
    loadScenes,
  } = useStudioStore();

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [burnSubtitles, setBurnSubtitles] = useState(false);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  const totalScenes = scenes.length || currentJob?.progress.scenes_count || 0;
  const readyImages = scenes.filter((s) => s.status.has_image).length;
  const readyAudio = scenes.filter((s) => s.status.has_audio).length;
  const hasFilm = currentJob?.progress.film_ready ?? false;

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

  useEffect(() => {
    const onOpenContinuity = () => setIsDropdownOpen(false);
    window.addEventListener("aivideo:open-continuity", onOpenContinuity);
    return () => window.removeEventListener("aivideo:open-continuity", onOpenContinuity);
  }, []);

  const handleRunAllPipeline = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 5, "正在啟動一鍵全流程 (逐幕出圖 ➔ 配音 ➔ 合成)...");
    await api.runPipeline(selectedJobId, "all", false, burnSubtitles);
  };

  const handleStopPipeline = async () => {
    if (selectedJobId) {
      await api.stopPipeline(selectedJobId);
      setPipelineRunning(false, 0, "任務已中止");
    }
  };

  const handlePausePipeline = async () => {
    if (!selectedJobId) return;
    await api.pausePipeline(selectedJobId);
    setPipelineRunning(true, pipelineProgress, "已請求暫停", pipelineCooldown, 0, true);
  };

  const handleResumePipeline = async () => {
    if (!selectedJobId) return;
    await api.resumePipeline(selectedJobId);
    setPipelineRunning(true, pipelineProgress, "已繼續", pipelineCooldown, 0, false);
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

  const runOverflow = async (fn: () => Promise<void>) => {
    setIsDropdownOpen(false);
    await fn();
  };

  const handleBatchPip = async () => {
    if (!selectedJobId) return;
    setPipelineRunning(true, 10, "正在跨來源檢索真實考據照片 (PiP)...");
    await api.runPipeline(selectedJobId, "pip");
  };

  const handleForceImages = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm("強制全覆蓋會重畫所有鏡頭畫面（含已完成）。確定？");
    if (!ok) return;
    setPipelineRunning(true, 10, "正在強制覆蓋出圖...");
    await api.runPipeline(selectedJobId, "images", true);
  };

  const handleClearImagesOnly = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm("確定清空所有分鏡已生成的圖片？（語音與口白會保留）");
    if (!ok) return;
    try {
      await api.clearJobImages(selectedJobId);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast("已清空所有分鏡圖片", "success");
    } catch (e: any) {
      showToast("清空圖片失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleClearAudioOnly = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm("確定清空所有分鏡已生成的配音？（畫面與口白會保留）");
    if (!ok) return;
    try {
      await api.clearJobAudio(selectedJobId);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast("已清空所有分鏡配音", "success");
    } catch (e: any) {
      showToast("清空配音失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleClearAllMedia = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm("確定清空所有已生成素材（圖、聲、考據、成片）？口白與設定會保留。");
    if (!ok) return;
    try {
      await api.clearJobMedia(selectedJobId);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast("已清空所有分鏡素材", "success");
    } catch (e: any) {
      showToast("清除失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  return (
    <header className="flex h-12 items-center justify-between px-4 border-b border-cinema-border bg-cinema-darker select-none gap-3">
      <div className="flex items-center space-x-2 min-w-0">
        <div className="relative min-w-[180px] max-w-[280px]">
          <select
            value={selectedJobId || ""}
            onChange={(e) => {
              if (!e.target.value) {
                startNewDraft();
                return;
              }
              selectJob(e.target.value);
            }}
            className="w-full h-8 pl-2.5 pr-7 rounded-lg bg-cinema-card border border-cinema-border/70 hover:border-cinema-muted text-xs text-cinema-text focus:outline-none focus:border-amber-cta appearance-none cursor-pointer font-medium truncate"
          >
            <option value="">新專案草稿</option>
            {jobs.map((j) => {
              const tag = j.progress.film_ready
                ? "已成片"
                : j.progress.images_ready > 0
                ? `製作中 ${j.progress.scenes_count} 鏡`
                : "草稿";
              return (
                <option key={j.id} value={j.id}>
                  {j.title || j.id} · {tag}
                </option>
              );
            })}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-cinema-muted text-[10px]">
            ▾
          </div>
        </div>
        <button
          onClick={() => {
            loadJobs();
            showToast("已重新掃描專案", "info");
          }}
          title="重新掃描 jobs 目錄"
          className="p-1.5 rounded-lg hover:bg-cinema-card text-cinema-muted hover:text-amber-cta"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => startNewDraft()}
          title="空白新專案"
          className="flex items-center h-7 px-2 rounded-lg text-[11px] text-cinema-muted hover:text-amber-cta hover:bg-cinema-card"
        >
          <Plus className="w-3.5 h-3.5 mr-0.5" />
          新建
        </button>
      </div>

      {currentTab === "storyboard" && (
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
                <span className="font-mono font-semibold text-cinema-text">
                  {isAllAudioDone ? "" : "~"}
                  {formatDurationText(estimatedTotalSec)}
                </span>
              </span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center space-x-2.5 shrink-0">
        <ConnectionLights compact />

        {isPipelineRunning ? (
          <div className="flex items-center space-x-2">
            <div
              className="flex items-center w-[220px] h-8 px-2.5 rounded-lg bg-cinema-card border border-amber-cta/40 shadow-sm shrink-0 select-none overflow-hidden"
              title={`當前完整狀態: ${pipelineMessage || "處理中..."} (${Math.round(pipelineProgress)}%)`}
            >
              <div className="w-5 h-5 flex items-center justify-center shrink-0 mr-1.5">
                {cooldownRemaining > 0 ? (
                  <span className="w-3.5 h-3.5 rounded-full border-2 border-amber-cta/30 border-t-amber-cta animate-spin" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-cta" />
                )}
              </div>
              <div className="flex-1 min-w-0 text-left">
                <span className="block truncate text-xs text-amber-cta font-medium">
                  {formatCompactStatus(pipelineMessage, cooldownRemaining)}
                </span>
              </div>
              <div className="w-9 text-right font-mono text-xs font-bold text-cinema-text shrink-0 pl-1 border-l border-cinema-border/60">
                {cooldownRemaining > 0 ? `${cooldownRemaining}s` : `${Math.min(100, Math.round(pipelineProgress))}%`}
              </div>
            </div>
            {isPipelinePaused ? (
              <button
                onClick={handleResumePipeline}
                className="flex items-center justify-center h-8 px-2.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs shrink-0"
              >
                <Play className="w-3 h-3 mr-1 fill-current" />
                <span>繼續</span>
              </button>
            ) : (
              <button
                onClick={handlePausePipeline}
                className="flex items-center justify-center h-8 px-2.5 rounded-lg border border-cinema-border bg-cinema-card text-cinema-text hover:text-amber-cta text-xs shrink-0"
              >
                <Pause className="w-3 h-3 mr-1 fill-current" />
                <span>暫停</span>
              </button>
            )}
            <button
              onClick={handleStopPipeline}
              className="flex items-center justify-center h-8 px-2.5 rounded-lg bg-red-950/70 hover:bg-red-900 border border-red-800/80 text-xs text-red-200 transition-colors shrink-0"
            >
              <Square className="w-3 h-3 mr-1 fill-current" />
              <span>停止</span>
            </button>
          </div>
        ) : currentTab === "storyboard" && selectedJobId ? (
          hasFilm ? (
            <button
              onClick={() => setTab("film")}
              className="flex items-center h-8 px-3.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow-sm active:scale-95 shrink-0"
              title="成片已就緒，點擊前往預覽成片"
            >
              <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
              <span>預覽成片</span>
            </button>
          ) : (
            <button
              onClick={handleRunAllPipeline}
              className="flex items-center h-8 px-3.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow-sm glow-amber active:scale-95 shrink-0"
              title="一鍵全自動：每幕先出圖 ➔ 再配音 ➔ 自動合成 1080p 影片"
            >
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
              <span>🚀 一鍵全流程</span>
            </button>
          )
        ) : null}

        <div className="relative shrink-0">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="p-1.5 rounded-lg hover:bg-cinema-card text-cinema-muted hover:text-cinema-text transition-colors"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {isDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-52 rounded-md bg-cinema-card border border-cinema-border shadow-xl py-1 z-50 text-xs text-cinema-text"
              onMouseLeave={() => setIsDropdownOpen(false)}
            >
              {currentTab === "storyboard" && selectedJobId && (
                <>
                  <button
                    className="w-full text-left px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      window.dispatchEvent(new CustomEvent("aivideo:open-continuity"));
                    }}
                  >
                    視覺定裝
                  </button>
                  <button
                    className="w-full text-left flex items-center px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
                    onClick={() => runOverflow(handleBatchPip)}
                  >
                    <Camera className="w-3.5 h-3.5 mr-2" />
                    批次考據
                  </button>
                  <button
                    className="w-full text-left px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
                    onClick={() => runOverflow(handleForceImages)}
                  >
                    強制全覆蓋出圖
                  </button>
                  <label className="flex items-center justify-between px-3 py-1.5 hover:bg-cinema-cardHover cursor-pointer">
                    <span>燒錄字幕</span>
                    <input
                      type="checkbox"
                      checked={burnSubtitles}
                      onChange={(e) => {
                        setBurnSubtitles(e.target.checked);
                        window.dispatchEvent(
                          new CustomEvent("aivideo:burn-subtitles", { detail: e.target.checked })
                        );
                      }}
                      className="rounded border-cinema-border bg-cinema-darker text-amber-cta w-3.5 h-3.5"
                    />
                  </label>
                  <button
                    className="w-full text-left flex items-center px-3 py-1.5 hover:bg-cinema-cardHover text-cinema-muted hover:text-amber-400"
                    onClick={() => runOverflow(handleClearImagesOnly)}
                  >
                    <ImageOff className="w-3.5 h-3.5 mr-2" />
                    清空圖片
                  </button>
                  <button
                    className="w-full text-left flex items-center px-3 py-1.5 hover:bg-cinema-cardHover text-cinema-muted hover:text-sky-400"
                    onClick={() => runOverflow(handleClearAudioOnly)}
                  >
                    <MicOff className="w-3.5 h-3.5 mr-2" />
                    清空配音
                  </button>
                  <button
                    className="w-full text-left px-3 py-1.5 hover:bg-cinema-cardHover text-cinema-muted hover:text-red-400"
                    onClick={() => runOverflow(handleClearAllMedia)}
                  >
                    清空素材
                  </button>
                  <div className="my-1 border-t border-cinema-border" />
                </>
              )}
              <a
                href={selectedJobId ? `/media/jobs/${encodeURIComponent(selectedJobId)}/compose/film.mp4` : "#"}
                download
                className="block px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
              >
                下載 1080p MP4
              </a>
              <a
                href={selectedJobId ? srtMediaUrl(selectedJobId) : "#"}
                download
                className="block px-3 py-1.5 hover:bg-cinema-cardHover hover:text-amber-cta"
              >
                下載 SRT 字幕
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
