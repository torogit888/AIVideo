import React, { useEffect, useState, useRef } from "react";
import {
  X,
  Youtube,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Key,
  ShieldCheck,
  RefreshCw,
  FileText,
  Image as ImageIcon,
  Sparkles,
  Wand2,
} from "lucide-react";
import { api } from "../api";
import {
  YouTubeAuthStatus,
  YouTubePrepareData,
} from "../types";

interface Props {
  jobId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const YouTubeUploadModal: React.FC<Props> = ({ jobId, isOpen, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [generatingThumb, setGeneratingThumb] = useState(false);
  const [updatingExisting, setUpdatingExisting] = useState(false);
  const [authStatus, setAuthStatus] = useState<YouTubeAuthStatus | null>(null);
  const [prepareData, setPrepareData] = useState<YouTubePrepareData | null>(null);

  // 授權設定相關
  const [secretJsonText, setSecretJsonText] = useState("");
  const [showSecretInput, setShowSecretInput] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  // 表單資料
  const [title, setTitle] = useState("");
  const [candidateTitles, setCandidateTitles] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [privacy, setPrivacy] = useState<"private" | "unlisted" | "public">("unlisted");
  const [oldVideoAction, setOldVideoAction] = useState<"private" | "delete" | "keep">("private");
  const [uploadSrt, setUploadSrt] = useState(true);
  const [uploadThumb, setUploadThumb] = useState(true);
  const [currentThumbUrl, setCurrentThumbUrl] = useState<string | null>(null);

  // 上傳進度
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadResult, setUploadResult] = useState<any | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isSaved, setIsSaved] = useState(true);

  const pollIntervalRef = useRef<any>(null);
  const saveDraftTimerRef = useRef<any>(null);
  const prevOpenRef = useRef(false);
  const prevJobIdRef = useRef("");

