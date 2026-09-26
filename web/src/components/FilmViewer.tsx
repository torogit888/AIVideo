import React from "react";
import { PlaySquare, Download, FileText, Film } from "lucide-react";
import { useStudioStore } from "../store";

export const FilmViewer: React.FC = () => {
  const { selectedJobId, scenes, openInspector, setTab } = useStudioStore();

  const encodedJobId = selectedJobId ? encodeURIComponent(selectedJobId) : "";
  const filmUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/film.mp4` : null;
  const srtUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/film.srt` : null;
  const assUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/film.ass` : null;

  const handleSceneClick = (sceneId: string) => {
    openInspector(sceneId);
    setTab("storyboard");
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 max-w-5xl mx-auto space-y-6">
      {/* 頂部標題與下載 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">成片劇院預覽</h2>
          <p className="text-xs text-cinema-muted">
            1080p 說書人成片播放與分鏡切片時間軸 · 支援直接下載純淨影片與 YouTube SRT 字幕檔
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {filmUrl && (
            <a
              href={filmUrl}
              download
              className="flex items-center h-8 px-3 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-text hover:text-amber-cta transition-colors"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" />
              <span>下載 MP4 成片</span>
            </a>
          )}
          {srtUrl && (
            <a
              href={srtUrl}
              download
              className="flex items-center h-8 px-3 rounded bg-amber-cta/15 hover:bg-amber-cta/25 border border-amber-cta/40 text-xs text-amber-cta font-medium transition-colors"
              title="下載 YouTube 專用 SRT 時間軸字幕檔，可在 YouTube Studio 直接上傳"
            >
              <FileText className="w-3.5 h-3.5 mr-1.5" />
              <span>下載 YouTube 字幕 (.srt)</span>
            </a>
          )}
          {assUrl && (
            <a
              href={assUrl}
              download
              className="flex items-center h-8 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
              title="下載帶絕對定位與樣式設定的 ASS 字幕檔"
            >
              <FileText className="w-3.5 h-3.5 mr-1" />
              <span>.ass</span>
            </a>
          )}
        </div>
      </div>

      {/* 16:9 主劇院播放器 */}
      <div className="relative aspect-video w-full rounded-xl bg-black overflow-hidden border border-cinema-border shadow-2xl">
        {filmUrl ? (
          <video
            src={filmUrl}
            controls
            className="w-full h-full object-contain"
            autoPlay={false}
          />
        ) : (
          <div className="flex flex-col items-center justify-center w-full h-full text-cinema-muted">
            <PlaySquare className="w-16 h-16 stroke-1 mb-3 text-cinema-muted/40" />
            <p className="text-sm">尚未合成 1080p 成片</p>
            <p className="text-xs text-cinema-muted/60 mt-1">請先於分鏡頁面完成出圖與配音後執行合成</p>
          </div>
        )}
      </div>

      {/* 下方分鏡時間軸切片 (帶秒數標記) */}
      <div>
        <div className="text-xs font-medium text-cinema-muted mb-2">分鏡時間軸 (點擊跳轉精修該幕)</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {scenes.map((s, idx) => {
            const startSec = idx * 6;
            const endSec = (idx + 1) * 6;
            const formatTime = (sec: number) =>
              `00:${String(sec).padStart(2, "0")}`;

            return (
              <div
                key={s.id}
                onClick={() => handleSceneClick(s.id)}
                className="group relative rounded-md bg-cinema-card border border-cinema-border overflow-hidden cursor-pointer hover:border-amber-cta transition-all"
              >
                <div className="text-[10px] text-center font-mono py-1 text-cinema-muted bg-cinema-darker border-b border-cinema-border/50">
                  {formatTime(startSec)} - {formatTime(endSec)}
                </div>
                <div className="aspect-video w-full bg-black/40 overflow-hidden">
                  {s.status.image_url ? (
                    <img
                      src={s.status.image_url}
                      alt={s.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                  ) : (
                    <Film className="w-6 h-6 m-auto text-cinema-muted/30" />
                  )}
                </div>
                <div className="p-1.5 text-center truncate text-[11px] text-cinema-text">
                  {s.title}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
