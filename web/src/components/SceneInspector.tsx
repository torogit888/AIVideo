import React, { useEffect, useState } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Image as ImageIcon,
  ImageOff,
  Mic,
  MicOff,
  Save,
  Loader2,
  Volume2,
  Camera,
  CheckCircle2,
  Search,
  Trash2,
  Lock,
  Unlock,
  Sparkles,
  RefreshCw,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { SceneDetail, SceneTake } from "../types";

export const SceneInspector: React.FC = () => {
  const {
    activeSceneId,
    isInspectorOpen,
    closeInspector,
    selectedJobId,
    scenes,
    loadScenes,
    loadJobs,
    showToast,
  } = useStudioStore();

  const [detail, setDetail] = useState<SceneDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isRegeneratingAudio, setIsRegeneratingAudio] = useState(false);
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [isClearingImage, setIsClearingImage] = useState(false);
  const [isClearingAudio, setIsClearingAudio] = useState(false);
  const [isClearingPip, setIsClearingPip] = useState(false);
  const [isFetchingPip, setIsFetchingPip] = useState(false);
  const [selectingTake, setSelectingTake] = useState<string | null>(null);
  const [gcing, setGcing] = useState(false);

  // 表單內部暫存狀態
  const [narration, setNarration] = useState("");
  const [prompt, setPrompt] = useState("");
  const [pipQuery, setPipQuery] = useState("");
  const [pipEnabled, setPipEnabled] = useState(false);
  const [pipPos, setPipPos] = useState("right-center");
  const [pipMode, setPipMode] = useState<"pip" | "spotlight">("pip");
  const [pipScale, setPipScale] = useState(0.24);
  const [isTranslatingPrompt, setIsTranslatingPrompt] = useState(false);

  const handleTranslatePrompt = async () => {
    if (!selectedJobId || !activeSceneId || !narration.trim()) {
      showToast("請先輸入本幕口白台詞！", "error");
      return;
    }
    setIsTranslatingPrompt(true);
    try {
      const res = await api.translateScenePrompt(selectedJobId, activeSceneId, narration.trim());
      setPrompt(res.image_prompt);
      await api.patchScene(selectedJobId, activeSceneId, {
        narration,
        image_prompt: res.image_prompt,
      });
      await loadScenes(selectedJobId);
      showToast("✨ 已依全域視覺風格重構為電影感出圖 Prompt！", "success");
    } catch (e: any) {
      showToast("重構 Prompt 失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsTranslatingPrompt(false);
    }
  };

  const liveScene = scenes.find((s) => s.id === activeSceneId);
  const liveAudioUrl = liveScene?.status?.audio_url || "";
  const liveDuration = liveScene?.status?.duration ?? 0;

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
        setPipQuery(data.pip?.query || "");
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

  const imageLocked = Boolean(detail?.locks?.image);
  const speechLocked = Boolean(detail?.locks?.speech);

  const handleToggleLock = async (kind: "image" | "speech") => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    const next = {
      image: kind === "image" ? !detail.locks?.image : Boolean(detail.locks?.image),
      speech: kind === "speech" ? !detail.locks?.speech : Boolean(detail.locks?.speech),
    };
    try {
      const fresh = await api.patchScene(selectedJobId, activeSceneId, { locks: next });
      setDetail(fresh);
      await loadScenes(selectedJobId);
      showToast(next[kind] ? `已鎖定${kind === "image" ? "畫面" : "配音"}` : `已解鎖${kind === "image" ? "畫面" : "配音"}`, "success");
    } catch (e: any) {
      showToast("鎖定失敗: " + (e.message || "未知錯誤"), "error");
    }
  };

  const handleGcTakes = async () => {
    if (!selectedJobId || !activeSceneId) return;
    const ok = window.confirm("清理本場過舊 takes，保留 current 與最新 3 個？");
    if (!ok) return;
    setGcing(true);
    try {
      const result = await api.gcSceneTakes(selectedJobId, activeSceneId, 3);
      const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
      setDetail(fresh);
      showToast(`已清理 ${result.removed} 個舊檔`, "success");
    } catch (e: any) {
      showToast("清理 takes 失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setGcing(false);
    }
  };

  const handleSelectTake = async (take: SceneTake) => {
    if (!selectedJobId || !activeSceneId) return;
    setSelectingTake(take.take_id);
    try {
      const fresh = await api.selectSceneTake(
        selectedJobId,
        activeSceneId,
        take.take_id,
        take.kind === "speech" ? "speech" : "image"
      );
      setDetail(fresh);
      await loadScenes(selectedJobId);
      showToast(`已設為 current：${take.take_id}`, "success");
    } catch (e: any) {
      showToast("設為 current 失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setSelectingTake(null);
    }
  };

  const handleQuickUpdatePip = async (
    nextEnabled: boolean,
    nextMode: "pip" | "spotlight",
    customMsg?: string
  ) => {
    setPipEnabled(nextEnabled);
    setPipMode(nextMode);
    if (!selectedJobId || !activeSceneId || !detail) return;
    try {
      const updated = await api.patchScene(selectedJobId, activeSceneId, {
        pip: {
          ...detail.pip,
          enabled: nextEnabled,
          mode: nextMode,
          position: pipPos,
          scale: pipScale,
          query: pipQuery.trim() || undefined,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);
      if (customMsg !== "") {
        showToast(customMsg || (nextEnabled ? "已啟用本幕考據" : "已取消本幕考據"), "info");
      }
    } catch (e: any) {
      showToast("更新考據狀態失敗: " + (e.message || "未知錯誤"), "error");
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
          query: pipQuery.trim() || undefined,
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
    if (detail.locks?.image) {
      showToast("畫面已鎖定，請先解鎖再重抽", "info");
      return;
    }
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
          query: pipQuery.trim() || undefined,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);

      // 記錄重抽前的 Take ID 與 URL
      const oldImageTake = detail.current?.image_take || "";
      const oldImageUrl = detail.status?.image_url || "";

      // 2. 觸發重抽畫面
      await api.regenerateImage(selectedJobId, activeSceneId);
      showToast(`第 ${detail.index} 幕已開始重新生圖...`, "info");

      // 3. 背景輪詢狀態（每 2 秒輪詢一次，最多 45 次 = 90 秒）
      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
          const hasNewTake = fresh.current?.image_take && fresh.current.image_take !== oldImageTake;
          const hasNewUrl = fresh.status?.image_url && fresh.status.image_url !== oldImageUrl;
          const isInitialImage = !oldImageTake && !oldImageUrl && fresh.status?.has_image && fresh.status?.image_url;

          if (hasNewTake || hasNewUrl || isInitialImage) {
            setDetail(fresh);
            await loadScenes(selectedJobId);
            setIsRegeneratingImage(false);
            showToast(`第 ${detail.index} 幕畫面更新完成！`, "success");
            clearInterval(timer);
          } else if (attempts >= 45) {
            setIsRegeneratingImage(false);
            showToast(`第 ${detail.index} 幕出圖耗時較長，請稍後檢視`, "info");
            clearInterval(timer);
          }
        } catch {
          if (attempts >= 45) {
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
    if (detail.locks?.speech) {
      showToast("配音已鎖定，請先解鎖再重錄", "info");
      return;
    }
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
          query: pipQuery.trim() || undefined,
        },
      });
      setDetail(updated);
      await loadScenes(selectedJobId);

      // 記錄重錄前的 Take ID 與 URL
      const oldAudioTake = detail.current?.speech_take || "";
      const oldAudioUrl = detail.status?.audio_url || "";

      // 2. 觸發配音重錄
      await api.regenerateAudio(selectedJobId, activeSceneId);
      showToast(`第 ${detail.index} 幕已開始重錄配音...`, "info");

      // 3. 背景輪詢狀態（每 2 秒輪詢一次，最多 35 次 = 70 秒）
      let attempts = 0;
      const timer = setInterval(async () => {
        attempts++;
        try {
          const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
          const hasNewTake = fresh.current?.speech_take && fresh.current.speech_take !== oldAudioTake;
          const hasNewUrl = fresh.status?.audio_url && fresh.status.audio_url !== oldAudioUrl;
          const isInitialAudio = !oldAudioTake && !oldAudioUrl && fresh.status?.has_audio && fresh.status?.audio_url;

          if (hasNewTake || hasNewUrl || isInitialAudio) {
            setDetail(fresh);
            await loadScenes(selectedJobId);
            setIsRegeneratingAudio(false);
            showToast(`第 ${detail.index} 幕配音已更新完成！`, "success");
            clearInterval(timer);
          } else if (attempts >= 35) {
            setIsRegeneratingAudio(false);
            showToast(`第 ${detail.index} 幕配音重錄耗時較長，請稍後檢視`, "info");
            clearInterval(timer);
          }
        } catch {
          if (attempts >= 35) {
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
    if (!pipQuery.trim()) {
      showToast("請先輸入考據實體檢索詞！", "error");
      return;
    }
    setIsFetchingPip(true);
    try {
      await api.fetchScenePip(selectedJobId, activeSceneId, pipQuery.trim());
      const fresh = await api.getSceneDetail(selectedJobId, activeSceneId);
      setDetail(fresh);
      setPipEnabled(fresh.pip?.enabled || false);
      await loadScenes(selectedJobId);
      showToast(`已成功依【${pipQuery.trim()}】檢索並套用真實考據照片！`, "success");
    } catch (e: any) {
      showToast("下載考據照片失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsFetchingPip(false);
    }
  };

  const handleClearImage = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    const ok = window.confirm(
      `確定要清空第 ${detail.index} 幕已生成的圖片嗎？\n\n清空後此幕將回到初始「待出圖」狀態，口白台詞與語音將完整保留。`
    );
    if (!ok) return;

    setIsClearingImage(true);
    try {
      const fresh = await api.clearSceneImage(selectedJobId, activeSceneId);
      setDetail(fresh);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast(`第 ${detail.index} 幕圖片已清空，回到待出圖狀態`, "success");
    } catch (e: any) {
      showToast("清空圖片失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsClearingImage(false);
    }
  };

  const handleClearAudio = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    const ok = window.confirm(
      `確定要清空第 ${detail.index} 幕已生成的語音嗎？\n\n清空後此幕將回到初始「待配音」狀態，畫面圖片與口白台詞將完整保留。`
    );
    if (!ok) return;

    setIsClearingAudio(true);
    try {
      const fresh = await api.clearSceneAudio(selectedJobId, activeSceneId);
      setDetail(fresh);
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast(`第 ${detail.index} 幕語音已清空，回到待配音狀態`, "success");
    } catch (e: any) {
      showToast("清空語音失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsClearingAudio(false);
    }
  };

  const handleClearPip = async () => {
    if (!selectedJobId || !activeSceneId || !detail) return;
    const ok = window.confirm(
      `確定要清除第 ${detail.index} 幕的真實考據照片 (pip.png) 嗎？\n\n清除後此幕將不再疊加或聚焦該考據圖，完全以 AI 生圖為主畫面。`
    );
    if (!ok) return;

    setIsClearingPip(true);
    try {
      const fresh = await api.clearScenePip(selectedJobId, activeSceneId);
      setDetail(fresh);
      setPipEnabled(false);
      setPipMode("pip");
      await loadScenes(selectedJobId);
      await loadJobs();
      showToast(`第 ${detail.index} 幕考據照片已成功清除`, "success");
    } catch (e: any) {
      showToast("清除考據圖失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsClearingPip(false);
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
            <div className="relative aspect-video w-full rounded-md bg-black overflow-hidden border border-cinema-border flex items-center justify-center">
              {/* 重繪畫面中的浮層 Loading 指示 */}
              {isRegeneratingImage && (
                <div className="absolute inset-0 bg-black/70 backdrop-blur-[2px] flex flex-col items-center justify-center z-20 text-amber-cta animate-in fade-in duration-200">
                  <Loader2 className="w-8 h-8 animate-spin mb-2" />
                  <span className="text-xs font-semibold tracking-wide">AI 正在重新繪製畫面...</span>
                  <span className="text-[10px] text-cinema-muted mt-0.5">完成後將立即自動更新預覽</span>
                </div>
              )}

              {pipMode === "spotlight" && pipEnabled && detail?.status?.has_pip && detail?.status?.pip_url ? (
                <div className="relative w-full h-full bg-black flex items-center justify-center">
                  <img
                    key={detail.status.pip_url}
                    src={detail.status.pip_url}
                    alt="Spotlight Archival"
                    className="max-h-[85%] max-w-[85%] object-contain rounded border border-white/80 shadow-2xl"
                  />
                  <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-amber-500/90 text-black font-semibold text-[10px] z-10 shadow">
                    🏛️ 黑底歷史聚焦原照
                  </div>
                </div>
              ) : detail?.status.image_url ? (
                <div className="relative w-full h-full bg-cinema-darker overflow-hidden">
                  <img
                    key={detail.status.image_url}
                    src={detail.status.image_url}
                    alt={detail.title}
                    className="w-full h-full object-cover"
                  />
                  {pipEnabled && pipMode === "pip" && detail?.status?.has_pip && detail?.status?.pip_url && (
                    <div className="absolute top-1/2 -translate-y-1/2 right-2 max-w-[30%] max-h-[75%] rounded-[6px] border-[2px] border-white/95 bg-white p-1 overflow-hidden shadow-2xl z-10 flex items-center justify-center">
                      <img src={detail.status.pip_url} alt="PiP Preview" className="max-h-[110px] max-w-full object-contain rounded-sm" />
                    </div>
                  )}
                </div>
              ) : pipMode === "spotlight" && pipEnabled ? (
                <div className="flex flex-col items-center justify-center w-full h-full bg-black text-amber-cta/90 p-4 text-center select-none">
                  <Camera className="w-10 h-10 stroke-1 mb-2 text-amber-cta" />
                  <span className="text-sm font-semibold text-amber-cta">🏛️ 待檢索黑底歷史考據原照</span>
                  <span className="text-xs text-cinema-muted mt-1 max-w-[280px]">
                    一鍵生成時將優先下載真實歷史照片慢推，自動跳過 AI 生圖
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted/50">
                  <ImageIcon className="w-10 h-10 stroke-1 mb-1" />
                  <span className="text-xs">尚無影像</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleToggleLock("image")}
                className={`flex-1 h-8 px-2 rounded-lg border text-[11px] flex items-center justify-center ${
                  imageLocked
                    ? "border-amber-cta/70 bg-amber-cta/10 text-amber-cta"
                    : "border-cinema-border bg-cinema-darker text-cinema-muted hover:text-cinema-text"
                }`}
              >
                {imageLocked ? <Lock className="w-3 h-3 mr-1" /> : <Unlock className="w-3 h-3 mr-1" />}
                {imageLocked ? "畫面已鎖" : "鎖畫面"}
              </button>
              <button
                type="button"
                onClick={() => handleToggleLock("speech")}
                className={`flex-1 h-8 px-2 rounded-lg border text-[11px] flex items-center justify-center ${
                  speechLocked
                    ? "border-amber-cta/70 bg-amber-cta/10 text-amber-cta"
                    : "border-cinema-border bg-cinema-darker text-cinema-muted hover:text-cinema-text"
                }`}
              >
                {speechLocked ? <Lock className="w-3 h-3 mr-1" /> : <Unlock className="w-3 h-3 mr-1" />}
                {speechLocked ? "配音已鎖" : "鎖配音"}
              </button>
            </div>

            {/* 2. 重抽 / 換圖 / 重錄快速小按鈕列 */}
            <div className="flex items-center space-x-2">
              {pipMode === "spotlight" && pipEnabled && detail?.status?.has_pip ? (
                <div
                  className="flex-1 flex items-center justify-center h-8 rounded bg-amber-cta/10 border border-amber-cta/30 text-xs text-amber-cta select-none"
                  title="此幕成片直接採用真實歷史照片慢推，已自動跳過 AI 生圖"
                >
                  <span>🏛️ 黑底考據（已免除生圖）</span>
                </div>
              ) : (
                <button
                  onClick={handleRegenImage}
                  disabled={isRegeneratingImage || isRegeneratingAudio || imageLocked}
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
              )}
              {detail?.status?.has_image && (
                <button
                  onClick={handleClearImage}
                  disabled={isRegeneratingImage || isRegeneratingAudio || isClearingImage}
                  className="flex items-center justify-center h-8 px-2.5 rounded bg-cinema-darker hover:bg-red-950/40 border border-cinema-border hover:border-red-900/60 text-xs text-cinema-muted hover:text-red-400 transition-colors disabled:opacity-50 shrink-0"
                  title="清空此幕已生成的圖片，重置為待出圖狀態"
                >
                  {isClearingImage ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-red-400" />
                  ) : (
                    <ImageOff className="w-3.5 h-3.5" />
                  )}
                </button>
              )}
              <button
                onClick={handleRegenAudio}
                disabled={isRegeneratingAudio || isRegeneratingImage || isClearingAudio || speechLocked}
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
              {detail?.status.has_audio && (
                <button
                  type="button"
                  onClick={handleClearAudio}
                  disabled={isClearingAudio || isRegeneratingAudio}
                  className="flex items-center justify-center h-8 px-2.5 rounded bg-cinema-darker hover:bg-sky-950/40 border border-cinema-border hover:border-sky-900/60 text-xs text-cinema-muted hover:text-sky-400 transition-colors disabled:opacity-50"
                  title="清空本幕已生成的配音，回到待配音狀態"
                >
                  {isClearingAudio ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400" />
                  ) : (
                    <MicOff className="w-3.5 h-3.5" />
                  )}
                </button>
              )}
            </div>

            {/* 歷史 takes */}
            {(detail?.takes?.images?.length || detail?.takes?.speeches?.length) ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] text-cinema-muted">
                    本場 {detail.takes.images.length} 張圖 · {detail.takes.speeches.length} 段聲
                  </div>
                  <button
                    type="button"
                    onClick={handleGcTakes}
                    disabled={gcing}
                    className="h-7 px-2 rounded text-[10px] text-cinema-muted hover:text-amber-cta border border-cinema-border"
                  >
                    {gcing ? "清理中..." : "gc 舊 takes"}
                  </button>
                </div>
                {detail.takes.images.length > 0 && (
                  <div>
                    <div className="text-[11px] font-medium text-cinema-muted mb-1.5">畫面 takes</div>
                    <div className="flex gap-1.5 overflow-x-auto pb-1">
                      {detail.takes.images.map((t) => (
                        <button
                          key={t.take_id}
                          onClick={() => handleSelectTake(t)}
                          disabled={selectingTake === t.take_id}
                          title={`設為 current：${t.take_id}`}
                          className={`relative w-20 h-12 shrink-0 rounded overflow-hidden border ${
                            t.is_current ? "border-amber-cta ring-1 ring-amber-cta/40" : "border-cinema-border"
                          }`}
                        >
                          {t.url ? (
                            <img src={t.url} alt={t.take_id} className="w-full h-full object-cover" />
                          ) : (
                            <span className="text-[9px]">{t.take_id}</span>
                          )}
                          {t.is_current && (
                            <span className="absolute bottom-0 inset-x-0 bg-black/70 text-[8px] text-amber-cta text-center">
                              current
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {detail.takes.speeches.length > 0 && (
                  <div>
                    <div className="text-[11px] font-medium text-cinema-muted mb-1.5">配音 takes</div>
                    <div className="space-y-1">
                      {detail.takes.speeches.map((t) => (
                        <button
                          key={t.take_id}
                          onClick={() => handleSelectTake(t)}
                          disabled={selectingTake === t.take_id}
                          className={`w-full flex items-center justify-between h-7 px-2 rounded text-[10px] font-mono border ${
                            t.is_current
                              ? "border-amber-cta text-amber-cta bg-amber-cta/10"
                              : "border-cinema-border text-cinema-muted hover:text-cinema-text"
                          }`}
                        >
                          <span className="truncate">{t.take_id}</span>
                          <span>{t.is_current ? "current" : "設為 current"}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}

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
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <label className="font-medium text-cinema-text flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-cta" />
                  <span>畫面提示詞 (English Prompt)</span>
                </label>
                <button
                  type="button"
                  onClick={handleTranslatePrompt}
                  disabled={isTranslatingPrompt || !narration.trim()}
                  className="flex items-center h-6 px-2.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/30 text-[10px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
                  title="由 AI 依據上方口白與專案全域視覺風格，重新轉譯生成最適出圖 Prompt"
                >
                  {isTranslatingPrompt ? (
                    <>
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                      <span>轉譯中...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-2.5 h-2.5 mr-1" />
                      <span>重構 Prompt</span>
                    </>
                  )}
                </button>
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 focus:outline-none focus:border-amber-cta leading-relaxed resize-none"
                placeholder="Cinematic 16:9 composition prompt..."
              />
              <div className="text-[10px] text-cinema-muted/80 flex items-center justify-between">
                <span>出圖時將自動拼接所選風格前綴並過濾文字浮水印</span>
              </div>
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
                  onChange={(e) => handleQuickUpdatePip(e.target.checked, pipMode)}
                  className="rounded bg-cinema-card border-cinema-border text-amber-cta focus:ring-0 cursor-pointer"
                />
              </div>

              {/* 實體檢索詞編輯與多圖源抓取 */}
              <div className="text-[11px] bg-cinema-card p-2.5 rounded border border-cinema-border/70 space-y-2">
                <div className="flex items-center justify-between text-cinema-muted">
                  <span className="font-medium text-cinema-text">考據實體檢索詞 (NASA/全網/國會圖書館/維基):</span>
                  <button
                    onClick={handleFetchPip}
                    disabled={isFetchingPip || !pipQuery.trim()}
                    className="flex items-center px-2 py-0.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/30 text-[10px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
                    title="立即向 NASA、全網新聞歷史照片、國會圖書館與維基百科檢索"
                  >
                    {isFetchingPip ? (
                      <>
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        <span>檢索中...</span>
                      </>
                    ) : (
                      <>
                        <Search className="w-3 h-3 mr-1" />
                        <span>重新抓圖</span>
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
                  placeholder="輸入具體型號、人物全名或條目名 (例如：Whiskey-class submarine)"
                  className="w-full h-7 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono focus:outline-none focus:border-amber-cta"
                />

                {detail?.status?.has_pip && detail?.status?.pip_url && (
                  <div className="pt-1.5 border-t border-cinema-border/50 space-y-1.5">
                    <div className="text-[10px] text-emerald-400 flex items-center justify-between">
                      <span className="flex items-center font-medium">
                        <CheckCircle2 className="w-3 h-3 mr-1 shrink-0" /> 已就緒考據照片
                      </span>
                      <button
                        onClick={handleClearPip}
                        disabled={isClearingPip}
                        className="flex items-center px-1.5 py-0.5 rounded bg-red-950/50 hover:bg-red-900/70 border border-red-800 text-[10px] text-red-300 transition-colors cursor-pointer disabled:opacity-40"
                        title="徹底刪除此考據圖檔案，完全回歸 AI 純繪圖畫面"
                      >
                        {isClearingPip ? (
                          <Loader2 className="w-2.5 h-2.5 animate-spin mr-0.5" />
                        ) : (
                          <Trash2 className="w-2.5 h-2.5 mr-0.5" />
                        )}
                        <span>清除圖檔</span>
                      </button>
                    </div>

                    {/* 檢索詞 vs 來源檔案標題清楚對照 */}
                    <div className="text-[10px] space-y-0.5 bg-cinema-darker/70 p-1.5 rounded border border-cinema-border/60 font-mono">
                      <div className="flex items-center text-cinema-muted truncate">
                        <span className="text-zinc-500 mr-1.5 shrink-0">命中實體:</span>
                        <span className="text-amber-cta/90 truncate font-semibold" title={detail.pip?.query || pipQuery}>
                          {detail.pip?.query || pipQuery || "未指定"}
                        </span>
                      </div>
                      {detail.pip?.source_title && (
                        <div className="flex items-center text-cinema-muted truncate">
                          <span className="text-zinc-500 mr-1.5 shrink-0">圖檔出處:</span>
                          <span className="text-zinc-300 truncate" title={detail.pip.source_title}>
                            {detail.pip.source_title}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* 若使用者修改了檢索詞但尚未重新抓圖，提示點擊更新 */}
                    {pipQuery.trim() && detail.pip?.query && pipQuery.trim() !== detail.pip.query && (
                      <div className="flex items-center justify-between p-1.5 rounded bg-amber-950/40 border border-amber-800/60 text-[10px] text-amber-300">
                        <span>檢索詞已修改，照片尚未更新</span>
                        <button
                          type="button"
                          onClick={handleFetchPip}
                          disabled={isFetchingPip}
                          className="px-1.5 py-0.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-bold cursor-pointer"
                        >
                          立即重新抓圖
                        </button>
                      </div>
                    )}

                    <div className={`relative max-w-[170px] max-h-[120px] p-1 rounded overflow-hidden border ${
                      pipMode === "spotlight" ? "border-cinema-border bg-black" : "border-white/80 bg-white shadow-md"
                    } flex items-center justify-center`}>
                      <img src={detail.status.pip_url} alt="PiP Preview" className="max-w-full max-h-[110px] object-contain rounded-sm" />
                    </div>
                  </div>
                )}
              </div>

              {/* 呈現方式：無論是否勾選啟用，都讓創作者一眼看清並能隨時切換 */}
              <div className="pt-1 text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-cinema-muted">呈現方式</span>
                  <select
                    value={pipMode}
                    onChange={(e) => handleQuickUpdatePip(pipEnabled, e.target.value as "pip" | "spotlight")}
                    className="h-7 px-2 rounded bg-cinema-card border border-cinema-border text-cinema-text text-[11px] font-medium"
                  >
                    <option value="pip">📌 畫中畫小卡 (PiP · 角落小卡)</option>
                    <option value="spotlight">🏛️ 黑底歷史聚焦 (慢推浮現 · 主角)</option>
                  </select>
                </div>

                {pipEnabled && pipMode === "pip" && (
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
                )}
                {pipEnabled && pipMode === "spotlight" && (
                  <div className="text-[11px] text-amber-cta/90 bg-amber-500/10 p-2 rounded border border-amber-500/20 leading-relaxed">
                    🏛️ 本幕將以深邃黑底為背景，真實考據照片在中央緩慢推鏡淡入，營造紀錄片大片沉浸感。
                  </div>
                )}
              </div>
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
