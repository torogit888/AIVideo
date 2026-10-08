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
} from "lucide-react";
import { api } from "../api";
import { VertexAccount, CreateVertexAccountInput } from "../types";
import { useStudioStore } from "../store";

interface VertexAccountsPanelProps {
  onAccountChanged?: () => void;
}

export const VertexAccountsPanel: React.FC<VertexAccountsPanelProps> = ({ onAccountChanged }) => {
  const { showToast } = useStudioStore();
  const [accounts, setAccounts] = useState<VertexAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // 新增表單狀態
  const [formData, setFormData] = useState<CreateVertexAccountInput>({
    name: "",
    auth_type: "service_account",
    project_id: "",
    location: "us-central1",
    service_account_json: "",
    api_key: "",
  });
  const [activateImmediately, setActivateImmediately] = useState(true);
  const [jsonFileName, setJsonFileName] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const list = await api.getVertexAccounts();
      setAccounts(list);
    } catch (e: any) {
      showToast("載入 Vertex AI 帳戶失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  const handleSwitchAccount = async (account: VertexAccount) => {
    if (account.is_active) return;
    setSwitchingId(account.id);
    try {
      await api.activateVertexAccount(account.id);
      await loadAccounts();
      showToast(`已切換至帳戶【${account.name}】`, "success");
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
    const ok = window.confirm(`確定要刪除帳戶【${account.name}】嗎？`);
    if (!ok) return;

    setDeletingId(account.id);
    try {
      await api.deleteVertexAccount(account.id);
      await loadAccounts();
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
      await loadAccounts();
      setIsModalOpen(false);
      // 重置表單
      setFormData({
        name: "",
        auth_type: "service_account",
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
    <div className="p-5 rounded-lg bg-cinema-card border border-cinema-border space-y-4 text-xs">
      {/* 標題與動作 */}
      <div className="flex items-center justify-between border-b border-cinema-border/60 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-cinema-text flex items-center">
            <KeyRound className="w-4 h-4 text-amber-cta mr-2" />
            Vertex AI 憑證與帳戶管理
          </h3>
          <p className="text-xs text-cinema-muted mt-0.5">
            配置並切換多個 Google Cloud 專案、Service Account 金鑰或 API Key，免重啟即時生效。
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={loadAccounts}
            disabled={loading}
            className="p-1.5 rounded hover:bg-cinema-darker text-cinema-muted hover:text-amber-cta transition-colors"
            title="重新整理帳戶列表"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-amber-cta" : ""}`} />
          </button>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center h-8 px-3 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold transition-colors"
          >
            <Plus className="w-3.5 h-3.5 mr-1" />
            <span>新增帳戶 / 憑證</span>
          </button>
        </div>
      </div>

      {/* 帳戶卡片列表 */}
      <div className="space-y-2.5">
        {accounts.map((acc) => {
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
                        ? "Service Account"
                        : acc.auth_type === "api_key"
                        ? "API Key"
                        : "ADC 認證"}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-cinema-muted font-mono pt-0.5">
                    {acc.project_id && (
                      <span className="flex items-center">
                        <span className="text-zinc-500 mr-1">Project:</span>
                        <span className="text-cinema-text">{acc.project_id}</span>
                      </span>
                    )}
                    {acc.location && (
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
        })}
      </div>

      {/* 新增帳戶 Modal 彈窗 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-cinema-border/60">
              <div className="flex items-center space-x-2">
                <KeyRound className="w-4 h-4 text-amber-cta" />
                <h3 className="font-semibold text-sm text-cinema-text">新增 Vertex AI 憑證 / 帳戶</h3>
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
                  placeholder="例如：Google Cloud 主帳號、備用出圖專案 2"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full h-8 px-2.5 rounded-lg bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cinema-text mb-1">認證類型</label>
                <div className="grid grid-cols-2 gap-2">
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
                    <span>Service Account JSON</span>
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
                    <KeyRound className="w-3.5 h-3.5 mr-1.5" />
                    <span>AI Studio API Key</span>
                  </button>
                </div>
              </div>

              {formData.auth_type === "service_account" ? (
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
                  <div>
                    <label className="block text-xs font-medium text-cinema-text mb-1">
                      Gemini API Key <span className="text-red-400">*</span>
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
