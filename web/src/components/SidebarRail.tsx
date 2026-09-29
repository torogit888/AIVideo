import React, { useEffect, useState } from "react";
import {
  LayoutDashboard,
  FileText,
  Film,
  PlaySquare,
  Sparkles,
  Settings,
  ChevronLeft,
  ChevronRight,
  Video,
  Clapperboard,
  Copy,
  Check,
  RefreshCw,
} from "lucide-react";
import { useStudioStore } from "../store";
import { NavTab, AI_TEXT_MODELS, AI_IMAGE_MODELS } from "../types";
import { api } from "../api";

interface NavItem {
  key: NavTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { key: "overview", label: "總覽", icon: LayoutDashboard },
  { key: "script", label: "腳本", icon: FileText },
  { key: "storyboard", label: "分鏡", icon: Film },
  { key: "film", label: "成片", icon: PlaySquare },
  { key: "assets", label: "素材", icon: Sparkles },
  { key: "settings", label: "設定", icon: Settings },
];

export const SidebarRail: React.FC = () => {
  const {
    currentTab,
    setTab,
    isSidebarExpanded,
    toggleSidebar,
    selectedJobId,
    selectJob,
    loadJobs,
    jobs,
    scenes,
    showToast,
    selectedAiModel,
    setSelectedAiModel,
    selectedImageModel,
    setSelectedImageModel,
  } = useStudioStore();
  const [copied, setCopied] = useState(false);
  const [isServerOnline, setIsServerOnline] = useState<boolean | null>(null);

  const handleImageModelChange = async (newModel: string) => {
    setSelectedImageModel(newModel);
    const item = AI_IMAGE_MODELS.find((m) => m.id === newModel);
    if (selectedJobId) {
      try {
        await api.updateJob(selectedJobId, { image_model: newModel });
        await loadJobs();
        showToast(`已切換當前專案生圖模型為 ${item?.badge || newModel}`, "success");
      } catch {
        showToast(`已切換預設生圖模型為 ${item?.badge || newModel}`, "info");
      }
    } else {
      showToast(`已切換預設生圖模型為 ${item?.badge || newModel}`, "info");
    }
  };

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
  const total = scenes.length || currentJob?.progress.scenes_count || 0;
  const imgReady = scenes.filter((s) => s.status.has_image).length || currentJob?.progress.images_ready || 0;
  const audReady = scenes.filter((s) => s.status.has_audio).length || currentJob?.progress.audio_ready || 0;
  const filmReady = currentJob?.progress.film_ready ?? false;

  const handleCopyJobId = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!selectedJobId) return;
    navigator.clipboard.writeText(selectedJobId);
    setCopied(true);
    showToast("專案 ID 已複製到剪貼簿", "info");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <aside
      className={`relative flex flex-col justify-between border-r border-cinema-border bg-cinema-darker transition-all duration-200 select-none ${
        isSidebarExpanded ? "w-[220px]" : "w-[64px]"
      }`}
    >
      {/* 頂部 Logo 區塊 + 專案選擇器 */}
      <div>
        <div className="flex h-12 items-center px-4 border-b border-cinema-border/50">
          <div className="flex items-center space-x-2 text-amber-cta font-semibold">
            <Video className="w-5 h-5 flex-shrink-0" />
            {isSidebarExpanded && (
              <span className="text-sm tracking-wide text-cinema-text">
                AIVideo <span className="text-xs text-amber-cta font-mono">Studio</span>
              </span>
            )}
          </div>
        </div>

        {/* 專案選擇與重新整理 (展開與收合狀態適配) */}
        {isSidebarExpanded ? (
          <div className="p-2 border-b border-cinema-border/40">
            <div className="flex items-center space-x-1">
              <div className="relative flex-1 min-w-0">
                <select
                  value={selectedJobId || ""}
                  onChange={(e) => selectJob(e.target.value)}
                  className="w-full h-8 pl-2.5 pr-6 rounded-lg bg-cinema-card border border-cinema-border/70 hover:border-cinema-muted text-xs text-cinema-text focus:outline-none focus:border-amber-cta appearance-none cursor-pointer font-medium truncate"
                >
                  {jobs.length === 0 && <option value="">載入專案中...</option>}
                  {jobs.map((j) => {
                    const datePrefix = j.id.slice(0, 8);
                    const tag = j.progress.film_ready
                      ? "🟢已成片"
                      : j.progress.images_ready > 0
                      ? `🟡製作中(${j.progress.scenes_count}幕)`
                      : "⚪草稿";
                    return (
                      <option key={j.id} value={j.id}>
                        {j.title || j.id} [{datePrefix} · {tag}]
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
                  showToast("已重新掃描硬碟專案", "info");
                }}
                title="重新整理專案列表（掃描磁碟 jobs 目錄）"
                className="p-1.5 rounded-lg hover:bg-cinema-card text-cinema-muted hover:text-amber-cta transition-colors shrink-0"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="p-2 flex justify-center border-b border-cinema-border/40">
            <button
              onClick={() => {
                loadJobs();
                showToast("已重新掃描硬碟專案", "info");
              }}
              title={`目前專案：${currentJob?.title || selectedJobId || "無"}\n點擊重新掃描磁碟 jobs 目錄`}
              className="p-2 rounded-lg bg-cinema-card/50 hover:bg-cinema-card text-cinema-muted hover:text-amber-cta transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* 導航清單 */}
        <nav className="p-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                title={item.label}
                className={`relative flex items-center w-full h-10 px-3 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-cinema-card text-amber-cta"
                    : "text-cinema-muted hover:text-cinema-text hover:bg-cinema-card/50"
                } ${!isSidebarExpanded && "justify-center px-0"}`}
              >
                {/* 琥珀色 3px 指示條 */}
                {isActive && (
                  <div className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-amber-cta" />
                )}
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-amber-cta" : "text-cinema-muted"}`} />
                {isSidebarExpanded && <span className="ml-3 truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      {/* 底部收合控制與精緻專案縮影卡 */}
      <div className="p-2 border-t border-cinema-border/50">
        {/* 專案縮影卡片 */}
        {selectedJobId ? (
          isSidebarExpanded ? (
            <div
              onClick={() => setTab("overview")}
              title="點擊前往專案總覽"
              className="group relative p-2.5 mb-2 rounded-lg bg-cinema-card/50 hover:bg-cinema-card border border-cinema-border/60 hover:border-amber-cta/40 transition-all cursor-pointer"
            >
              <div className="flex items-start justify-between gap-1 mb-1">
                <div className="flex items-center min-w-0">
                  <Clapperboard className="w-3.5 h-3.5 mr-1.5 text-amber-cta shrink-0" />
                  <span className="text-xs font-semibold text-cinema-text truncate group-hover:text-amber-cta transition-colors">
                    {currentJob?.title || selectedJobId}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyJobId}
                  title="複製專案目錄 ID"
                  className="p-1 rounded text-cinema-muted/60 hover:text-amber-cta hover:bg-cinema-cardHover transition-colors shrink-0"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>

              {/* 專案 ID 微縮字 */}
              <div className="text-[10px] font-mono text-cinema-muted truncate mb-2">
                {selectedJobId}
              </div>

              {/* 迷你進度指示 */}
              <div className="flex items-center justify-between text-[10px] text-cinema-muted">
                <span className="flex items-center">
                  <span
                    className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                      filmReady
                        ? "bg-emerald-400 shadow-[0_0_4px_#34d399]"
                        : imgReady > 0 || audReady > 0
                        ? "bg-amber-cta"
                        : "bg-cinema-border"
                    }`}
                  />
                  <span>{filmReady ? "已成片" : total > 0 ? `製作中 ${imgReady}/${total}` : "空專案"}</span>
                </span>
                <span className="font-mono text-cinema-muted/80">{total > 0 ? `${total} 幕` : "-"}</span>
              </div>
            </div>
          ) : (
            <div
              onClick={() => setTab("overview")}
              title={`目前專案：${currentJob?.title || selectedJobId} (${filmReady ? "已成片" : "製作中"})`}
              className="relative flex items-center justify-center w-full h-10 mb-2 rounded-lg bg-cinema-card/40 hover:bg-cinema-card text-amber-cta hover:text-amber-ctaHover cursor-pointer transition-colors"
            >
              <Clapperboard className="w-4 h-4" />
              <span
                className={`absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full ${
                  filmReady ? "bg-emerald-400 shadow-[0_0_4px_#34d399]" : "bg-amber-cta"
                }`}
              />
            </div>
          )
        ) : null}

        {/* 左下角：全域 AI 核心文本模型切換器 */}
        {isSidebarExpanded ? (
          <div className="mb-1.5 px-1">
            <div
              className="flex items-center h-8 px-2.5 rounded-lg bg-cinema-card/70 hover:bg-cinema-card border border-cinema-border/70 text-xs transition-colors"
              title="切換核心文本大模型 (分鏡/腳本/提煉)"
            >
              <span className="text-[11px] mr-1.5 text-amber-cta">⚡</span>
              <select
                value={selectedAiModel}
                onChange={(e) => {
                  setSelectedAiModel(e.target.value);
                  const item = AI_TEXT_MODELS.find((m) => m.id === e.target.value);
                  if (item) showToast(`已切換核心 AI 模型為 ${item.name}`, "info");
                }}
                className="w-full bg-transparent text-cinema-text text-xs font-medium focus:outline-none appearance-none cursor-pointer pr-3 truncate"
              >
                {AI_TEXT_MODELS.map((m) => (
                  <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text py-1">
                    {m.badge} · {m.tag}
                  </option>
                ))}
              </select>
              <span className="text-[9px] text-cinema-muted -ml-2 pointer-events-none">▾</span>
            </div>
          </div>
        ) : (
          <div className="mb-1.5 flex justify-center">
            <div
              title={`核心文本模型：${AI_TEXT_MODELS.find((m) => m.id === selectedAiModel)?.name || selectedAiModel}`}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-cinema-card/60 text-amber-cta cursor-default border border-cinema-border/50"
            >
              <span className="text-xs">⚡</span>
            </div>
          </div>
        )}

        {/* 左下角：全域 AI 生圖模型切換器 */}
        {isSidebarExpanded ? (
          <div className="mb-2 px-1">
            <div
              className="flex items-center h-8 px-2.5 rounded-lg bg-cinema-card/70 hover:bg-cinema-card border border-cinema-border/70 text-xs transition-colors"
              title="切換 AI 生圖模型 (Google Gemini / Imagen)"
            >
              <span className="text-[11px] mr-1.5 text-purple-400">🎨</span>
              <select
                value={selectedImageModel}
                onChange={(e) => handleImageModelChange(e.target.value)}
                className="w-full bg-transparent text-cinema-text text-xs font-medium focus:outline-none appearance-none cursor-pointer pr-3 truncate"
              >
                {AI_IMAGE_MODELS.map((m) => (
                  <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text py-1">
                    {m.badge} · {m.tag}
                  </option>
                ))}
              </select>
              <span className="text-[9px] text-cinema-muted -ml-2 pointer-events-none">▾</span>
            </div>
          </div>
        ) : (
          <div className="mb-2 flex justify-center">
            <div
              title={`生圖模型：${AI_IMAGE_MODELS.find((m) => m.id === selectedImageModel)?.name || selectedImageModel}`}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-cinema-card/60 text-purple-400 cursor-default border border-cinema-border/50"
            >
              <span className="text-xs">🎨</span>
            </div>
          </div>
        )}

        {/* 左下角：API 在線狀態監控燈 */}
        {isSidebarExpanded ? (
          <div
            title={
              isServerOnline === true
                ? "後端 API 服務正常在線 (Port 8000)"
                : isServerOnline === false
                ? "後端 API 連線中斷 / 伺服器熱重載中"
                : "檢測後端連線中..."
            }
            className={`flex items-center justify-between h-7 px-2.5 mb-2 rounded-md text-[11px] font-mono border transition-all ${
              isServerOnline === true
                ? "bg-emerald-950/20 border-emerald-800/40 text-emerald-400"
                : isServerOnline === false
                ? "bg-red-950/40 border-red-800/80 text-red-300 animate-pulse"
                : "bg-cinema-card/50 border-cinema-border/50 text-cinema-muted"
            }`}
          >
            <span className="flex items-center">
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  isServerOnline === true
                    ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
                    : isServerOnline === false
                    ? "bg-red-400 shadow-[0_0_6px_#f87171]"
                    : "bg-cinema-muted"
                }`}
              />
              <span>API 8000</span>
            </span>
            <span className="text-[10px]">
              {isServerOnline === true ? "在線" : isServerOnline === false ? "斷線" : "連線中"}
            </span>
          </div>
        ) : (
          <div className="mb-2 flex justify-center">
            <div
              title={
                isServerOnline === true
                  ? "後端 API 正常在線 (Port 8000)"
                  : isServerOnline === false
                  ? "後端 API 連線中斷"
                  : "檢測中..."
              }
              className="w-8 h-7 flex items-center justify-center rounded-md bg-cinema-card/50 border border-cinema-border/50"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isServerOnline === true
                    ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
                    : isServerOnline === false
                    ? "bg-red-400 shadow-[0_0_6px_#f87171]"
                    : "bg-cinema-muted"
                }`}
              />
            </div>
          </div>
        )}

        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full h-8 rounded text-cinema-muted hover:text-cinema-text hover:bg-cinema-card transition-colors text-xs"
        >
          {isSidebarExpanded ? (
            <>
              <ChevronLeft className="w-4 h-4 mr-1" />
              <span>收合導航</span>
            </>
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
};
