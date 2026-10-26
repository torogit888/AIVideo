import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, Loader2 } from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { AI_IMAGE_MODELS, AI_TEXT_MODELS, ModelsStatusResponse } from "../types";
import { VertexAccountsPanel } from "./VertexAccountsPanel";
import { ConnectionLights } from "./ConnectionLights";

export const SettingsHealthPanel: React.FC = () => {
  const { refreshConnectionLights, showToast } = useStudioStore();
  const [checking, setChecking] = useState(false);
  const [defaults, setDefaults] = useState<{
    default_voice_id?: string;
    tones?: string[];
    font_path?: string | null;
    font_ok?: boolean;
  }>({});

  useEffect(() => {
    api
      .getSystemStatus()
      .then((st: any) =>
        setDefaults({
          default_voice_id: st.default_voice_id,
          tones: st.tones,
          font_path: st.font_path,
          font_ok: st.font_ok,
        })
      )
      .catch(() => undefined);
  }, []);

  const runCheck = async (target: string) => {
    setChecking(true);
    try {
      await api.checkConnections(target);
      await refreshConnectionLights();
      showToast(
        target === "gemini"
          ? "已檢測 Gemini 憑證"
          : target === "comfy"
          ? "已檢測 Comfy"
          : "已檢測連線",
        "success"
      );
    } catch (e: any) {
      showToast("檢測失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-cinema-text">連線與預設資產</h3>
        <ConnectionLights noPoll />
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("gemini")}
          className="h-8 px-3 rounded-lg border border-cinema-border bg-cinema-darker text-cinema-text hover:border-amber-cta/60 hover:text-amber-cta"
        >
          檢測 Gemini
        </button>
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("comfy")}
          className="h-8 px-3 rounded-lg border border-cinema-border bg-cinema-darker text-cinema-text hover:border-amber-cta/60 hover:text-amber-cta"
        >
          檢測 Comfy
        </button>
        <button
          type="button"
          disabled={checking}
          onClick={() => runCheck("all")}
          className="h-8 px-3 rounded-lg bg-amber-cta text-cinema-bg font-semibold hover:bg-amber-ctaHover"
        >
          全部檢測
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px]">
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">預設發音人</div>
          <div className="font-mono text-cinema-text">
            {defaults.default_voice_id || "tw_female01"}
          </div>
        </div>
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">口吻庫</div>
          <div className="text-cinema-text">{(defaults.tones || []).join("、") || "—"}</div>
        </div>
        <div className="p-3 rounded-md bg-cinema-darker border border-cinema-border/70">
          <div className="text-cinema-muted mb-1">字幕字型</div>
          <div
            className={`font-mono truncate ${
              defaults.font_ok ? "text-emerald-400" : "text-amber-400"
            }`}
            title={defaults.font_path || ""}
          >
            {defaults.font_ok ? defaults.font_path : "未找到檔案，ASS 用 Noto Sans CJK TC"}
          </div>
        </div>
      </div>
      <details className="pt-1">
        <summary className="cursor-pointer text-cinema-muted hover:text-cinema-text">
          開發端點
        </summary>
        <div className="space-y-1.5 text-cinema-muted mt-2">
          <div className="flex justify-between py-1 border-b border-cinema-border/40">
            <span>後端 API</span>
            <span className="text-cinema-text font-mono">http://localhost:8000</span>
          </div>
          <div className="flex justify-between py-1 border-b border-cinema-border/40">
            <span>靜態媒體</span>
            <span className="text-cinema-text font-mono">/media/jobs</span>
          </div>
          <div className="flex justify-between py-1">
            <span>ComfyUI</span>
            <span className="text-cinema-text font-mono">http://127.0.0.1:8188</span>
          </div>
        </div>
      </details>
    </div>
  );
};

