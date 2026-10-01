import React, { useState } from "react";
import { PlaySquare, Download, FileText, Youtube } from "lucide-react";
import { useStudioStore } from "../store";
import { YouTubeUploadModal } from "./YouTubeUploadModal";

export const FilmViewer: React.FC = () => {
  const { selectedJobId } = useStudioStore();
  const [showYouTubeModal, setShowYouTubeModal] = useState(false);

  const encodedJobId = selectedJobId ? encodeURIComponent(selectedJobId) : "";
  const filmUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/film.mp4` : null;
  const srtUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/timeline.srt` : null;
  const assUrl = encodedJobId ? `/media/jobs/${encodedJobId}/compose/timeline.ass` : null;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 pb-20 max-w-5xl mx-auto space-y-6">
      {/* 頂部標題與下載 */}
      <div className="shrink-0 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">成片劇院預覽</h2>
          <p className="text-xs text-cinema-muted">
            1080p 說書人成片播放 · 支援一鍵發布至 YouTube 或下載純淨影片與 SRT 字幕檔
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {filmUrl && (
            <button
              onClick={() => setShowYouTubeModal(true)}
              className="flex items-center h-8 px-3 rounded bg-red-600 hover:bg-red-700 text-white text-xs font-medium shadow-md transition-colors"
              title="將成片與字幕一鍵發布至 YouTube"
            >
              <Youtube className="w-4 h-4 mr-1.5" />
              <span>發布至 YouTube</span>
            </button>
          )}
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

      {/* 16:9 主劇院播放器（加上 shrink-0 防止被 flex 壓縮為 0） */}
      <div className="shrink-0 relative aspect-video w-full rounded-xl bg-black overflow-hidden border border-cinema-border shadow-2xl">
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

      {/* YouTube 發布彈窗 */}
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