  const triggerSaveDraft = (
    newTitle: string,
    newDesc: string,
    newTags: string,
    newPrivacy: string,
    newCandidates: string[]
  ) => {
    setIsSaved(false);
    if (saveDraftTimerRef.current) clearTimeout(saveDraftTimerRef.current);
    saveDraftTimerRef.current = setTimeout(async () => {
      try {
        const parsedTags = newTags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean);
        await api.saveYouTubeMetadata({
          job_id: jobId,
          title: newTitle.trim(),
          description: newDesc.trim(),
          tags: parsedTags,
          privacy_status: newPrivacy,
          candidate_titles: newCandidates,
        });
        setIsSaved(true);
      } catch (e) {
        console.error("Auto save draft failed", e);
      }
    }, 600);
  };

  useEffect(() => {
    const justOpened = isOpen && !prevOpenRef.current;
    const jobChanged = isOpen && prevJobIdRef.current !== jobId;

    if (justOpened || jobChanged) {
      loadInitialData();
    }
    prevOpenRef.current = isOpen;
    prevJobIdRef.current = jobId;

    if (!isOpen && pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    const handleWindowMessage = (event: MessageEvent) => {
      if (event.data?.type === "YOUTUBE_AUTH_SUCCESS") {
        loadInitialData();
      }
    };
    window.addEventListener("message", handleWindowMessage);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      window.removeEventListener("message", handleWindowMessage);
    };
  }, [isOpen, jobId]);

  const loadInitialData = async () => {
    setLoading(true);
    setAuthError(null);
    setUploadError(null);
    try {
      const [auth, prep] = await Promise.all([
        api.getYouTubeStatus(),
        api.prepareYouTubeUpload(jobId),
      ]);
      setAuthStatus(auth);
      setPrepareData(prep);
      setTitle(prep.default_title);
      setDescription(prep.default_description);
      setTagsText(prep.default_tags.join(", "));
      setPrivacy(prep.default_privacy);
      setCandidateTitles(prep.candidate_titles || []);
      setUploadSrt(prep.has_srt);
      setUploadThumb(prep.has_thumbnail);
      if (prep.thumbnail_url) {
        setCurrentThumbUrl(prep.thumbnail_url);
      }
      setIsSaved(true);

      // 檢查是否有進行中的上傳任務
      const currentStatus = await api.getYouTubeUploadStatus();
      if (currentStatus.is_uploading) {
        setUploading(true);
        setUploadProgress(currentStatus.progress);
        setUploadMessage(currentStatus.message);
        startPolling();
      } else if (currentStatus.result) {
        setUploadResult(currentStatus.result);
      }
    } catch (err: any) {
      setAuthError(err.message || "載入 YouTube 資料失敗");
    } finally {
      setLoading(false);
    }
  };

  const handleOptimizeMetadata = async () => {
    try {
      setOptimizing(true);
      setAuthError(null);
      const res = await api.optimizeYouTubeMetadata(jobId);
      setTitle(res.best_title);
      setCandidateTitles(res.titles || []);
      setDescription(res.description);
      setTagsText(res.tags.join(", "));
    } catch (err: any) {
      setAuthError(err.message || "演算法中繼資料優化失敗");
    } finally {
      setOptimizing(false);
    }
  };

  const handleGenerateThumbnail = async () => {
    try {
      setGeneratingThumb(true);
      setAuthError(null);
      // 直接傳遞當前畫面中選定/輸入的標題
      const res = await api.generateYouTubeThumbnail(jobId, title.trim());
      if (res.thumbnail_url) {
        setCurrentThumbUrl(res.thumbnail_url);
        setUploadThumb(true);
      }
    } catch (err: any) {
      setAuthError(err.message || "AI 封面縮圖生成失敗");
    } finally {
      setGeneratingThumb(false);
    }
  };

  const handleUpdateExistingOnly = async () => {
    const existingId = prepareData?.existing_youtube?.video_id;
    if (!existingId) return;
    try {
      setUpdatingExisting(true);
      setAuthError(null);
      const tags = tagsText
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean);

      const res = await api.updateExistingYouTubeVideo({
        job_id: jobId,
        video_id: existingId,
        title: title.trim(),
        description: description.trim(),
        tags,
        privacy_status: privacy,
        upload_thumbnail: uploadThumb,
      });

      setUploadResult(res);
    } catch (err: any) {
      setAuthError(err.message || "更新現有影片資訊失敗");
    } finally {
      setUpdatingExisting(false);
    }
  };

  const handleSaveSecret = async () => {
    if (!secretJsonText.trim()) return;
    try {
      setLoading(true);
      await api.uploadYouTubeSecret(secretJsonText.trim());
      const auth = await api.getYouTubeStatus();
      setAuthStatus(auth);
      setShowSecretInput(false);
      setSecretJsonText("");
    } catch (err: any) {
      setAuthError(err.message || "憑證儲存失敗");
    } finally {
      setLoading(false);
    }
  };

  const handleStartOAuth = async () => {
    try {
      setLoading(true);
      setAuthError(null);
      const res = await api.getYouTubeAuthUrl();
      if (res.auth_url) {
        window.open(res.auth_url, "_blank");
        // 啟動自動狀態偵測，一旦瀏覽器回呼換票成功立即自動更新
        const pollAuth = setInterval(async () => {
          try {
            const st = await api.getYouTubeStatus();
            if (st.is_authenticated) {
              clearInterval(pollAuth);
              setAuthStatus(st);
            }
          } catch (e) {}
        }, 1500);
        setTimeout(() => clearInterval(pollAuth), 120000);
      }
    } catch (err: any) {
      setAuthError(err.message || "取得授權網址失敗");
    } finally {
      setLoading(false);
    }
  };

  const startPolling = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const status = await api.getYouTubeUploadStatus();
        setUploadProgress(status.progress);
        setUploadMessage(status.message);
        if (!status.is_uploading) {
          clearInterval(pollIntervalRef.current);
          setUploading(false);
          if (status.error) {
            setUploadError(status.error);
          } else if (status.result) {
            setUploadResult(status.result);
          }
        }
      } catch (e) {
        console.error("Poll status error", e);
      }
    }, 1500);
  };

  const handleSubmitUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(0.02);
    setUploadMessage("正在啟動背景上傳...");

    try {
      const tags = tagsText
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean);

      await api.uploadToYouTube({
        job_id: jobId,
        title: title.trim(),
        description: description.trim(),
        tags,
        privacy_status: privacy,
        upload_subtitles: uploadSrt,
        upload_thumbnail: uploadThumb,
        old_video_id: prepareData?.existing_youtube?.video_id || null,
        old_video_action: oldVideoAction,
      });

      startPolling();
    } catch (err: any) {
      setUploading(false);
      setUploadError(err.message || "啟動上傳失敗");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[92vh] bg-cinema-card border border-cinema-border rounded-xl shadow-2xl flex flex-col overflow-hidden">
        {/* 頂部標題 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-cinema-border bg-cinema-darker/60">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-red-600/20 text-red-500 border border-red-500/30">
              <Youtube className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-cinema-text">發布成片至 YouTube</h3>
              <p className="text-xs text-cinema-muted">
                演算法高 CTR 最佳化 · 自動生成標題/標籤/章節/同風格 16:9 封面縮圖
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-cinema-muted hover:text-cinema-text hover:bg-cinema-cardHover transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 內容區塊 */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* 錯誤通知 */}
          {(authError || uploadError) && (
            <div className="p-3.5 rounded-lg bg-red-950/40 border border-red-800/60 flex items-start space-x-2.5 text-xs text-red-300">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
              <div className="flex-1 leading-relaxed">{authError || uploadError}</div>
            </div>
          )}

          {/* AI 演算法一鍵最佳化橫幅按鈕 */}
          <div className="p-3 rounded-lg bg-gradient-to-r from-amber-cta/15 via-red-600/10 to-transparent border border-amber-cta/30 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-amber-cta flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" />
                <span>YouTube 演算法一鍵最佳化</span>
              </div>
              <p className="text-[11px] text-cinema-muted mt-0.5">
                由 AI 解析故事高潮與反差懸念，生成高點擊率標題、章節時間軸與高搜尋標籤
              </p>
            </div>
            <button
              type="button"
              onClick={handleOptimizeMetadata}
              disabled={optimizing || loading}
              className="shrink-0 px-3 py-1.5 rounded bg-amber-cta hover:bg-amber-cta/90 text-black text-xs font-medium inline-flex items-center transition-all disabled:opacity-50"
            >
              {optimizing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  <span>分析演算中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  <span>一鍵生成優化</span>
                </>
              )}
            </button>
          </div>

          {/* 1. 授權狀態卡片 */}
          <div className="p-4 rounded-lg bg-cinema-darker border border-cinema-border space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-cinema-muted flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-cinema-accent" />
                Google 帳號授權狀態
              </span>
              {authStatus?.is_authenticated ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> 已綁定頻道
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  尚未授權
                </span>
              )}
            </div>

            {authStatus?.is_authenticated && authStatus.channel ? (
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center space-x-3">
                  {authStatus.channel.thumbnail ? (
                    <img
                      src={authStatus.channel.thumbnail}
                      alt={authStatus.channel.title || "Channel"}
                      className="w-8 h-8 rounded-full border border-cinema-border"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-red-600/20 text-red-400 flex items-center justify-center font-bold text-xs">
                      YT
                    </div>
                  )}
                  <div>
                    <div className="text-xs font-semibold text-cinema-text">
                      {authStatus.channel.title}
                    </div>
                    <div className="text-[11px] text-cinema-muted">
                      {authStatus.channel.custom_url || authStatus.channel.id}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleStartOAuth}
                  className="text-xs text-cinema-muted hover:text-amber-cta underline"
                >
                  切換帳號
                </button>
              </div>
            ) : (
              <div className="space-y-3 pt-1">
                {!authStatus?.has_client_secret ? (
                  <div className="space-y-2">
                    <p className="text-xs text-cinema-muted leading-relaxed">
                      請先備妥 Google Cloud 專案的 OAuth 2.0 Client Secret（已啟用 YouTube Data API v3）。
                    </p>
                    {showSecretInput ? (
                      <div className="space-y-2">
                        <textarea
                          rows={4}
                          value={secretJsonText}
                          onChange={(e) => setSecretJsonText(e.target.value)}
                          placeholder="貼上 client_secret.json 完整內容..."
                          className="w-full text-xs font-mono p-2 rounded bg-black/40 border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta"
                        />
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleSaveSecret}
                            className="px-3 py-1 bg-amber-cta text-black text-xs font-medium rounded hover:bg-amber-cta/90"
                          >
                            儲存憑證
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowSecretInput(false)}
                            className="px-3 py-1 bg-cinema-card border border-cinema-border text-xs rounded text-cinema-muted"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setShowSecretInput(true)}
                        className="inline-flex items-center text-xs text-amber-cta hover:underline"
                      >
                        <Key className="w-3.5 h-3.5 mr-1" />
                        匯入 client_secret.json 內容
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-cinema-muted">憑證已就緒，點擊按鈕登入 Google 帳號授權：</span>
                      <button
                        type="button"
                        onClick={handleStartOAuth}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-medium inline-flex items-center shadow transition-colors"
                      >
                        <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                        開啟 Google 登入視窗
                      </button>
                    </div>
                    <p className="text-[11px] text-cinema-muted/80">
                      💡 提示：點擊按鈕後將在新分頁開啟 Google 授權，完成授權後視窗會自動關閉並在此處完成綁定。
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 2. 上傳中進度展示 */}
          {uploading && (
            <div className="p-4 rounded-lg bg-amber-cta/10 border border-amber-cta/30 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-amber-cta flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  {uploadMessage || "正在上傳成片至 YouTube..."}
                </span>
                <span className="font-mono text-amber-cta font-bold">
                  {Math.round(uploadProgress * 100)}%
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-black/40 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-red-600 to-amber-cta transition-all duration-300"
                  style={{ width: `${Math.max(uploadProgress * 100, 3)}%` }}
                />
              </div>
              <p className="text-[11px] text-cinema-muted">
                大檔案採用 Resumable 斷點續傳分塊傳輸，請保持瀏覽器開啟。
              </p>
            </div>
          )}

          {/* 3. 上傳成功結果畫面 */}
          {uploadResult ? (
            <div className="p-5 rounded-xl bg-emerald-950/40 border border-emerald-800/60 space-y-4">
              <div className="flex items-center space-x-2 text-emerald-400 text-base font-semibold">
                <CheckCircle2 className="w-5 h-5" />
                <span>發布成功！已在 YouTube 上架</span>
              </div>
              <div className="text-xs text-cinema-muted space-y-1.5 bg-black/40 p-3 rounded-lg border border-cinema-border">
                <div>影片標題：<span className="text-cinema-text font-medium">{uploadResult.title}</span></div>
                <div>發布狀態：<span className="text-amber-cta font-mono uppercase font-bold">{uploadResult.privacy_status}</span></div>
                <div>繁中字幕：<span className="text-emerald-400 font-medium">{uploadResult.has_subtitles ? "已自動掛載" : "未掛載"}</span></div>
              </div>

              {/* 縮圖狀態與提示 */}
              {!uploadResult.has_thumbnail && (
                <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-2">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>自訂封面縮圖未自動套用說明：</span>
                  </div>
                  <p className="text-[11px] text-cinema-muted leading-relaxed">
                    {uploadResult.thumbnail_error || "YouTube 官方規定新頻道需在「YouTube 工作室」完成手機號碼簡訊驗證（中階功能資格），API 才能自訂上傳封面縮圖。"}
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <a
                      href={`/media/jobs/${encodeURIComponent(jobId)}/compose/thumbnail.png`}
                      download={`${jobId}_thumbnail.png`}
                      className="px-2.5 py-1 rounded bg-amber-cta text-black text-xs font-medium inline-flex items-center hover:bg-amber-cta/90 transition-colors"
                    >
                      <ImageIcon className="w-3.5 h-3.5 mr-1" />
                      下載已生成的黃白封面圖
                    </a>
                    <a
                      href={`https://studio.youtube.com/video/${uploadResult.video_id}/edit`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-2.5 py-1 rounded bg-cinema-card border border-cinema-border text-cinema-text text-xs inline-flex items-center hover:bg-cinema-cardHover transition-colors"
                    >
                      前往 Studio 上傳縮圖 / 驗證手機 <ExternalLink className="w-3 h-3 ml-1" />
                    </a>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2.5 pt-2">
                <a
                  href={uploadResult.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 justify-center py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-semibold inline-flex items-center shadow transition-colors"
                >
                  <ExternalLink className="w-4 h-4 mr-1.5" />
                  前往 YouTube 觀看影片
                </a>
                <a
                  href={uploadResult.studio_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 justify-center py-2 rounded-lg bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text font-medium inline-flex items-center transition-colors"
                >
                  <ExternalLink className="w-4 h-4 mr-1.5" />
                  YouTube Studio 編輯影片
                </a>
              </div>

              <div className="pt-2 border-t border-cinema-border/50 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setUploadResult(null)}
                  className="px-3 py-1.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
                >
                  再次編輯發布
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-1.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors"
                >
                  完成並關閉
                </button>
              </div>
            </div>
          ) : (
            /* 4. 發布表單 */
            <form onSubmit={handleSubmitUpload} className="space-y-4">
            {prepareData?.existing_youtube && (
              <>
                <div className="p-3.5 rounded-lg bg-blue-950/40 border border-blue-800/60 text-xs text-blue-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5">
                  <div className="space-y-0.5">
                    <div className="font-semibold flex items-center gap-1.5 text-blue-300">
                      <Youtube className="w-4 h-4 text-red-500" />
                      <span>本專案已在 YouTube 上架 (ID: {prepareData.existing_youtube.video_id})</span>
                    </div>
                    <p className="text-[11px] text-cinema-muted">
                      發布時間：{prepareData.existing_youtube.uploaded_at || "已發布"} · 狀態：{prepareData.existing_youtube.privacy_status}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={handleUpdateExistingOnly}
                      disabled={uploading || updatingExisting || loading}
                      className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium inline-flex items-center transition-colors disabled:opacity-50"
                      title="不重新上傳整部影片，僅同步更新標題、說明或補傳剛剛驗證通過的縮圖"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 mr-1 ${updatingExisting ? "animate-spin" : ""}`} />
                      <span>{updatingExisting ? "同步中..." : "同步更新資訊 / 補傳縮圖"}</span>
                    </button>
                    <a
                      href={prepareData.existing_youtube.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-2.5 py-1 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-cinema-text text-xs inline-flex items-center transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5 mr-1" />
                      觀看
                    </a>
                  </div>
                </div>

                {/* 舊影片處理方式 */}
                <div className="p-3 rounded-lg bg-cinema-darker/60 border border-cinema-border space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-cinema-text">若選擇重新發布新成片，如何處理舊版影片？</span>
                    <span className="text-[10px] text-cinema-muted">ID: {prepareData.existing_youtube.video_id}</span>
                  </div>
                  <select
                    value={oldVideoAction}
                    onChange={(e: any) => setOldVideoAction(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded bg-black/40 border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta"
                  >
                    <option value="private">自動將上一版舊影片設為私人下架（推薦・避免前台重複影片，保留後台備份）</option>
                    <option value="delete">直接從 YouTube 徹底刪除舊影片（完全清除）</option>
                    <option value="keep">保留舊影片（新舊兩部共存）</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-cinema-muted">
                    影片標題 (Title)
                  </label>
                  <span className={`text-[10px] ${isSaved ? "text-emerald-400/80" : "text-amber-cta animate-pulse"}`}>
                    {isSaved ? "✓ 草稿已儲存" : "✎ 儲存中..."}
                  </span>
                </div>
                <div className="text-[10px] text-cinema-muted">
                  {title.length}/100
                </div>
              </div>
              <input
                type="text"
                required
                maxLength={100}
                value={title}
                onChange={(e) => {
                  const newVal = e.target.value;
                  setTitle(newVal);
                  triggerSaveDraft(newVal, description, tagsText, privacy, candidateTitles);
                }}
                placeholder="輸入 YouTube 影片標題..."
                className="w-full text-xs px-3 py-2 rounded-lg bg-cinema-darker border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta"
              />

              {/* 候選標題快捷按鈕 */}
              {candidateTitles.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="text-[10px] text-cinema-muted">✨ 演算法高 CTR 候選標題（點擊套用）：</div>
                  <div className="flex flex-col gap-1">
                    {candidateTitles.map((t, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setTitle(t);
                          triggerSaveDraft(t, description, tagsText, privacy, candidateTitles);
                        }}
                        className={`text-left text-xs px-2.5 py-1.5 rounded border transition-all truncate ${
                          title === t
                            ? "bg-amber-cta/20 border-amber-cta text-amber-cta font-medium"
                            : "bg-cinema-darker/70 border-cinema-border text-cinema-muted hover:text-cinema-text hover:border-cinema-cardHover"
                        }`}
                      >
                        {idx + 1}. {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-cinema-muted mb-1.5">
                  發布隱私權限
                </label>
                <select
                  value={privacy}
                  onChange={(e: any) => {
                    const newVal = e.target.value;
                    setPrivacy(newVal);
                    triggerSaveDraft(title, description, tagsText, newVal, candidateTitles);
                  }}
                  className="w-full text-xs px-3 py-2 rounded-lg bg-cinema-darker border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta"
                >
                  <option value="unlisted">不公開 (Unlisted) - 推薦先複查</option>
                  <option value="private">私人 (Private) - 僅自己可見</option>
                  <option value="public">公開 (Public) - 立即全網發布</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cinema-muted mb-1.5">
                  影片標籤 (Tags，以逗號分隔)
                </label>
                <input
                  type="text"
                  value={tagsText}
                  onChange={(e) => {
                    const newVal = e.target.value;
                    setTagsText(newVal);
                    triggerSaveDraft(title, description, newVal, privacy, candidateTitles);
                  }}
                  placeholder="AIVideo, 說書人, 歷史..."
                  className="w-full text-xs px-3 py-2 rounded-lg bg-cinema-darker border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-cinema-muted">
                  說明欄內容 (Description)
                </label>
              </div>
              <textarea
                rows={6}
                maxLength={5000}
                value={description}
                onChange={(e) => {
                  const newVal = e.target.value;
                  setDescription(newVal);
                  triggerSaveDraft(title, newVal, tagsText, privacy, candidateTitles);
                }}
                placeholder="輸入影片介紹、延伸閱讀、參考資料..."
                className="w-full text-xs font-mono p-3 rounded-lg bg-cinema-darker border border-cinema-border text-cinema-text focus:outline-none focus:border-amber-cta leading-relaxed"
              />
            </div>

            {/* 封面縮圖預覽與 AI 生成 */}
            <div className="p-3.5 rounded-lg bg-cinema-darker/60 border border-cinema-border space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-cinema-muted flex items-center gap-1.5">
                  <ImageIcon className="w-3.5 h-3.5 text-amber-cta" />
                  <span>YouTube 16:9 封面縮圖 (黃白立體標題)</span>
                </span>
                <button
                  type="button"
                  onClick={handleGenerateThumbnail}
                  disabled={generatingThumb || loading}
                  className="px-2.5 py-1 rounded bg-amber-cta/15 hover:bg-amber-cta/25 border border-amber-cta/40 text-amber-cta text-xs font-medium inline-flex items-center transition-colors disabled:opacity-50"
                  title="由 Gemini 3.1 Flash 採用相同畫風，直接在畫面上生成選定標題的黃白配色醒目立體字"
                >
                  {generatingThumb ? (
                    <>
                      <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                      <span>3.1 Flash 出圖中...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-3 h-3 mr-1" />
                      <span>✨ AI 生成黃白標題封面縮圖</span>
                    </>
                  )}
                </button>
              </div>

              {currentThumbUrl ? (
                <div className="relative aspect-video w-full max-w-xs mx-auto rounded-lg overflow-hidden border border-cinema-border bg-black/60 shadow-md">
                  <img
                    src={currentThumbUrl}
                    alt="YouTube Thumbnail"
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[10px] text-white font-mono">
                    16:9 封面
                  </div>
                </div>
              ) : (
                <div className="text-center py-4 border border-dashed border-cinema-border/50 rounded-lg text-xs text-cinema-muted">
                  尚未生成專屬縮圖，可點擊上方按鈕一鍵繪製
                </div>
              )}

              {/* 勾選項 */}
              <div className="grid grid-cols-2 gap-3 pt-1 border-t border-cinema-border/40">
                <label className="flex items-center space-x-2 text-xs text-cinema-text cursor-pointer">
                  <input
                    type="checkbox"
                    checked={uploadThumb}
                    onChange={(e) => setUploadThumb(e.target.checked)}
                    className="rounded border-cinema-border text-amber-cta focus:ring-0"
                  />
                  <span>上傳設定為影片官方縮圖</span>
                </label>

                <label className="flex items-center space-x-2 text-xs text-cinema-text cursor-pointer">
                  <input
                    type="checkbox"
                    checked={uploadSrt}
                    onChange={(e) => setUploadSrt(e.target.checked)}
                    className="rounded border-cinema-border text-amber-cta focus:ring-0"
                  />
                  <FileText className="w-3.5 h-3.5 text-amber-cta" />
                  <span>自動掛載繁中字幕 (timeline.srt)</span>
                </label>
              </div>
            </div>

            {/* 底部按鈕 */}
            <div className="flex items-center justify-end space-x-2.5 pt-2 border-t border-cinema-border">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
              >
                關閉
              </button>
              <button
                type="submit"
                disabled={
                  uploading ||
                  !authStatus?.is_authenticated ||
                  !prepareData?.has_film ||
                  loading
                }
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-medium inline-flex items-center shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <UploadCloud className="w-4 h-4 mr-1.5" />
                <span>{uploading ? "上傳中..." : "立即發布至 YouTube"}</span>
              </button>
            </div>
          </form>
          )}
        </div>
      </div>
    </div>
  );
};