export const SettingsPanel: React.FC = () => {
  const {
    selectedJobId,
    loadJobs,
    showToast,
    selectedAiModel,
    setSelectedAiModel,
    selectedImageModel,
    setSelectedImageModel,
  } = useStudioStore();

  const [modelsReport, setModelsReport] = useState<ModelsStatusResponse | null>(null);
  const [isCheckingModels, setIsCheckingModels] = useState(false);

  const fetchModelsStatus = useCallback(
    async (force = false) => {
      setIsCheckingModels(true);
      try {
        const res = force
          ? await api.checkModelsAvailability()
          : await api.getModelsStatus();
        setModelsReport(res);
        if (force) {
          showToast("已完成所有模型可用性與權限檢測！", "success");
        }
      } catch (e: any) {
        if (force) {
          showToast("模型可用性檢測失敗: " + (e.message || "未知錯誤"), "error");
        }
      } finally {
        setIsCheckingModels(false);
      }
    },
    [showToast]
  );

  useEffect(() => {
    if (!modelsReport) {
      fetchModelsStatus(false);
    }
  }, [modelsReport, fetchModelsStatus]);

  const renderModelStatusBadge = (modelId: string) => {
    if (isCheckingModels) {
      return (
        <span className="flex items-center text-[10px] text-amber-cta font-mono">
          <Loader2 className="w-2.5 h-2.5 animate-spin mr-1" />
          <span>檢測中</span>
        </span>
      );
    }
    const item = modelsReport?.models?.[modelId];
    if (!item) return null;

    if (item.status === "available") {
      return (
        <span
          className="flex items-center px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-[10px] text-emerald-400 font-mono"
          title={`狀態: ${item.message} ${item.latency_ms ? `(延遲 ${item.latency_ms}ms)` : ""}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse" />
          <span>可用 {item.latency_ms ? `${item.latency_ms}ms` : ""}</span>
        </span>
      );
    }
    if (item.status === "disabled") {
      return (
        <span
          className="flex items-center px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-800 text-[10px] text-amber-300 font-mono"
          title={item.message}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1" />
          <span>需啟用 API</span>
        </span>
      );
    }
    if (item.status === "quota_exceeded") {
      return (
        <span
          className="flex items-center px-1.5 py-0.5 rounded bg-red-950/80 border border-red-800 text-[10px] text-red-300 font-mono"
          title={item.message}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-red-400 mr-1" />
          <span>額度耗盡</span>
        </span>
      );
    }
    if (item.status === "permission_denied") {
      return (
        <span
          className="flex items-center px-1.5 py-0.5 rounded bg-red-950/80 border border-red-800 text-[10px] text-red-300 font-mono"
          title={item.message}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-red-400 mr-1" />
          <span>權限不足</span>
        </span>
      );
    }
    return (
      <span
        className="flex items-center px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono"
        title={item.message}
      >
        <span>未開放</span>
      </span>
    );
  };

  return (
    <div className="flex-1 p-8 space-y-6 max-w-3xl mx-auto overflow-y-auto">
      <div>
        <h2 className="text-xl font-bold text-cinema-text">Studio 設定</h2>
        <p className="text-xs text-cinema-muted mt-1">
          管理 Vertex AI 憑證帳戶、模型可用性授權、環境端點與渲染管線配置。
        </p>
      </div>

      {/* 1. Vertex AI 憑證與多帳號管理 */}
      <VertexAccountsPanel
        onAccountChanged={() => {
          fetchModelsStatus(true);
        }}
      />

      {/* 2. AI 文本大模型設定卡片 */}
      <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4">
        <div className="flex items-center justify-between border-b border-cinema-border/60 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-cinema-text flex items-center">
              <span className="text-amber-cta mr-2">⚡</span>
              Google Cloud Vertex AI 核心大模型
            </h3>
            <p className="text-xs text-cinema-muted mt-0.5">
              驅動故事發想長篇寫作、說書人口吻特徵萃取、AI 分鏡切鏡與英文電影提示詞生成。
            </p>
          </div>
          <button
            type="button"
            onClick={() => fetchModelsStatus(true)}
            disabled={isCheckingModels}
            className="flex items-center h-7 px-2.5 rounded-lg border border-amber-cta/40 bg-amber-cta/10 hover:bg-amber-cta/20 text-amber-cta text-[11px] font-medium transition-colors disabled:opacity-50 shrink-0"
            title="立即探測當前帳戶所有模型的可用性與配額狀態"
          >
            <RefreshCw className={`w-3 h-3 mr-1.5 ${isCheckingModels ? "animate-spin" : ""}`} />
            <span>{isCheckingModels ? "正在檢測中..." : "⚡ 檢測模型可用性"}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {AI_TEXT_MODELS.map((m) => {
            const isSelected = selectedAiModel === m.id;
            return (
              <div
                key={m.id}
                onClick={() => {
                  setSelectedAiModel(m.id);
                  showToast(`已切換全域核心 AI 模型為 ${m.name}`, "success");
                }}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  isSelected
                    ? "border-amber-cta bg-amber-cta/10 ring-1 ring-amber-cta/30"
                    : "border-cinema-border bg-cinema-darker/60 hover:border-cinema-muted"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`text-xs font-semibold ${
                      isSelected ? "text-amber-cta" : "text-cinema-text"
                    }`}
                  >
                    {m.name}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isSelected
                        ? "bg-amber-cta text-cinema-bg font-bold"
                        : "bg-cinema-card text-cinema-muted"
                    }`}
                  >
                    {m.badge}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-cinema-border/50">
                  <span className="text-[11px] text-cinema-muted truncate mr-1">{m.tag}</span>
                  <div className="shrink-0">{renderModelStatusBadge(m.id)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. 生圖模型設定卡片 */}
      <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4">
        <div className="flex items-center justify-between border-b border-cinema-border/60 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-cinema-text">生圖模型</h3>
            <p className="text-xs text-cinema-muted mt-0.5">
              分鏡出圖使用的 Gemini／Imagen 影像模型。
            </p>
          </div>
          {modelsReport?.checked_at && (
            <span className="text-[10px] text-cinema-muted font-mono">
              最近檢測: {modelsReport.checked_at}
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {AI_IMAGE_MODELS.map((m) => {
            const isSelected = selectedImageModel === m.id;
            return (
              <div
                key={m.id}
                onClick={async () => {
                  setSelectedImageModel(m.id);
                  if (selectedJobId) {
                    try {
                      await api.updateJob(selectedJobId, { image_model: m.id });
                      await loadJobs();
                    } catch {
                      /* 預設仍寫入本機 */
                    }
                  }
                  showToast(`已切換生圖模型為 ${m.name}`, "success");
                }}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  isSelected
                    ? "border-amber-cta bg-amber-cta/10 ring-1 ring-amber-cta/30"
                    : "border-cinema-border bg-cinema-darker/60 hover:border-cinema-muted"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`text-xs font-semibold ${
                      isSelected ? "text-amber-cta" : "text-cinema-text"
                    }`}
                  >
                    {m.name}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isSelected
                        ? "bg-amber-cta text-cinema-bg font-bold"
                        : "bg-cinema-card text-cinema-muted"
                    }`}
                  >
                    {m.badge}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-cinema-border/50">
                  <span className="text-[11px] text-cinema-muted truncate mr-1">{m.tag}</span>
                  <div className="shrink-0">{renderModelStatusBadge(m.id)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. 連線檢測與預設配置 */}
      <SettingsHealthPanel />
    </div>
  );
};
