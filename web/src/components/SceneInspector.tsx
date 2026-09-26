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
  Volume2,
  Camera,
  CheckCircle2,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { SceneDetail, AssetVoice } from "../types";

export const SceneInspector: React.FC = () => {
  const {
    activeSceneId,
    isInspectorOpen,
    closeInspector,
    selectedJobId,
    scenes,
    loadScenes,
    jobs,
    loadJobs,
    showToast,
  } = useStudioStore();

  const [detail, setDetail] = useState<SceneDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isRegeneratingAudio, setIsRegeneratingAudio] = useState(false);
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [isFetchingPip, setIsFetchingPip] = useState(false);
  const [voices, setVoices] = useState<AssetVoice[]>([]);

  // 表單內部暫存狀態
  const [narration, setNarration] = useState("");
  const [prompt, setPrompt] = useState("");
  const [pipEnabled, setPipEnabled] = useState(false);
  const [pipPos, setPipPos] = useState("right-center");
  const [pipMode, setPipMode] = useState<"pip" | "spotlight">("pip");
  const [pipScale, setPipScale] = useState(0.24);

  const currentJob = jobs.find((j) => j.id === selectedJobId);
  const liveScene = scenes.find((s) => s.id === activeSceneId);
  const liveAudioUrl = liveScene?.status?.audio_url || "";
  const liveDuration = liveScene?.status?.duration ?? 0;

  // 載入可用音色庫
  useEffect(() => {
    api.getVoices().then(setVoices).catch(console.error);
  }, []);

  // 載入當前鏡頭細節（一鍵生成過程中語音就緒時會再抓一次）
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
        setPipPos(data.pip?.position || "right-center");
        setPipMode(data.pip?.mode || "pip");
        setPipScale(data.pip?.scale || 0.24);
      })
      .catch((e) => console.error("載入分鏡失敗", e))
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedJobId, activeSceneId, isInspectorOpen, liveAudioUrl, liveDuration]);

  if (!isInspectorOpen || !activeSceneId) return null;

  // 計算上一幕 / 下一幕
  const currentIndex = scenes.findIndex((s) => s.id === activeSceneId);
  const prevScene = currentIndex > 0 ? scenes[currentIndex - 1] : null;
  const nextScene = currentIndex < scenes.length - 1 ? scenes[currentIndex + 1] : null;

  const handleVoiceChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newVoice = e.target.value;
    if (!selectedJobId) return;
    try {
      await api.updateJob(selectedJobId, { voice_id: newVoice });
      await loadJobs();
      showToast("專案發音人已更新", "success");
    } catch (err: any) {
      showToast("更新發音人失敗: " + (err.message || "未知錯誤"), "error");
    }
  };

  const handleSave = async (showNotification = true) => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    setSaving(true);
    try {
      const updated = await api.patchScene(selectedJobId, activeSceneId, {
        narration,
        image_prompt: prompt,
        pip: {
          ...detail.pip,
          enabled: pipEnabled,
          position: pipPos,
          mode: pipMode,
          scale: pipScale,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);
      if (showNotification) {
        showToast("分鏡資料已儲存", "success");
      }
    } catch (e: any) {
      console.error("儲存失敗", e);
      if (showNotification) showToast("儲存失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenImage = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    setIsRegeneratingImage(true);
    try {
      // 1. 自動先儲存目前輸入框內容
      const updated = await api.patchScene(selectedJobId, activeSceneId, {
        narration,
        image_prompt: prompt,
        pip: {
          ...detail.pip,
          enabled: pipEnabled,
          position: pipPos,
          mode: pipMode,
          scale: pipScale,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);

      // 2. 觸發重抽畫面
      await api.regenerateImage(selectedJobId, activeSceneId);
      showToast(`第 ${detail.index} 幕已開始重新生圖...`, "info");

      // 3. 背景輪詢狀態（每 2 秒輪詢一次，最多 15 次）
      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
          if (fresh.status.has_image) {
            setDetail(fresh);
            await loadScenes(selectedJobId);
            setIsRegeneratingImage(false);
            showToast(`第 ${detail.index} 幕畫面更新完成！`, "success");
            clearInterval(timer);
          } else if (attempts >= 15) {
            setIsRegeneratingImage(false);
            clearInterval(timer);
          }
        } catch {
          if (attempts >= 15) {
            setIsRegeneratingImage(false);
            clearInterval(timer);
          }
        }
      }, 2000);
    } catch (e: any) {
      setIsRegeneratingImage(false);
      showToast("出圖啟動失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleRegenAudio = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    setIsRegeneratingAudio(true);
    try {
      // 1. 自動先儲存最新修改的口白與設定
      const updated = await api.patchScene(selectedJobId, activeSceneId, {
        narration,
        image_prompt: prompt,
        pip: {
          ...detail.pip,
          enabled: pipEnabled,
          position: pipPos,
          mode: pipMode,
          scale: pipScale,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);

      // 2. 觸發配音重錄
      await api.regenerateAudio(selectedJobId, activeSceneId);
      showToast(`第 ${detail.index} 幕已開始重錄配音...`, "info");

      // 3. 背景輪詢狀態（每 2 秒輪詢一次，最多 15 次）
      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
          if (fresh.status.has_audio) {
            setDetail(fresh);
            await loadScenes(selectedJobId);
            setIsRegeneratingAudio(false);
            showToast(`第 ${detail.index} 幕配音已更新完成！`, "success");
            clearInterval(timer);
          } else if (attempts >= 15) {
            setIsRegeneratingAudio(false);
            clearInterval(timer);
          }
        } catch {
          if (attempts >= 15) {
            setIsRegeneratingAudio(false);
            clearInterval(timer);
          }
        }
      }, 2000);
    } catch (e: any) {
      setIsRegeneratingAudio(false);
      showToast("配音重錄失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleFetchPip = async () => {
    if (!selectedJobId || !activeSceneId) return;
    setIsFetchingPip(true);
    try {
      await api.fetchScenePip(selectedJobId, activeSceneId);
      const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
      setDetail(fresh);
      setPipEnabled(fresh.pip?.enabled || false);
      await loadScenes(selectedJobId);
      showToast("考據照片已成功下載並套用！", "success");
    } catch (e: any) {
      showToast("下載考據照片失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsFetchingPip(false);
    }
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
                disabled={isRegeneratingImage || isRegeneratingAudio}
                className="flex-1 flex items-center justify-center h-8 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text hover:text-amber-cta transition-colors disabled:opacity-50"
              >
                {isRegeneratingImage ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1 text-amber-cta" />
                    <span>出圖中...</span>
                  </>
                ) : (
                  <>
                    <RotateCw className="w-3.5 h-3.5 mr-1" />
                    <span>重抽畫面</span>
                  </>
                )}
              </button>
              <button
                onClick={handleRegenAudio}
                disabled={isRegeneratingAudio || isRegeneratingImage}
                className="flex-1 flex items-center justify-center h-8 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text hover:text-amber-cta transition-colors disabled:opacity-50"
              >
                {isRegeneratingAudio ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1 text-amber-cta" />
                    <span>配音中...</span>
                  </>
                ) : (
                  <>
                    <Mic className="w-3.5 h-3.5 mr-1" />
                    <span>重錄配音</span>
                  </>
                )}
              </button>
            </div>

            {/* 2.2 專案發音人切換 */}
            <div className="p-2.5 rounded bg-cinema-darker border border-cinema-border space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-cinema-text flex items-center">
                  <Mic className="w-3.5 h-3.5 mr-1 text-amber-cta" />
                  <span>專案發音人</span>
                </span>
                <span className="text-[11px] text-cinema-muted">重錄或批次配音即套用</span>
              </div>
              <select
                value={currentJob?.voice_id || "female01"}
                onChange={handleVoiceChange}
                className="w-full h-8 px-2.5 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta cursor-pointer"
              >
                {voices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.gender})
                  </option>
                ))}
              </select>
            </div>

            {/* 2.5 語音試聽播放器 */}
            {detail?.status.has_audio && detail.status.audio_url && (
              <div className="p-2.5 rounded bg-cinema-darker border border-cinema-border space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-cinema-text flex items-center">
                    <Volume2 className="w-3.5 h-3.5 mr-1 text-amber-cta" />
                    <span>本幕配音試聽</span>
                  </span>
                  <span className="text-[11px] font-mono text-cinema-muted">
                    {detail.status.duration.toFixed(1)} 秒
                  </span>
                </div>
                <audio
                  controls
                  preload="auto"
                  src={detail.status.audio_url}
                  key={detail.status.audio_url}
                  className="w-full h-8"
                />
              </div>
            )}

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
            <div className="p-3 rounded bg-cinema-darker border border-cinema-border space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-1.5">
                  <Camera className="w-3.5 h-3.5 text-amber-cta" />
                  <span className="font-medium text-cinema-text">真實考據畫中畫 (PiP)</span>
                </div>
                <input
                  type="checkbox"
                  checked={pipEnabled}
                  onChange={(e) => setPipEnabled(e.target.checked)}
                  className="rounded bg-cinema-card border-cinema-border text-amber-cta focus:ring-0 cursor-pointer"
                />
              </div>

              {/* 顯示 AI 分析的檢索詞與圖片狀態 */}
              {detail?.pip?.query && (
                <div className="text-[11px] bg-cinema-card p-2 rounded border border-cinema-border/70 space-y-1.5">
                  <div className="text-cinema-muted flex items-center justify-between">
                    <span>AI 考據實體檢索詞:</span>
                    <div className="flex items-center space-x-1.5">
                      <span className="font-mono text-amber-cta text-[10px] font-semibold">{detail.pip.query}</span>
                      <button
                        onClick={handleFetchPip}
                        disabled={isFetchingPip}
                        className="px-1.5 py-0.5 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-cinema-border text-cinema-muted hover:text-amber-cta text-[10px] transition-colors"
                        title="立即向 NASA / 維基百科檢索下載照片"
                      >
                        {isFetchingPip ? "抓取中..." : "重新抓圖"}
                      </button>
                    </div>
                  </div>
                  {detail.status?.has_pip && detail.status?.pip_url && (
                    <div className="pt-1 border-t border-cinema-border/50 space-y-1">
                      <div className="text-[10px] text-emerald-400 flex items-center">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> 已下載真實考據照片:
                      </div>
                      <div className="relative max-w-[160px] max-h-[120px] p-0.5 rounded overflow-hidden border border-cinema-border bg-black flex items-center justify-center">
                        <img src={detail.status.pip_url} alt="PiP Preview" className="max-w-full max-h-[110px] object-contain rounded-sm" />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {pipEnabled && (
                <div className="pt-1 text-xs space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-cinema-muted">呈現方式</span>
                    <select
                      value={pipMode}
                      onChange={(e) => setPipMode(e.target.value as "pip" | "spotlight")}
                      className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px] font-medium"
                    >
                      <option value="pip">📌 畫中畫小卡 (PiP)</option>
                      <option value="spotlight">🏛️ 黑底歷史聚焦 (慢推浮現)</option>
                    </select>
                  </div>

                  {pipMode === "pip" ? (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-cinema-muted">卡片大小比例</span>
                        <select
                          value={pipScale}
                          onChange={(e) => setPipScale(parseFloat(e.target.value))}
                          className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px]"
                        >
                          <option value="0.20">精巧微縮 (20%)</option>
                          <option value="0.24">標準考據 (24%・推薦)</option>
                          <option value="0.30">清晰放大 (30%)</option>
                        </select>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-cinema-muted">疊加位置</span>
                        <select
                          value={pipPos}
                          onChange={(e) => setPipPos(e.target.value)}
                          className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px]"
                        >
                          <option value="right-center">右半部置中 (推薦)</option>
                          <option value="top-right">右上角</option>
                          <option value="top-left">左上角</option>
                          <option value="bottom-right">右下角</option>
                          <option value="bottom-left">左下角</option>
                          <option value="center">正中央</option>
                        </select>
                      </div>
                    </>
                  ) : (
                    <div className="text-[11px] text-amber-cta/90 bg-amber-500/10 p-2 rounded border border-amber-500/20 leading-relaxed">
                      🏛️ 本幕將以深邃黑底為背景，真實考據照片在中央緩慢推鏡淡入，營造紀錄片大片沉浸感。
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 6. 儲存變更按鈕 */}
            <button
              onClick={() => handleSave(true)}
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
