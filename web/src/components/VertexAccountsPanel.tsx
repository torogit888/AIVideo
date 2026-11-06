import React, { useEffect, useState } from "react";
import {
  KeyRound,
  Plus,
  Loader2,
  Trash2,
  RefreshCw,
  Upload,
  Check,
  ShieldCheck,
  Globe,
  Radio,
  FileCode,
  Terminal,
  Sparkles,
  Cloud,
  ExternalLink,
} from "lucide-react";
import { api } from "../api";
import { VertexAccount, CreateVertexAccountInput } from "../types";
import { useStudioStore } from "../store";

interface VertexAccountsPanelProps {
  onAccountChanged?: () => void;
}

type ProviderTab = "vertex" | "aistudio";

export const VertexAccountsPanel: React.FC<VertexAccountsPanelProps> = ({ onAccountChanged }) => {
  const { showToast, requestConfirm } = useStudioStore();
  const [accounts, setAccounts] = useState<VertexAccount[]>([]);
  const [providerTab, setProviderTab] = useState<ProviderTab>("vertex");
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [syncingGcloud, setSyncingGcloud] = useState(false);

  // Google AI Studio 快速設定表單
  const [quickKeyName, setQuickKeyName] = useState("Google AI Studio 金鑰");
  const [quickApiKey, setQuickApiKey] = useState("");
  const [savingQuickKey, setSavingQuickKey] = useState(false);

  // 新增表單狀態
  const [formData, setFormData] = useState<CreateVertexAccountInput>({
    name: "",
    auth_type: "adc",
    project_id: "",
    location: "us-central1",
    service_account_json: "",
    api_key: "",
  });
  const [activateImmediately, setActivateImmediately] = useState(true);
  const [jsonFileName, setJsonFileName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadAccounts = async (syncTabWithActive = false) => {
    setLoading(true);
    try {
      const list = await api.getVertexAccounts();
      setAccounts(list);
      if (syncTabWithActive) {
        const active = list.find((a) => a.is_active);
        if (active) {
          setProviderTab(active.auth_type === "api_key" ? "aistudio" : "vertex");
        }
      }
      return list;
    } catch (e: any) {
      showToast("載入憑證帳戶失敗: " + (e.message || "未知錯誤"), "error");
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAccounts(true);
  }, []);

  const activeAccount = accounts.find((a) => a.is_active);
  const activeProvider: ProviderTab = activeAccount?.auth_type === "api_key" ? "aistudio" : "vertex";
  const vertexAccounts = accounts.filter((a) => a.auth_type !== "api_key");
  const aiStudioAccounts = accounts.filter((a) => a.auth_type === "api_key");
  const visibleAccounts = providerTab === "aistudio" ? aiStudioAccounts : vertexAccounts;

  const handleSelectProviderTab = async (tab: ProviderTab) => {
    setProviderTab(tab);
    // 若切換到的供應商已有儲存的帳戶且目前啟用的是另一邊，自動幫使用者切換過去
    if (tab === "aistudio" && activeProvider !== "aistudio" && aiStudioAccounts.length > 0) {
      await handleSwitchAccount(aiStudioAccounts[0]);
    } else if (tab === "vertex" && activeProvider !== "vertex" && vertexAccounts.length > 0) {
      await handleSwitchAccount(vertexAccounts[0]);
    }
  };

  const handleOpenAddModal = (targetTab: ProviderTab) => {
    setFormData({
      name: targetTab === "aistudio" ? "Google AI Studio 金鑰" : "",
      auth_type: targetTab === "aistudio" ? "api_key" : "adc",
      project_id: "",
      location: "us-central1",
      service_account_json: "",
      api_key: "",
    });
    setJsonFileName(null);
    setActivateImmediately(true);
    setIsModalOpen(true);
  };

  const handleQuickSaveAiStudioKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickApiKey.trim()) {
      showToast("請貼上 Google AI Studio 的 Gemini API Key！", "error");
      return;
    }
    setSavingQuickKey(true);
    try {
      const created = await api.createVertexAccount({
        name: quickKeyName.trim() || "Google AI Studio 金鑰",
        auth_type: "api_key",
        api_key: quickApiKey.trim(),
      });
      await api.activateVertexAccount(created.id);
      await loadAccounts(true);
      setQuickApiKey("");
      showToast(`已啟用 Google AI Studio【${created.name}】！`, "success");
      onAccountChanged?.();
    } catch (err: any) {
      showToast("儲存 API Key 失敗: " + (err.message || "未知錯誤"), "error");
    } finally {
      setSavingQuickKey(false);
    }
  };

  const handleSyncGcloud = async () => {
    setSyncingGcloud(true);
    try {
      const acc = await api.syncGcloudAccount();
      await loadAccounts(true);
      showToast(`已成功載入並切換至本機 gcloud 帳戶【${acc.name}】！`, "success");
      onAccountChanged?.();
    } catch (e: any) {
      showToast("載入本機 gcloud 憑證失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSyncingGcloud(false);
    }
  };

  const handleSwitchAccount = async (account: VertexAccount) => {
    if (account.is_active) return;
    setSwitchingId(account.id);
    try {
      await api.activateVertexAccount(account.id);
      await loadAccounts();
      showToast(
        `已切換至${account.auth_type === "api_key" ? " Google AI Studio" : " Vertex AI"}【${account.name}】`,
        "success"
      );
      onAccountChanged?.();
    } catch (e: any) {
      showToast("切換帳戶失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSwitchingId(null);
    }
  };

  const handleTestAccount = async (account: VertexAccount) => {
    setTestingId(account.id);
    try {
      const res = await api.testVertexAccount(account.id);
      if (res.status === "available") {
        showToast(`【${account.name}】連線驗證成功！延遲: ${res.latency_ms || "--"}ms`, "success");
      } else {
        showToast(`【${account.name}】測試未通過: ${res.message || "未知錯誤"}`, "error");
      }
      onAccountChanged?.();
    } catch (e: any) {
      showToast("連線測試失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setTestingId(null);
    }
  };

  const handleDeleteAccount = async (account: VertexAccount) => {
    if (account.is_active && accounts.length > 1) {
      showToast("無法刪除當前使用中的作用中帳戶，請先切換至其他帳戶再刪除", "error");
      return;
    }
    const ok = await requestConfirm({
      title: "刪除憑證帳戶",
      message: `確定要刪除帳戶【${account.name}】嗎？`,
      confirmText: "確定刪除",
      variant: "danger",
    });
    if (!ok) return;

    setDeletingId(account.id);
    try {
      await api.deleteVertexAccount(account.id);
      await loadAccounts(true);
      showToast(`已成功刪除帳戶【${account.name}】`, "success");
      onAccountChanged?.();
    } catch (e: any) {
      showToast("刪除帳戶失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setDeletingId(null);
    }
  };

  // 處理上傳 JSON 金鑰檔案
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = JSON.parse(text);
        setJsonFileName(file.name);
        setFormData((prev) => ({
          ...prev,
          service_account_json: text,
          project_id: parsed.project_id || prev.project_id,
          name: prev.name || (parsed.project_id ? `專案 (${parsed.project_id})` : file.name.replace(".json", "")),
        }));
        showToast("已成功載入 Service Account JSON 金鑰檔案！", "success");
      } catch {
        showToast("JSON 檔案格式無效，請確認為有效的 Google 憑證檔案", "error");
      }
    };
    reader.readAsText(file);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      showToast("請輸入帳戶名稱！", "error");
      return;
    }
    if (formData.auth_type === "service_account" && !formData.service_account_json?.trim() && !formData.project_id?.trim()) {
      showToast("請上傳或貼上 Service Account JSON 金鑰內容，或指定專案 ID！", "error");
      return;
    }
    if (formData.auth_type === "adc" && !formData.project_id?.trim()) {
      showToast("請輸入 Google Cloud Project ID！", "error");
      return;
    }
    if (formData.auth_type === "api_key" && !formData.api_key?.trim()) {
      showToast("請輸入 Google AI Studio API Key！", "error");
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await api.createVertexAccount(formData);
      if (activateImmediately) {
        await api.activateVertexAccount(created.id);
      }
      await loadAccounts(activateImmediately);
      setIsModalOpen(false);
      setFormData({
        name: "",
        auth_type: "adc",
        project_id: "",
        location: "us-central1",
        service_account_json: "",
        api_key: "",
      });
      setJsonFileName(null);
      showToast(activateImmediately ? `已新增並切換至【${created.name}】` : `已新增帳戶【${created.name}】`, "success");
      onAccountChanged?.();
    } catch (e: any) {
      showToast("新增帳戶失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-3.5 text-xs">
      {/* 標題與動作 */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-cinema-border/60 pb-2.5">
        <div className="flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-amber-cta" />
          <h3 className="text-sm font-semibold text-cinema-text">AI 服務供應商與憑證</h3>
          <span className="px-2 py-0.5 rounded-full bg-amber-cta/15 border border-amber-cta/40 text-[10px] text-amber-cta font-medium">
            目前模式：{activeProvider === "aistudio" ? "Google AI Studio" : "Vertex AI"}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => loadAccounts(false)}
            disabled={loading}
            className="p-1.5 rounded hover:bg-cinema-darker text-cinema-muted hover:text-amber-cta transition-colors"
            title="重新整理帳戶列表"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-amber-cta" : ""}`} />
          </button>
          {providerTab === "vertex" && (
            <button
              type="button"
              onClick={handleSyncGcloud}
              disabled={syncingGcloud || loading}
              className="flex items-center h-7 px-2.5 rounded-lg border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-cinema-text text-xs transition-colors"
              title="從本機 gcloud 自動載入憑證"
            >
              <Terminal className={`w-3.5 h-3.5 mr-1 text-amber-cta ${syncingGcloud ? "animate-spin" : ""}`} />
              <span>{syncingGcloud ? "載入中..." : "載入 gcloud 憑證"}</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => handleOpenAddModal(providerTab)}
            className="flex items-center h-7 px-2.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold transition-colors"
          >
            <Plus className="w-3.5 h-3.5 mr-1" />
            <span>{providerTab === "aistudio" ? "新增 AI Studio 金鑰" : "新增 Vertex AI 帳戶"}</span>
          </button>
        </div>
      </div>

      {/* 頂層供應商二選一切換器：Vertex AI vs Google AI Studio */}
      <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-cinema-darker border border-cinema-border">
        <button
          type="button"
          onClick={() => handleSelectProviderTab("vertex")}
          className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg border text-left transition-all ${
            providerTab === "vertex"
              ? "bg-amber-cta/15 border-amber-cta text-amber-cta shadow-sm"
              : "border-transparent text-cinema-muted hover:text-cinema-text hover:bg-cinema-card/50"
          }`}
        >
          <div className="flex items-center space-x-2.5">
            <Cloud className="w-4 h-4 shrink-0" />
            <div>
              <div className="font-semibold text-xs">Vertex AI (Google Cloud)</div>
              <div className="text-[10px] opacity-80">使用 GCP 專案、gcloud ADC 或 Service Account</div>
            </div>
          </div>
          {activeProvider === "vertex" && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-950/90 border border-emerald-700 text-[10px] text-emerald-400 font-mono shrink-0">
              啟用中
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => handleSelectProviderTab("aistudio")}
          className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg border text-left transition-all ${
            providerTab === "aistudio"
              ? "bg-amber-cta/15 border-amber-cta text-amber-cta shadow-sm"
              : "border-transparent text-cinema-muted hover:text-cinema-text hover:bg-cinema-card/50"
          }`}
        >
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-4 h-4 shrink-0" />
            <div>
              <div className="font-semibold text-xs">Google AI Studio</div>
              <div className="text-[10px] opacity-80">使用 AI Studio 的 GEMINI_API_KEY 金鑰直連</div>
            </div>
          </div>
          {activeProvider === "aistudio" && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-950/90 border border-emerald-700 text-[10px] text-emerald-400 font-mono shrink-0">
              啟用中
            </span>
          )}
        </button>
      </div>

      {/* Google AI Studio 快速輸入與切換區 */}
      {providerTab === "aistudio" && (
        <form
          onSubmit={handleQuickSaveAiStudioKey}
          className="p-3.5 rounded-lg bg-cinema-darker border border-cinema-border/80 space-y-2.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-cinema-text flex items-center">
              <Sparkles className="w-3.5 h-3.5 text-amber-cta mr-1.5" />
              快速設定並啟用 Google AI Studio 金鑰
            </span>
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noreferrer"
              className="flex items-center text-[11px] text-amber-cta hover:underline"
            >
              <span>前往 Google AI Studio 取得 API Key</span>
              <ExternalLink className="w-3 h-3 ml-1" />
            </a>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
            <input
              type="text"
              placeholder="金鑰備註名稱（例如：AI Studio 主金鑰）"
              value={quickKeyName}
              onChange={(e) => setQuickKeyName(e.target.value)}
              className="sm:col-span-4 h-8 px-2.5 rounded-lg bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
            <input
              type="password"
              placeholder="貼上 Gemini API Key (AIzaSy...)"
              value={quickApiKey}
              onChange={(e) => setQuickApiKey(e.target.value)}
              className="sm:col-span-5 h-8 px-2.5 rounded-lg bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
            />
            <button
              type="submit"
              disabled={savingQuickKey}
              className="sm:col-span-3 flex items-center justify-center h-8 px-3 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs transition-colors disabled:opacity-50"
            >
              {savingQuickKey ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                  <span>啟用中...</span>
                </>
              ) : (
                <span>儲存並啟用</span>
              )}
            </button>
          </div>
        </form>
      )}

      {/* 帳戶卡片列表 */}
      <div className="space-y-2.5">
        {visibleAccounts.length === 0 ? (
          <div className="p-4 rounded-lg bg-cinema-darker/60 border border-dashed border-cinema-border text-center text-cinema-muted">
            {providerTab === "aistudio"
              ? "目前尚無已儲存的 Google AI Studio 金鑰，請在上方貼上 API Key 並點擊「儲存並啟用」。"
              : "目前尚無已儲存的 Vertex AI 帳戶，請點擊右上角「載入 gcloud 憑證」或「新增 Vertex AI 帳戶」。"}
          </div>
        ) : (
          visibleAccounts.map((acc) => {
            const isActive = acc.is_active;
            const isTesting = testingId === acc.id;
            const isSwitching = switchingId === acc.id;
            const isDeleting = deletingId === acc.id;

            return (
              <div
                key={acc.id}
                className={`p-3.5 rounded-lg border transition-all ${
                  isActive
                    ? "bg-amber-cta/8 border-amber-cta/80 ring-1 ring-amber-cta/30"
                    : "bg-cinema-darker border-cinema-border/70 hover:border-cinema-muted"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-cinema-text truncate text-xs">
                        {acc.name}
                      </span>
                      {isActive ? (
                        <span className="flex items-center px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-[10px] text-emerald-400 font-medium">
                          <Check className="w-3 h-3 mr-0.5" /> 當前使用中
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cinema-card border border-cinema-border text-cinema-muted font-mono">
                          備用
                        </span>
                      )}
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cinema-card text-cinema-muted font-mono">
                        {acc.auth_type === "service_account"
                          ? "Vertex AI · Service Account"
                          : acc.auth_type === "api_key"
                          ? "Google AI Studio · API Key"
                          : "Vertex AI · ADC 認證"}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-cinema-muted font-mono pt-0.5">
                      {acc.project_id && (
                        <span className="flex items-center">
                          <span className="text-zinc-500 mr-1">Project:</span>
                          <span className="text-cinema-text">{acc.project_id}</span>
                        </span>
                      )}
                      {acc.location && acc.auth_type !== "api_key" && (
                        <span className="flex items-center">
                          <Globe className="w-3 h-3 mr-1 text-zinc-500" />
                          <span className="text-cinema-text">{acc.location}</span>
                        </span>
                      )}
                      {acc.client_email && (
                        <span className="flex items-center truncate max-w-[240px]" title={acc.client_email}>
                          <ShieldCheck className="w-3 h-3 mr-1 text-zinc-500" />
                          <span className="truncate">{acc.client_email}</span>
                        </span>
                      )}
                      {acc.api_key_masked && (
                        <span className="flex items-center">
                          <span className="text-zinc-500 mr-1">Key:</span>
                          <span>{acc.api_key_masked}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 動作按鈕列 */}
                  <div className="flex items-center space-x-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleTestAccount(acc)}
                      disabled={isTesting || isSwitching}
                      className="flex items-center h-7 px-2.5 rounded border border-cinema-border bg-cinema-card hover:bg-cinema-cardHover text-[11px] text-cinema-text hover:text-amber-cta transition-colors disabled:opacity-40"
                      title="發送輕量探針測試連線與授權"
                    >
                      {isTesting ? (
                        <>
                          <Loader2 className="w-3 h-3 mr-1 animate-spin text-amber-cta" />
                          <span>測試中...</span>
                        </>
                      ) : (
                        <>
                          <Radio className="w-3 h-3 mr-1 text-amber-cta" />
                          <span>測試連線</span>
                        </>
                      )}
                    </button>

                    {!isActive && (
                      <button
                        type="button"
                        onClick={() => handleSwitchAccount(acc)}
                        disabled={isSwitching || isTesting}
                        className="flex items-center h-7 px-2.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-[11px] transition-colors disabled:opacity-40"
                      >
                        {isSwitching ? (
                          <>
                            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                            <span>切換中...</span>
                          </>
                        ) : (
                          <span>切換使用</span>
                        )}
                      </button>
                    )}

                    {!isActive && accounts.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleDeleteAccount(acc)}
                        disabled={isDeleting}
                        className="p-1.5 rounded hover:bg-red-950/60 text-cinema-muted hover:text-red-400 transition-colors"
                        title="刪除此帳戶憑證"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-red-400" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 新增帳戶 Modal 彈窗 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-cinema-border/60">
              <div className="flex items-center space-x-2">
                <KeyRound className="w-4 h-4 text-amber-cta" />
                <h3 className="font-semibold text-sm text-cinema-text">
                  新增 AI 服務憑證（Vertex AI / Google AI Studio）
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-cinema-muted hover:text-cinema-text text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
              <div>
                <label className="block text-xs font-medium text-cinema-text mb-1">
                  帳戶自訂名稱 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="例如：Google AI Studio 主帳號、GCP 出圖專案"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cinema-text mb-1">選擇服務供應商與認證方式</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, auth_type: "adc" })}
                    className={`flex items-center justify-center p-2 rounded-lg border text-xs font-medium transition-colors ${
                      formData.auth_type === "adc"
                        ? "bg-amber-cta/15 border-amber-cta text-amber-cta"
                        : "bg-cinema-darker border-cinema-border text-cinema-muted hover:text-cinema-text"
                    }`}
                  >
                    <Terminal className="w-3.5 h-3.5 mr-1.5" />
                    <span>Vertex AI (ADC)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, auth_type: "service_account" })}
                    className={`flex items-center justify-center p-2 rounded-lg border text-xs font-medium transition-colors ${
                      formData.auth_type === "service_account"
                        ? "bg-amber-cta/15 border-amber-cta text-amber-cta"
                        : "bg-cinema-darker border-cinema-border text-cinema-muted hover:text-cinema-text"
                    }`}
                  >
                    <FileCode className="w-3.5 h-3.5 mr-1.5" />
                    <span>Vertex AI (JSON)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, auth_type: "api_key" })}
                    className={`flex items-center justify-center p-2 rounded-lg border text-xs font-medium transition-colors ${
                      formData.auth_type === "api_key"
                        ? "bg-amber-cta/15 border-amber-cta text-amber-cta"
                        : "bg-cinema-darker border-cinema-border text-cinema-muted hover:text-cinema-text"
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                    <span>Google AI Studio</span>
                  </button>
                </div>
              </div>

              {formData.auth_type === "adc" ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border/80 text-[11px] text-cinema-muted leading-relaxed space-y-1">
                    <p className="text-cinema-text font-medium flex items-center">
                      <Terminal className="w-3.5 h-3.5 mr-1 text-amber-cta" />
                      使用本機 gcloud 登入憑證 (ADC)
                    </p>
                    <p>
                      需已在本機終端機執行過 <code className="px-1 py-0.5 rounded bg-black/40 text-amber-cta font-mono">gcloud auth application-default login</code>，系統將自動調用本機授權，無需上傳任何 JSON 私鑰檔案。
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-cinema-text mb-1">
                        Google Cloud Project ID <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="例如：my-vertex-project-123"
                        value={formData.project_id || ""}
                        onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                        className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-cinema-text mb-1">預設地區 (Location)</label>
                      <select
                        value={formData.location || "us-central1"}
                        onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                        className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta cursor-pointer"
                      >
                        <option value="us-central1">us-central1 (愛荷華・推薦)</option>
                        <option value="global">global (全球全域・3系列首選)</option>
                        <option value="us-east4">us-east4 (北維吉尼亞)</option>
                        <option value="us-west1">us-west1 (奧勒岡)</option>
                        <option value="asia-east1">asia-east1 (台灣彰化)</option>
                      </select>
                    </div>
                  </div>
                </div>
              ) : formData.auth_type === "service_account" ? (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-cinema-text mb-1">
                      上傳金鑰 JSON 檔案或貼上內容
                    </label>
                    <div className="flex items-center space-x-2 mb-2">
                      <label className="flex items-center px-3 py-1.5 rounded-lg border border-cinema-border bg-cinema-darker hover:border-amber-cta cursor-pointer text-xs text-cinema-text transition-colors">
                        <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
                        <span>選擇本機 .json 金鑰檔案</span>
                        <input type="file" accept=".json" onChange={handleFileUpload} className="hidden" />
                      </label>
                      {jsonFileName && (
                        <span className="text-[11px] text-emerald-400 font-mono truncate max-w-[200px]">
                          已載入: {jsonFileName}
                        </span>
                      )}
                    </div>
                    <textarea
                      rows={5}
                      placeholder='可直接貼上包含 "private_key"、"client_email"、"project_id" 的 JSON 內容...'
                      value={formData.service_account_json || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFormData({ ...formData, service_account_json: val });
                        try {
                          const parsed = JSON.parse(val);
                          if (parsed.project_id && !formData.project_id) {
                            setFormData((prev) => ({ ...prev, project_id: parsed.project_id }));
                          }
                        } catch {}
                      }}
                      className="w-full p-2.5 rounded-lg bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 focus:outline-none focus:border-amber-cta leading-relaxed resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-cinema-text mb-1">Google Cloud Project ID</label>
                      <input
                        type="text"
                        placeholder="例如：my-vertex-project-123"
                        value={formData.project_id || ""}
                        onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                        className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-cinema-text mb-1">預設地區 (Location)</label>
                      <select
                        value={formData.location || "us-central1"}
                        onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                        className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta cursor-pointer"
                      >
                        <option value="us-central1">us-central1 (愛荷華・推薦)</option>
                        <option value="global">global (全球全域・3系列首選)</option>
                        <option value="us-east4">us-east4 (北維吉尼亞)</option>
                        <option value="us-west1">us-west1 (奧勒岡)</option>
                        <option value="asia-east1">asia-east1 (台灣彰化)</option>
                      </select>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border/80 text-[11px] text-cinema-muted leading-relaxed">
                    輸入從{" "}
                    <a
                      href="https://aistudio.google.com/apikey"
                      target="_blank"
                      rel="noreferrer"
                      className="text-amber-cta hover:underline"
                    >
                      Google AI Studio (aistudio.google.com)
                    </a>{" "}
                    取得的 API Key，儲存後系統將自動切換為 Google AI Studio 直連模式（<code className="text-amber-cta">GOOGLE_GENAI_USE_VERTEXAI=false</code>）。
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-cinema-text mb-1">
                      Google AI Studio API Key <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="password"
                      placeholder="AIzaSy..."
                      value={formData.api_key || ""}
                      onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                      className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
                    />
                  </div>
                </div>
              )}

              <div className="pt-2">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activateImmediately}
                    onChange={(e) => setActivateImmediately(e.target.checked)}
                    className="rounded bg-cinema-darker border-cinema-border text-amber-cta focus:ring-0"
                  />
                  <span className="text-xs text-cinema-text">儲存後立即啟用切換至此帳戶</span>
                </label>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-cinema-border/60">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-1.5 rounded-lg border border-cinema-border hover:bg-cinema-darker text-cinema-muted hover:text-cinema-text text-xs"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center px-4 py-1.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      <span>正在儲存...</span>
                    </>
                  ) : (
                    <span>確認儲存</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
