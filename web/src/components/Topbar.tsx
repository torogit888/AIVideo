import React, { useEffect, useState } from "react";
import { Sparkles, RefreshCw, MoreVertical, Play, Square, Loader2, Trash2 } from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { AI_TEXT_MODELS } from "../types";

const CooldownRing: React.FC<{ remaining: number; total: number }> = ({ remaining, total }) => {
  const size = 32;
  const stroke = 3;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(1, remaining / Math.max(1, total));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`冷卻 ${remaining}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#2A2A30" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#E8B86D"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct)}
        />
      </svg>
      <div
        className="absolute inset-[3px] rounded-full border-2 border-transparent border-t-amber-cta animate-spin"
        style={{ animationDuration: "0.9s" }}
      />
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold font-mono text-amber-cta leading-none">
        {remaining}
      </span>
    </div>
  );
};

export const Topbar: React.FC = () => {
  const {
    jobs,
    selectedJobId,
    selectJob,
    loadJobs,
    scenes,
    isPipelineRunning,
    pipelineProgress,
    pipelineMessage,
    pipelineCooldown,
    pipelineCooldownTotal,
    setPipelineRunning,
    setTab,
    showToast,
    selectedAiModel,
    setSelectedAiModel,
  } = useStudioStore();

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isServerOnline, setIsServerOnline] = useState<boolean | null>(null);

  useEffect(() => {
    loadJobs();
    const checkHealth = () => {
      api
        .getSystemStatus()
        .then(() => setIsServerOnline(true))
        .catch(() => setIsServerOnline(false));
    };
    checkHealth();
    const timer = setInterval(checkHealth, 4000);
    return () => clearInterval(timer);
  }, [loadJobs]);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  // 狀態計算
  const totalScenes = scenes.length || currentJob?.progress.scenes_count || 0;
  const readyImages = scenes.filter((s) => s.status.has_image).length;
  const readyAudio = scenes.filter((s) => s.status.has_audio).length;
  const hasFilm = currentJob?.progress.film_ready ?? false;

  // 計算頂列一句話完成度
  const statusSentence =
    totalScenes === 0
      ? "尚無可用分鏡"
      : `圖 ${readyImages}/${totalScenes} · 聲 ${readyAudio}/${totalScenes} · ${hasFilm ? "🟢 已合成" : "⏳ 待合成"}`;

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

  return (
    <header className="flex h-12 items-center justify-between px-4 border-b border-cinema-border bg-cinema-darker select-none">
      {/* 左：專案下拉 */}
      <div className="flex items-center space-x-2">
        <div className="relative">
          <select
            value={selectedJobId || ""}
            onChange={(e) => selectJob(e.target.value)}
            className="h-8 pl-3 pr-8 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta appearance-none cursor-pointer"
          >
            {jobs.length === 0 && <option value="">無專案</option>}
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} ({j.id})
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-cinema-muted">
            ▾
          </div>
        </div>
        <button
          onClick={() => loadJobs()}
          title="重新整理專案"
          className="p-1.5 rounded hover:bg-cinema-card text-cinema-muted hover:text-cinema-text transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* 全域 AI 模型膠囊選擇器 */}
        <div className="relative flex items-center ml-1">
          <div className="flex items-center h-8 pl-2.5 pr-6 rounded-full bg-cinema-card border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium transition-all shadow-sm">
            <span className="text-xs mr-1">⚡</span>
            <select
              value={selectedAiModel}
              onChange={(e) => {
                setSelectedAiModel(e.target.value);
                const item = AI_TEXT_MODELS.find((m) => m.id === e.target.value);
                if (item) showToast(`已切換核心 AI 模型為 ${item.name}`, "info");
              }}
              title="切換全域 AI 文本生成模型 (Vertex AI Gemini Flash)"
              className="bg-transparent text-amber-cta text-xs font-semibold focus:outline-none appearance-none cursor-pointer pr-1"
            >
              {AI_TEXT_MODELS.map((m) => (
                <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text py-1">
                  {m.badge} ({m.tag})
                </option>
              ))}
            </select>
          </div>
          <div className="pointer-events-none absolute right-2 text-amber-cta/70 text-[10px]">
            ▾
          </div>
        </div>

        {/* 後端連線狀態燈 */}
        <div
          title={
            isServerOnline === true
              ? "後端 API 服務在線 (Port 8000)"
              : isServerOnline === false
              ? "後端 API 連線中斷 / 伺服器正在熱重載中..."
              : "檢測後端連線中..."
          }
          className={`flex items-center px-2 py-1 rounded-full text-[10px] font-mono border transition-all ${
            isServerOnline === true
              ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-400"
              : isServerOnline === false
              ? "bg-red-950/70 border-red-800 text-red-300 animate-pulse"
              : "bg-cinema-card border-cinema-border text-cinema-muted"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
              isServerOnline === true
                ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
                : isServerOnline === false
                ? "bg-red-400 shadow-[0_0_6px_#f87171]"
                : "bg-cinema-muted"
            }`}
          />
          <span>{isServerOnline === true ? "API 在線" : isServerOnline === false ? "重連中" : "連線中"}</span>
        </div>
      </div>

      {/* 中：完成度一句話 */}
      <div className="text-xs text-cinema-muted font-medium tracking-wide">
        {statusSentence}
      </div>

      {/* 右：唯一實心主 CTA + ⋯ */}
      <div className="flex items-center space-x-3">
        {isPipelineRunning ? (
          <div className="flex items-center space-x-2">
            {cooldownRemaining > 0 ? (
              <CooldownRing
                remaining={cooldownRemaining}
                total={pipelineCooldownTotal || (cooldownRemaining > 8 ? 30 : 8)}
              />
            ) : (
              <div className="flex items-center text-xs text-amber-cta font-mono bg-cinema-card px-2.5 py-1 rounded border border-cinema-border max-w-[280px]">
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5 shrink-0" />
                <span className="truncate">{pipelineMessage || `處理中 ${pipelineProgress}%`}</span>
              </div>
            )}
            <button
              onClick={handleStopPipeline}
              className="flex items-center h-8 px-2.5 rounded bg-red-950/80 hover:bg-red-900 border border-red-800 text-xs text-red-200 transition-colors"
              title="中止當前任務"
            >
              <Square className="w-3 h-3 mr-1" />
              <span>停止</span>
            </button>
          </div>
        ) : (
          <button
            onClick={handlePrimaryAction}
            className="flex items-center h-8 px-4 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow-sm glow-amber active:scale-95"
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
        <div className="relative">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="p-1.5 rounded hover:bg-cinema-card text-cinema-muted hover:text-cinema-text transition-colors"
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
