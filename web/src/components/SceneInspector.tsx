import React, { useEffect, useState } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Image as ImageIcon,
  Mic,
  Save,
  Loader2,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { SceneDetail } from "../types";

export const SceneInspector: React.FC = () => {
  const { activeSceneId, isInspectorOpen, closeInspector, selectedJobId, scenes, loadScenes } = useStudioStore();

  const [detail, setDetail] = useState<SceneDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // 表單內部暫存狀態
  const [narration, setNarration] = useState("");
  const [prompt, setPrompt] = useState("");
  const [pipEnabled, setPipEnabled] = useState(false);
  const [pipPos, setPipPos] = useState("top-right");

  // 載入當前鏡頭細節
  useEffect(() => {
    if (!selectedJobId || !activeSceneId || !isInspectorOpen) return;

    let mounted = true;
    setLoading(true);

    api
      .getSceneDetail(selectedJobId, activeSceneId)
      .then((data) => {
        if (!mounted) return;
        setDetail(data);
        setNarration(data.narration || "");
        setPrompt(data.image_prompt || "");
        setPipEnabled(data.pip?.enabled || false);
        setPipPos(data.pip?.position || "top-right");
      })
      .catch((e) => console.error("載入分鏡失敗", e))
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedJobId, activeSceneId, isInspectorOpen]);

  if (!isInspectorOpen || !activeSceneId) return null;

  // 計算上一幕 / 下一幕
  const currentIndex = scenes.findIndex((s) => s.id === activeSceneId);
  const prevScene = currentIndex > 0 ? scenes[currentIndex - 1] : null;
  const nextScene = currentIndex < scenes.length - 1 ? scenes[currentIndex + 1] : null;

  const handleSave = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    setSaving(true);
    try {
      await api.patchScene(selectedJobId, activeSceneId, {
        narration,
        image_prompt: prompt,
        pip: {
          ...detail.pip,
          enabled: pipEnabled,
          position: pipPos,
        },
      });
      // 靜默更新主網格資料
      await loadScenes(selectedJobId);
    } catch (e) {
      console.error("儲存失敗", e);
    } finally {
      setSaving(false);
    }
  };

  const handleRegenImage = async () => {
    if (!selectedJobId || !activeSceneId) return;
    await api.regenerateImage(selectedJobId, activeSceneId);
    alert("單幕出圖已觸發，完成後將自動刷新。");
  };

  const handleRegenAudio = async () => {
    if (!selectedJobId || !activeSceneId) return;
    await api.regenerateAudio(selectedJobId, activeSceneId);
    alert("單幕配音已觸發，完成後將自動刷新。");
  };

  return (
    <aside className="w-[380px] h-full flex flex-col border-l border-cinema-border bg-cinema-card z-20 shadow-2xl transition-all duration-200">
      {/* 頂部導航與關閉 */}
      <div className="flex h-12 items-center justify-between px-4 border-b border-cinema-border/60">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-cinema-text">
            第 {detail ? String(detail.index).padStart(2, "0") : "--"} / {String(scenes.length).padStart(2, "0")} 幕
          </span>
          <div className="flex items-center space-x-0.5 text-cinema-muted">
            <button
              disabled={!prevScene}
              onClick={() => prevScene && useStudioStore.getState().openInspector(prevScene.id)}
              className="p-1 rounded hover:bg-cinema-cardHover hover:text-cinema-text disabled:opacity-30"
              title="上一幕"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              disabled={!nextScene}
              onClick={() => nextScene && useStudioStore.getState().openInspector(nextScene.id)}
              className="p-1 rounded hover:bg-cinema-cardHover hover:text-cinema-text disabled:opacity-30"
              title="下一幕"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        <button
          onClick={closeInspector}
          className="p-1.5 rounded hover:bg-cinema-cardHover text-cinema-muted hover:text-cinema-text"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 內容區域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-cinema-muted text-xs">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            載入中...
          </div>
        ) : (
          <>
            {/* 1. 16:9 大預覽 */}
            <div className="relative aspect-video w-full rounded-md bg-black/60 overflow-hidden border border-cinema-border">
              {detail?.status.image_url ? (
                <img
                  src={detail.status.image_url}
                  alt={detail.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted/50">
                  <ImageIcon className="w-10 h-10 stroke-1 mb-1" />
                  <span className="text-xs">尚無影像</span>
                </div>
              )}
            </div>

            {/* 2. 重抽 / 換圖 / 重錄快速小按鈕列 */}
            <div className="flex items-center space-x-2">
              <button
                onClick={handleRegenImage}
                className="flex-1 flex items-center justify-center h-8 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text hover:text-amber-cta transition-colors"
              >
                <RotateCw className="w-3.5 h-3.5 mr-1" />
                <span>重抽畫面</span>
              </button>
              <button
                onClick={handleRegenAudio}
                className="flex-1 flex items-center justify-center h-8 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text hover:text-amber-cta transition-colors"
              >
                <Mic className="w-3.5 h-3.5 mr-1" />
                <span>重錄配音</span>
              </button>
            </div>

            {/* 3. 旁白解說 */}
            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <label className="font-medium text-cinema-text">旁白 / 口白</label>
                <span className="text-cinema-muted text-[11px] font-mono">{narration.length} 字</span>
              </div>
              <textarea
                value={narration}
                onChange={(e) => setNarration(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta leading-relaxed resize-none"
                placeholder="輸入本幕說書人口白..."
              />
            </div>

            {/* 4. 英文 Prompt */}
            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <label className="font-medium text-cinema-text">畫面提示詞 (English Prompt)</label>
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 focus:outline-none focus:border-amber-cta leading-relaxed resize-none"
                placeholder="Cinematic 16:9 composition prompt..."
              />
            </div>

            {/* 5. PiP 圖中圖設定 */}
            <div className="p-3 rounded bg-cinema-darker border border-cinema-border space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-cinema-text">PiP 圖中圖疊加</span>
                <input
                  type="checkbox"
                  checked={pipEnabled}
                  onChange={(e) => setPipEnabled(e.target.checked)}
                  className="rounded bg-cinema-card border-cinema-border text-amber-cta focus:ring-0 cursor-pointer"
                />
              </div>
              {pipEnabled && (
                <div className="pt-2 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-cinema-muted">疊加位置</span>
                    <select
                      value={pipPos}
                      onChange={(e) => setPipPos(e.target.value)}
                      className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px]"
                    >
                      <option value="top-right">右上角</option>
                      <option value="top-left">左上角</option>
                      <option value="bottom-right">右下角</option>
                      <option value="bottom-left">左下角</option>
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* 6. 儲存變更按鈕 */}
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow active:scale-98 disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>儲存中...</span>
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                  <span>儲存變更</span>
                </>
              )}
            </button>
          </>
        )}
      </div>
    </aside>
  );
};
