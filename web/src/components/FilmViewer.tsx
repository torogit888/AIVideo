import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { PlaySquare, Download, FileText, Youtube, RefreshCw, AlertCircle } from "lucide-react";
import { useStudioStore } from "../store";
import { YouTubeUploadModal } from "./YouTubeUploadModal";

export const FilmViewer: React.FC = () => {
  const { currentTab, jobs, selectedJobId, scenes, loadScenes, loadJobs, setTab, openInspector } =
    useStudioStore();
  const [showYouTubeModal, setShowYouTubeModal] = useState(false);
  const [filmVersion, setFilmVersion] = useState<number>(Date.now());
  const [videoError, setVideoError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const currentJob = jobs.find((j) => j.id === selectedJobId);
  const hasFilm = currentJob?.progress.film_ready ?? false;

  const refreshFilm = useCallback(() => {
    setFilmVersion(Date.now());
    setVideoError(false);
    if (selectedJobId) {
      loadScenes(selectedJobId);
      loadJobs();
    }
  }, [selectedJobId, loadScenes, loadJobs]);

  // 當使用者切換到成片分頁（或切換專案）時，自動同步最新專案資料並重新載入影片
  useEffect(() => {
    if (currentTab === "film" && selectedJobId) {
      refreshFilm();
    }
  }, [currentTab, selectedJobId, refreshFilm]);

  const encodedJobId = selectedJobId ? encodeURIComponent(selectedJobId) : "";
  const rawFilmUrl = encodedJobId && hasFilm ? `/media/jobs/${encodedJobId}/compose/film.mp4` : null;
  // 加上時間戳防止瀏覽器快取舊成片或快取先前的 404 狀態
  const filmPlayUrl = rawFilmUrl ? `${rawFilmUrl}?t=${filmVersion}` : null;
  const srtUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/timeline.srt` : null;
  const assUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/timeline.ass` : null;

  const cues = useMemo(() => {
    let t = 0;
    return scenes.map((s) => {
      const dur = s.status.duration > 0 ? s.status.duration : 5.5;
      const cue = { id: s.id, title: s.title, start: t, end: t + dur };
      t += dur;
      return cue;
    });
  }, [scenes]);
  const totalDur = cues.length ? cues[cues.length - 1].end : 1;

  const jumpToScene = (sceneId: string, startSec: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = startSec;
    }
    setTab("storyboard");
    openInspector(sceneId);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 pb-20 max-w-5xl mx-auto space-y-6">
      <div className="shrink-0 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">成片劇院預覽</h2>
          <p className="text-xs text-cinema-muted">
            1080p 說書人成片播放 · 點時間軸可跳到該場分鏡精修
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {rawFilmUrl && (
            <button
              onClick={refreshFilm}
              className="flex items-center h-8 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-amber-cta transition-colors"
              title="重新載入最新成片"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              <span>重新載入</span>
            </button>
          )}
          {rawFilmUrl && (
            <button
              onClick={() => setShowYouTubeModal(true)}
              className="flex items-center h-8 px-3 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-white text-xs font-medium transition-colors"
              title="將成片發布至 YouTube"
            >
              <Youtube className="w-3.5 h-3.5 mr-1.5" />
              <span>YouTube</span>
            </button>
          )}
          {rawFilmUrl && (
            <a
              href={rawFilmUrl}
              download
              className="flex items-center h-8 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              <span>.mp4</span>
            </a>
          )}
          {srtUrl && (
            <a
              href={srtUrl}
              download
              className="flex items-center h-8 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
              title="下載 SRT 字幕"
            >
              <FileText className="w-3.5 h-3.5 mr-1" />
              <span>.srt</span>
            </a>
          )}
          {assUrl && (
            <a
              href={assUrl}
              download
              className="flex items-center h-8 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
              title="下載 ASS 字幕檔"
            >
              <FileText className="w-3.5 h-3.5 mr-1" />
              <span>.ass</span>
            </a>
          )}
        </div>
      </div>

      <div className="shrink-0 relative aspect-video w-full rounded-xl bg-black overflow-hidden border border-cinema-border shadow-2xl">
        {filmPlayUrl && !videoError ? (
          <video
            key={filmPlayUrl}
            ref={videoRef}
            src={filmPlayUrl}
            controls
            className="w-full h-full object-contain"
            autoPlay={false}
            onError={() => setVideoError(true)}
          />
        ) : videoError ? (
          <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted space-y-3 p-6 text-center">
            <AlertCircle className="w-12 h-12 text-amber-cta/80" />
            <div>
              <p className="text-sm font-medium text-cinema-text">成片檔案載入中或尚未完全寫入</p>
              <p className="text-xs text-cinema-muted mt-1">若剛剛才合成完成，請點擊下方按鈕重試</p>
            </div>
            <button
              onClick={refreshFilm}
              className="flex items-center h-8 px-4 rounded-lg bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              <span>重新載入影片</span>
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted">
            <PlaySquare className="w-16 h-16 stroke-1 mb-3 text-cinema-muted/40" />
            <p className="text-sm">尚未合成 1080p 成片</p>
            <p className="text-xs text-cinema-muted/60 mt-1">請先於分鏡頁面完成出圖與配音後執行合成</p>
          </div>
        )}
      </div>

      {cues.length > 0 && (
        <div className="shrink-0 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-cinema-muted">
            <span>時間軸（點一場進入分鏡 Inspector）</span>
            <span className="font-mono">{cues.length} 場</span>
          </div>
          <div className="flex h-10 rounded-lg overflow-hidden border border-cinema-border bg-cinema-darker">
            {cues.map((cue) => {
              const pct = ((cue.end - cue.start) / totalDur) * 100;
              return (
                <button
                  key={cue.id}
                  type="button"
                  title={`${cue.title} · ${cue.start.toFixed(1)}s`}
                  onClick={() => jumpToScene(cue.id, cue.start)}
                  style={{ width: `${Math.max(pct, 0.8)}%` }}
                  className="h-full min-w-[4px] border-r border-cinema-border/60 last:border-r-0 bg-cinema-card hover:bg-amber-cta/40 text-[9px] text-cinema-muted hover:text-cinema-text truncate px-0.5 transition-colors"
                >
                  {pct >= 3 ? cue.title : ""}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {selectedJobId && (
        <YouTubeUploadModal
          jobId={selectedJobId}
          isOpen={showYouTubeModal}
          onClose={() => setShowYouTubeModal(false)}
        />
      )}
    </div>
  );
};
