import React from "react";
import {
  Camera,
  Check,
  CheckCircle2,
  Link as LinkIcon,
  Loader2,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { PipCandidateItem, SceneDetail } from "../types";

interface ScenePipSectionProps {
  detail: SceneDetail | null;
  narration: string;
  pipEnabled: boolean;
  pipMode: "pip" | "spotlight" | "broll";
  pipScale: number;
  pipPos: string;
  pipQuery: string;
  setPipQuery: (val: string) => void;
  pipSourceTab: "url" | "upload" | "search";
  setPipSourceTab: (tab: "url" | "upload" | "search") => void;
  customImageUrl: string;
  setCustomImageUrl: (val: string) => void;
  isApplyingUrl: boolean;
  isUploadingFile: boolean;
  isSearchingCandidates: boolean;
  isClearingPip: boolean;
  pipCandidates: PipCandidateItem[];
  applyingCandidateUrl: string | null;
  handleQuickUpdatePip: (
    nextEnabled: boolean,
    nextMode: "pip" | "spotlight" | "broll",
    customMsg?: string,
    overrides?: { scale?: number; position?: string }
  ) => Promise<void>;
  handleApplyPipUrl: (
    targetUrl: string,
    targetTitle?: string,
    mediaType?: string,
    force?: boolean
  ) => Promise<void>;
  handleUploadPipFile: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleSearchCandidates: () => Promise<void>;
  handleApplyCandidate: (cand: PipCandidateItem) => Promise<void>;
  handleClearPip: () => Promise<void>;
}

export const ScenePipSection: React.FC<ScenePipSectionProps> = ({
  detail,
  narration,
  pipEnabled,
  pipMode,
  pipScale,
  pipPos,
  pipQuery,
  setPipQuery,
  pipSourceTab,
  setPipSourceTab,
  customImageUrl,
  setCustomImageUrl,
  isApplyingUrl,
  isUploadingFile,
  isSearchingCandidates,
  isClearingPip,
  pipCandidates,
  applyingCandidateUrl,
  handleQuickUpdatePip,
  handleApplyPipUrl,
  handleUploadPipFile,
  handleSearchCandidates,
  handleApplyCandidate,
  handleClearPip,
}) => {
  return (
    <div className="p-3 rounded bg-cinema-darker border border-cinema-border space-y-2.5">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center space-x-1.5">
          <Camera className="w-3.5 h-3.5 text-amber-cta" />
          <span className="font-medium text-cinema-text">考據素材</span>
        </div>
        <label className="flex items-center space-x-1.5 cursor-pointer">
          <span className="text-[11px] text-cinema-muted">啟用</span>
          <input
            type="checkbox"
            checked={pipEnabled}
            onChange={(e) => handleQuickUpdatePip(e.target.checked, pipMode)}
            className="rounded bg-cinema-card border-cinema-border text-amber-cta focus:ring-0 cursor-pointer"
          />
        </label>
      </div>

      {/* 三大來源模式切換標籤 */}
      <div className="flex rounded-lg bg-cinema-card p-0.5 border border-cinema-border/70 text-[11px]">
        <button
          type="button"
          onClick={() => setPipSourceTab("url")}
          className={`flex-1 py-1 rounded flex items-center justify-center transition-colors ${
            pipSourceTab === "url"
              ? "bg-amber-cta text-cinema-bg font-semibold shadow"
              : "text-cinema-muted hover:text-cinema-text"
          }`}
        >
          <LinkIcon className="w-3 h-3 mr-1" />
          <span>貼網址</span>
        </button>
        <button
          type="button"
          onClick={() => setPipSourceTab("upload")}
          className={`flex-1 py-1 rounded flex items-center justify-center transition-colors ${
            pipSourceTab === "upload"
              ? "bg-amber-cta text-cinema-bg font-semibold shadow"
              : "text-cinema-muted hover:text-cinema-text"
          }`}
        >
          <Upload className="w-3 h-3 mr-1" />
          <span>本機上傳</span>
        </button>
        <button
          type="button"
          onClick={() => setPipSourceTab("search")}
          className={`flex-1 py-1 rounded flex items-center justify-center transition-colors ${
            pipSourceTab === "search"
              ? "bg-amber-cta text-cinema-bg font-semibold shadow"
              : "text-cinema-muted hover:text-cinema-text"
          }`}
        >
          <Search className="w-3 h-3 mr-1" />
          <span>全網搜尋</span>
        </button>
      </div>

      {/* 來源 1: 貼圖片網址 */}
      {pipSourceTab === "url" && (
        <div className="p-2 rounded bg-cinema-card border border-cinema-border/70 text-[11px]">
          <div className="flex space-x-1.5">
            <input
              type="url"
              placeholder="https://example.com/photo.jpg"
              value={customImageUrl}
              onChange={(e) => setCustomImageUrl(e.target.value)}
              className="flex-1 h-7 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
            />
            <button
              type="button"
              onClick={() => handleApplyPipUrl(customImageUrl)}
              disabled={isApplyingUrl || !customImageUrl.trim()}
              className="flex items-center px-2.5 h-7 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs transition-colors disabled:opacity-40 cursor-pointer"
            >
              {isApplyingUrl ? <Loader2 className="w-3 h-3 animate-spin" /> : <span>套用</span>}
            </button>
          </div>
        </div>
      )}

      {/* 來源 2: 本機照片上傳 */}
      {pipSourceTab === "upload" && (
        <div className="p-2.5 rounded bg-cinema-card border border-cinema-border/70 text-[11px] space-y-2">
          <label className="flex flex-col items-center justify-center p-3 rounded-lg border-2 border-dashed border-cinema-border hover:border-amber-cta cursor-pointer bg-cinema-darker transition-colors">
            {isUploadingFile ? (
              <Loader2 className="w-5 h-5 animate-spin text-amber-cta mb-1" />
            ) : (
              <Upload className="w-5 h-5 text-amber-cta mb-1" />
            )}
            <span className="text-cinema-text font-medium text-xs">
              {isUploadingFile ? "正在上傳..." : "選擇本機照片或影片"}
            </span>
            <input
              type="file"
              accept="image/*,video/*"
              onChange={handleUploadPipFile}
              disabled={isUploadingFile}
              className="hidden"
            />
          </label>
        </div>
      )}

      {/* 來源 3: 全網多候選檢索 */}
      {pipSourceTab === "search" && (
        <div className="p-2.5 rounded bg-cinema-card border border-cinema-border/70 space-y-2 text-[11px]">
          <div className="flex items-center justify-between text-cinema-muted">
            <span className="font-medium text-cinema-text">搜尋關鍵字</span>
            <button
              type="button"
              onClick={handleSearchCandidates}
              disabled={isSearchingCandidates || (!pipQuery.trim() && !narration.trim())}
              className="flex items-center px-2 py-0.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/30 text-[10px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
            >
              {isSearchingCandidates ? (
                <>
                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  <span>搜尋中...</span>
                </>
              ) : (
                <>
                  <Search className="w-3 h-3 mr-1" />
                  <span>搜尋</span>
                </>
              )}
            </button>
          </div>

          <input
            type="text"
            value={pipQuery}
            onChange={(e) => setPipQuery(e.target.value)}
            onBlur={async () => {
              const trimmed = pipQuery.trim();
              if (trimmed !== (detail?.pip?.query || "")) {
                await handleQuickUpdatePip(pipEnabled, pipMode, "已儲存考據檢索詞");
              }
            }}
            placeholder="輸入實體或場景關鍵字..."
            className="w-full h-7 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
          />

          {pipCandidates.length > 0 && (
            <div className="pt-2 border-t border-cinema-border/60 space-y-1.5">
              <div className="flex items-center justify-between text-[10px] text-cinema-muted">
                <span className="text-amber-cta font-medium">點選候選套用：</span>
                <span>{pipCandidates.length} 個</span>
              </div>
              <div className="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto pr-0.5">
                {pipCandidates.map((c, i) => (
                  <div
                    key={i}
                    onClick={() => handleApplyCandidate(c)}
                    className="relative group p-1 rounded bg-cinema-darker border border-cinema-border hover:border-amber-cta cursor-pointer transition-all flex flex-col items-center"
                  >
                    <div className="relative w-full h-16 rounded overflow-hidden bg-black flex items-center justify-center">
                      <img
                        src={c.thumbnail_url || c.url}
                        alt={c.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                      <span
                        className={`absolute top-1 left-1 px-1 py-0.2 rounded text-[8px] font-bold ${
                          c.media_type === "video"
                            ? "bg-emerald-500/95 text-black"
                            : "bg-purple-600/90 text-white"
                        }`}
                      >
                        {c.media_type === "video" ? "影片" : "照片"}
                      </span>
                      {applyingCandidateUrl === c.url && (
                        <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                          <Loader2 className="w-4 h-4 text-amber-cta animate-spin" />
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-cinema-muted truncate w-full mt-1 text-center" title={c.title}>
                      {c.title}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 目前已就緒之考據照片預覽卡片 */}
      {detail?.status?.has_pip && detail?.status?.pip_url && (
        <div className="p-2.5 rounded bg-cinema-card border border-cinema-border/70 space-y-1.5">
          <div className="text-[10px] text-emerald-400 flex items-center justify-between">
            <span className="flex items-center font-medium">
              <CheckCircle2 className="w-3 h-3 mr-1 shrink-0" /> 已配考據圖
            </span>
            <button
              onClick={handleClearPip}
              disabled={isClearingPip}
              className="flex items-center px-1.5 py-0.5 rounded bg-red-950/50 hover:bg-red-900/70 border border-red-800 text-[10px] text-red-300 transition-colors cursor-pointer disabled:opacity-40"
              title="清除考據圖檔"
            >
              {isClearingPip ? (
                <Loader2 className="w-2.5 h-2.5 animate-spin mr-0.5" />
              ) : (
                <Trash2 className="w-2.5 h-2.5 mr-0.5" />
              )}
              <span>清除</span>
            </button>
          </div>

          <div className="text-[10px] space-y-0.5 bg-cinema-darker/70 p-1.5 rounded border border-cinema-border/60 font-mono">
            <div className="flex items-center text-cinema-muted truncate">
              <span className="text-zinc-500 mr-1.5 shrink-0">關鍵字:</span>
              <span className="text-amber-cta/90 truncate font-semibold" title={detail.pip?.query || pipQuery}>
                {detail.pip?.query || pipQuery || "未指定"}
              </span>
            </div>
            {detail.pip?.source_title && (
              <div className="flex items-center text-cinema-muted truncate">
                <span className="text-zinc-500 mr-1.5 shrink-0">來源:</span>
                <span className="text-zinc-300 truncate" title={detail.pip.source_title}>
                  {detail.pip.source_title}
                </span>
              </div>
            )}
            {detail.pip?.verified && detail.pip?.review_reason && (
              <div className="flex items-center text-[10px] text-emerald-400 font-mono bg-emerald-950/40 p-1 rounded border border-emerald-800/50 mt-1">
                <Check className="w-3 h-3 mr-1 shrink-0" />
                <span className="truncate" title={detail.pip.review_reason}>
                  {detail.pip.review_reason}
                </span>
              </div>
            )}
          </div>

          <div
            className={`relative max-w-[170px] max-h-[120px] p-1 rounded overflow-hidden border ${
              pipMode === "spotlight" ? "border-cinema-border bg-black" : "border-white/80 bg-white shadow-md"
            } flex items-center justify-center mx-auto mt-1`}
          >
            <img
              src={detail.status.pip_url}
              alt="PiP Preview"
              className="max-w-full max-h-[110px] object-contain rounded-sm"
            />
          </div>
        </div>
      )}

      {/* 考據失敗原因與「抓到但被判定不符的考據候選」檢視區 */}
      {!detail?.status?.has_pip && detail?.pip?.fetch_error && (
        <div className="p-2.5 rounded bg-red-950/30 border border-red-800/50 text-[10px] text-red-200 space-y-2">
          <div className="flex items-center font-semibold text-red-300">
            <ShieldCheck className="w-3.5 h-3.5 mr-1 text-red-400 shrink-0" />
            <span>
              {(detail.pip.rejected_candidates && detail.pip.rejected_candidates.length > 0) ||
              detail.pip.fetch_error.includes("不符")
                ? "有抓到考據但 AI 判定與口白不符（已降級為 AI 畫面）"
                : "未抓到可用考據圖/影片（已降級為 AI 畫面）"}
            </span>
          </div>
          <div className="text-zinc-300 leading-relaxed font-mono text-[10px] bg-black/30 p-1.5 rounded border border-red-900/40">
            {detail.pip.fetch_error}
          </div>

          {detail.pip.rejected_candidates && detail.pip.rejected_candidates.length > 0 && (
            <div className="space-y-1.5 pt-1 border-t border-red-800/40">
              <div className="text-[10px] text-amber-300 font-medium">
                本次抓到的考據候選（共 {detail.pip.rejected_candidates.length} 筆，可點圖看原檔或強制套用）：
              </div>
              <div className="space-y-1.5 max-h-56 overflow-y-auto pr-0.5">
                {detail.pip.rejected_candidates.map((rej, idx) => {
                  const previewSrc =
                    (idx === 0 && detail.status?.pip_rejected_url) || rej.thumbnail_url || rej.url;
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 p-1.5 rounded bg-cinema-darker/90 border border-cinema-border/80"
                    >
                      {previewSrc && (
                        <a
                          href={rej.url}
                          target="_blank"
                          rel="noreferrer"
                          className="relative w-16 h-12 rounded overflow-hidden bg-black border border-cinema-border shrink-0"
                          title="點擊在新分頁開啟原始圖片或影片"
                        >
                          <img
                            src={previewSrc}
                            alt={rej.title}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                          <span className="absolute top-0.5 left-0.5 px-1 rounded bg-black/80 text-[8px] text-amber-300">
                            {rej.media_type === "video" ? "影片" : "照片"}
                          </span>
                        </a>
                      )}
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="flex items-center justify-between gap-1">
                          <a
                            href={rej.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[10px] text-cinema-text font-semibold hover:text-amber-cta truncate"
                            title={rej.title}
                          >
                            {rej.title}
                          </a>
                          <button
                            type="button"
                            disabled={isApplyingUrl}
                            onClick={() =>
                              handleApplyPipUrl(rej.url, rej.title, rej.media_type || "auto", true)
                            }
                            className="px-1.5 py-0.5 rounded bg-amber-cta/20 hover:bg-amber-cta hover:text-cinema-bg text-amber-300 border border-amber-cta/40 text-[9px] font-semibold shrink-0 transition-colors cursor-pointer disabled:opacity-40"
                            title="忽略 AI 退件原因，強制將此素材套用至本幕"
                          >
                            強制套用
                          </button>
                        </div>
                        {rej.source && (
                          <div className="text-[9px] text-zinc-400 truncate">來源：{rej.source}</div>
                        )}
                        <div className="text-[10px] text-red-300 leading-snug">
                          不符原因：{rej.reason || "與本幕口白描述主體不符"}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 呈現方式 */}
      <div className="pt-1 text-xs space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-cinema-muted">呈現方式</span>
          <select
            value={pipMode}
            onChange={(e) =>
              handleQuickUpdatePip(pipEnabled, e.target.value as "pip" | "spotlight" | "broll")
            }
            className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px] font-medium"
          >
            <option value="pip">角落小卡</option>
            <option value="spotlight">黑底全螢幕（照片）</option>
            <option value="broll">全螢幕影片</option>
          </select>
        </div>

        {pipEnabled && pipMode === "pip" && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-cinema-muted">卡片大小</span>
              <select
                value={pipScale}
                onChange={(e) => {
                  const nextScale = parseFloat(e.target.value);
                  handleQuickUpdatePip(pipEnabled, pipMode, "已更新考據卡片大小", {
                    scale: nextScale,
                  });
                }}
                className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px]"
              >
                <option value="0.20">小 (20%)</option>
                <option value="0.24">中 (24%)</option>
                <option value="0.30">大 (30%)</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-cinema-muted">疊加位置</span>
              <select
                value={pipPos}
                onChange={(e) => {
                  const nextPos = e.target.value;
                  handleQuickUpdatePip(pipEnabled, pipMode, "已更新考據疊加位置", {
                    position: nextPos,
                  });
                }}
                className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px]"
              >
                <option value="right-center">右半部置中</option>
                <option value="top-right">右上角</option>
                <option value="top-left">左上角</option>
                <option value="bottom-right">右下角</option>
                <option value="bottom-left">左下角</option>
                <option value="center">正中央</option>
              </select>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
