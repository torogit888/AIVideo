import React, { useEffect, useState, useRef } from "react";
import {
  X,
  Sparkles,
  RefreshCw,
  Upload,
  Trash2,
  Image as ImageIcon,
  Loader2,
  Info,
  Sliders,
  Plus,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { CharacterAnchor, JobVisualAnchors } from "../types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const VisualContinuityModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const { selectedJobId, loadJobs, loadScenes, showToast } = useStudioStore();

  const [anchors, setAnchors] = useState<JobVisualAnchors | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [syncingPrompts, setSyncingPrompts] = useState(false);

  const [environment, setEnvironment] = useState("");
  const [useImageRef, setUseImageRef] = useState(true);
  const [characters, setCharacters] = useState<CharacterAnchor[]>([]);

  const fileInputByChar = useRef<Record<string, HTMLInputElement | null>>({});

  const applyAnchors = (data: JobVisualAnchors) => {
    setAnchors(data);
    setEnvironment(data.environment || "");
    setUseImageRef(data.use_image_reference ?? true);
    setCharacters(data.characters?.length ? data.characters : []);
  };

  const fetchAnchors = async () => {
    if (!selectedJobId) return;
    setLoading(true);
    try {
      const data = await api.getJobAnchors(selectedJobId);
      applyAnchors(data);
    } catch (e: any) {
      console.error("載入錨點失敗", e);
      showToast("載入視覺錨點失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && selectedJobId) {
      fetchAnchors();
    }
  }, [isOpen, selectedJobId]);

  if (!isOpen) return null;

  const persistCharacters = () =>
    characters.map((c) => ({
      id: c.id,
      name: c.name.trim(),
      appearance: c.appearance.trim(),
    }));

  const handleSave = async (showSuccessToast = true) => {
    if (!selectedJobId) return;
    setSaving(true);
    try {
      const updated = await api.updateJobAnchors(selectedJobId, {
        environment: environment.trim(),
        use_image_reference: useImageRef,
        characters: persistCharacters(),
      });
      applyAnchors(updated);
      await loadJobs();
      if (showSuccessToast) {
        showToast("視覺錨點與參考圖設定已儲存！", "success");
      }
    } catch (e: any) {
      showToast("儲存失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateAll = async () => {
    if (!selectedJobId) return;
    setGeneratingAll(true);
    try {
      await api.updateJobAnchors(selectedJobId, {
        environment: environment.trim(),
        use_image_reference: useImageRef,
        characters: persistCharacters(),
      });
      const res = await api.generateHeroAnchor(selectedJobId);
      await fetchAnchors();
      await loadJobs();
      showToast(res.message || "已依專案風格為各角色生成定裝圖", "success");
    } catch (e: any) {
      showToast("生成定裝圖失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setGeneratingAll(false);
    }
  };

  const handleGenerateOne = async (charId: string) => {
    if (!selectedJobId) return;
    setGeneratingId(charId);
    try {
      await api.updateJobAnchors(selectedJobId, {
        environment: environment.trim(),
        use_image_reference: useImageRef,
        characters: persistCharacters(),
      });
      const updated = await api.generateCharacterHero(selectedJobId, charId);
      applyAnchors(updated);
      await loadJobs();
      showToast("已依專案風格生成此角色定裝圖", "success");
    } catch (e: any) {
      showToast("生成定裝圖失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setGeneratingId(null);
    }
  };

  const handleFileUpload = async (charId: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedJobId) return;
    setUploadingId(charId);
    try {
      const updated = await api.uploadCharacterHero(selectedJobId, charId, file);
      applyAnchors(updated);
      await loadJobs();
      showToast("角色定裝參考圖上傳成功", "success");
    } catch (err: any) {
      showToast("上傳失敗: " + (err.message || "未知錯誤"), "error");
    } finally {
      setUploadingId(null);
      e.target.value = "";
    }
  };

  const handleDeleteImage = async (charId: string) => {
    if (!selectedJobId) return;
    try {
      const updated = await api.deleteCharacterHero(selectedJobId, charId);
      applyAnchors(updated);
      await loadJobs();
      showToast("已移除此角色定裝圖", "info");
    } catch (e: any) {
      showToast("移除失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleAddCharacter = () => {
    setCharacters((prev) => [
      ...prev,
      { id: `char_${prev.length + 1}`, name: "", appearance: "", has_image: false },
    ]);
  };

  const handleRemoveCharacter = async (charId: string, index: number) => {
    if (!selectedJobId) return;
    const existing = anchors?.characters?.some((c) => c.id === charId);
    if (!existing) {
      setCharacters((prev) => prev.filter((_, i) => i !== index));
      return;
    }
    const ok = window.confirm("確定要移除此角色及其定裝圖嗎？");
    if (!ok) return;
    try {
      await api.updateJobAnchors(selectedJobId, {
        environment: environment.trim(),
        use_image_reference: useImageRef,
        characters: persistCharacters().filter((c) => c.id !== charId),
      });
      await fetchAnchors();
    } catch (e: any) {
      showToast("移除角色失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleSyncPrompts = async () => {
    if (!selectedJobId) return;
    const ok = window.confirm(
      "確定要依據最新角色定裝、環境錨點與專案生圖風格，重新產生全片所有分鏡的英文出圖 Prompt 嗎？"
    );
    if (!ok) return;

    setSyncingPrompts(true);
    try {
      await api.updateJobAnchors(selectedJobId, {
        environment: environment.trim(),
        use_image_reference: useImageRef,
        characters: persistCharacters(),
      });
      const res = await api.syncScenePrompts(selectedJobId);
      await loadScenes(selectedJobId);
      showToast(`🎉 ${res.message}`, "success");
    } catch (e: any) {
      showToast("重構 Prompt 失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSyncingPrompts(false);
    }
  };

  const busy = generatingAll || generatingId !== null || uploadingId !== null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl rounded-xl bg-cinema-darker border border-cinema-border shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-cinema-border/60 bg-cinema-card/50">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-amber-cta/15 text-amber-cta">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-cinema-text flex items-center gap-2">
                專案視覺一致性與角色定裝中心
                <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-cinema-border/50 text-cinema-muted">
                  Visual Continuity
                </span>
              </h3>
              <p className="text-xs text-cinema-muted mt-0.5">
                每位角色一張定裝圖，文字錨點與出圖 prompt 都會套用目前專案選擇的生圖風格。
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-cinema-muted hover:text-cinema-text hover:bg-cinema-card transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-cinema-muted">
              <Loader2 className="w-8 h-8 animate-spin text-amber-cta mb-2" />
              <span className="text-xs">正在讀取專案視覺特徵設定...</span>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-cinema-text flex items-center gap-1.5">
                    <Sliders className="w-4 h-4 text-amber-cta" />
                    環境與光影基調（全片共用）
                  </label>
                  <span className="text-[11px] text-cinema-muted">依專案生圖風格書寫</span>
                </div>
                <textarea
                  rows={3}
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  placeholder="此風格下的空間、色盤、光影與材質..."
                  className="w-full p-3 rounded-lg bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
                />
                <label className="flex items-start gap-2.5 cursor-pointer p-3 rounded-lg bg-cinema-card/70 border border-cinema-border/60">
                  <input
                    type="checkbox"
                    checked={useImageRef}
                    onChange={(e) => setUseImageRef(e.target.checked)}
                    className="mt-0.5 rounded border-cinema-border text-amber-cta focus:ring-amber-cta/30 bg-cinema-darker accent-amber-cta cursor-pointer"
                  />
                  <div className="flex-1">
                    <span className="text-xs font-medium text-cinema-text block">
                      出圖時將各角色定裝圖作為視覺參考 (Image Reference)
                    </span>
                    <p className="text-[11px] text-cinema-muted leading-relaxed mt-0.5">
                      啟用後，Gemini 會同時讀取每位已有定裝圖的角色，鎖定五官、服裝與配色。
                    </p>
                  </div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-cinema-text flex items-center gap-1.5">
                  <ImageIcon className="w-4 h-4 text-amber-cta" />
                  角色定裝圖（每人一張）
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleAddCharacter}
                    className="flex items-center px-2.5 py-1.5 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text text-[11px] border border-cinema-border"
                  >
                    <Plus className="w-3.5 h-3.5 mr-1" />
                    新增角色
                  </button>
                  <button
                    onClick={handleGenerateAll}
                    disabled={busy || characters.length === 0}
                    className="flex items-center px-3 py-1.5 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-[11px] disabled:opacity-50"
                  >
                    {generatingAll ? (
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    依風格生成全部定裝圖
                  </button>
                </div>
              </div>

              {characters.length === 0 && (
                <p className="text-xs text-cinema-muted">尚無角色。請先在腳本頁分析，或在此新增角色。</p>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {characters.map((ch, idx) => (
                  <div key={ch.id} className="rounded-lg border border-cinema-border bg-cinema-card/40 p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        value={ch.name}
                        onChange={(e) =>
                          setCharacters((prev) =>
                            prev.map((x, i) => (i === idx ? { ...x, name: e.target.value } : x))
                          )
                        }
                        className="flex-1 h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                        placeholder="角色名稱"
                      />
                      <button
                        onClick={() => handleRemoveCharacter(ch.id, idx)}
                        className="p-1.5 rounded text-cinema-muted hover:text-red-400"
                        title="移除此角色"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="relative aspect-video w-full rounded border border-cinema-border bg-black/60 overflow-hidden flex items-center justify-center">
                      {ch.has_image && ch.image_url ? (
                        <img src={ch.image_url} alt={ch.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="text-center text-cinema-muted/50 p-3">
                          <ImageIcon className="w-8 h-8 mx-auto stroke-1 mb-1" />
                          <p className="text-[11px]">尚未設定此角色定裝圖</p>
                        </div>
                      )}
                      {(generatingAll || generatingId === ch.id || uploadingId === ch.id) && (
                        <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center text-amber-cta text-[11px] space-y-1">
                          <Loader2 className="w-6 h-6 animate-spin" />
                          <span>{uploadingId === ch.id ? "上傳中..." : "依專案風格生成中..."}</span>
                        </div>
                      )}
                    </div>

                    <textarea
                      rows={3}
                      value={ch.appearance}
                      onChange={(e) =>
                        setCharacters((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, appearance: e.target.value } : x))
                        )
                      }
                      placeholder="此角色在目前生圖風格下的外觀..."
                      className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-[11px] text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
                    />

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleGenerateOne(ch.id)}
                        disabled={busy}
                        className="flex-1 flex items-center justify-center py-1.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-[11px] disabled:opacity-50"
                      >
                        <Sparkles className="w-3 h-3 mr-1" />
                        生成此張
                      </button>
                      <input
                        ref={(el) => {
                          fileInputByChar.current[ch.id] = el;
                        }}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                        onChange={(e) => handleFileUpload(ch.id, e)}
                      />
                      <button
                        onClick={() => fileInputByChar.current[ch.id]?.click()}
                        disabled={busy}
                        className="flex items-center justify-center px-2.5 py-1.5 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text text-[11px] border border-cinema-border disabled:opacity-50"
                      >
                        <Upload className="w-3 h-3 mr-1" />
                        上傳
                      </button>
                      {ch.has_image && (
                        <button
                          onClick={() => handleDeleteImage(ch.id)}
                          disabled={busy}
                          className="px-2 py-1.5 rounded bg-cinema-card hover:bg-red-950/60 text-cinema-muted hover:text-red-400 text-[11px] border border-cinema-border"
                        >
                          移除圖
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row gap-2 justify-end pt-2">
                <button
                  onClick={() => handleSave(true)}
                  disabled={saving}
                  className="px-4 py-2 rounded-lg bg-cinema-card hover:bg-cinema-cardHover text-cinema-text text-xs font-medium border border-cinema-border transition-colors disabled:opacity-50"
                >
                  {saving ? "儲存中..." : "💾 儲存錨點設定"}
                </button>
                <button
                  onClick={handleSyncPrompts}
                  disabled={syncingPrompts}
                  className="flex items-center justify-center px-4 py-2 rounded-lg bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-xs font-medium transition-colors disabled:opacity-50"
                >
                  {syncingPrompts ? (
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  )}
                  <span>🔄 依風格與錨點重產分鏡 Prompt</span>
                </button>
              </div>
            </>
          )}
        </div>

        <div className="px-6 py-3 border-t border-cinema-border/60 bg-cinema-card/30 flex items-center justify-between text-xs text-cinema-muted">
          <div className="flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-amber-cta" />
            <span>出圖時會把風格 prefix、角色定裝圖與文字錨點一起送進 Gemini。</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-cinema-card hover:bg-cinema-cardHover text-cinema-text text-xs border border-cinema-border transition-colors"
          >
            完成並關閉
          </button>
        </div>
      </div>
    </div>
  );
};
