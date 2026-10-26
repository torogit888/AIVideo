import React, { useEffect } from "react";
import { Film, Trash2, ArrowRight } from "lucide-react";
import { useStudioStore } from "../store";

export const OverviewPanel: React.FC = () => {
  const {
    jobs,
    selectedJobId,
    loadJobs,
    selectJob,
    deleteJob,
    setTab,
    startNewDraft,
  } = useStudioStore();

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const handleDeleteJobFromList = async (
    jobId: string,
    jobTitle: string,
    e: React.MouseEvent
  ) => {
    e.stopPropagation();
    await deleteJob(jobId, jobTitle);
  };

  return (
    <div className="flex-1 p-6 space-y-5 max-w-5xl mx-auto overflow-y-auto">
      <div className="flex justify-between items-center border-b border-cinema-border pb-3">
        <h2 className="text-base font-bold text-cinema-text">專案總覽</h2>
        <span className="text-xs font-mono text-cinema-muted">{jobs.length} 個專案</span>
      </div>

      {jobs.length === 0 ? (
        <div className="p-12 text-center rounded-lg bg-cinema-card border border-cinema-border space-y-3">
          <Film className="w-8 h-8 text-cinema-muted/50 mx-auto" />
          <p className="text-xs text-cinema-muted">目前尚無任何專案</p>
          <button
            onClick={() => startNewDraft()}
            className="text-xs text-amber-cta hover:underline font-medium"
          >
            立即點此建立第一個說書故事
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((j) => {
            const isSelected = selectedJobId === j.id;
            const total = j.progress.scenes_count;
            const imgReady = j.progress.images_ready;
            const audReady = j.progress.audio_ready;
            const filmReady = j.progress.film_ready;

            return (
              <div
                key={j.id}
                onClick={() => {
                  void (async () => {
                    const ok = await selectJob(j.id);
                    if (ok) setTab("storyboard");
                  })();
                }}
                className={`p-4 rounded-lg bg-cinema-card border cursor-pointer transition-all space-y-3 flex flex-col justify-between ${
                  isSelected
                    ? "border-amber-cta ring-2 ring-amber-cta/30"
                    : "border-cinema-border hover:border-cinema-muted"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-cinema-text truncate" title={j.title}>
                      {j.title}
                    </h3>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {j.progress.youtube_published && (
                        <a
                          href={
                            j.progress.youtube_video_url ||
                            `https://youtu.be/${j.progress.youtube_video_id}`
                          }
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[10px] px-2 py-0.5 rounded bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 font-medium flex items-center gap-1 transition-colors"
                          title={`已於 ${j.progress.youtube_uploaded_at || "YouTube"} 發布，點擊前往觀看`}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                          <span>YouTube 已上架</span>
                        </a>
                      )}
                      {isSelected && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-cta/20 text-amber-cta font-medium">
                          當前作用中
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-[11px] font-mono text-cinema-muted truncate">ID: {j.id}</div>
                  {j.load_error && (
                    <p className="text-[11px] text-red-300 break-words" title={j.load_error}>
                      讀取失敗：{j.load_error}
                    </p>
                  )}
                </div>

                {/* 進度指標 (4 欄位：畫面、配音、成片、YouTube) */}
                <div className="grid grid-cols-4 gap-2 py-2 border-y border-cinema-border/50 text-[11px]">
                  <div>
                    <span className="text-cinema-muted block text-[10px]">畫面產出</span>
                    <span
                      className={`font-semibold ${
                        imgReady === total && total > 0 ? "text-emerald-400" : "text-cinema-text"
                      }`}
                    >
                      {imgReady} / {total}
                    </span>
                  </div>
                  <div>
                    <span className="text-cinema-muted block text-[10px]">語音配音</span>
                    <span
                      className={`font-semibold ${
                        audReady === total && total > 0 ? "text-emerald-400" : "text-cinema-text"
                      }`}
                    >
                      {audReady} / {total}
                    </span>
                  </div>
                  <div>
                    <span className="text-cinema-muted block text-[10px]">成片狀態</span>
                    <span
                      className={`font-semibold ${
                        !filmReady
                          ? "text-amber-500"
                          : j.progress.film_stale
                          ? "text-amber-400"
                          : "text-emerald-400"
                      }`}
                    >
                      {!filmReady ? "待合成" : j.progress.film_stale ? "已合成 (已過期)" : "已合成"}
                    </span>
                  </div>
                  <div>
                    <span className="text-cinema-muted block text-[10px]">YouTube</span>
                    <span
                      className={`font-semibold ${
                        j.progress.youtube_published ? "text-red-400" : "text-cinema-muted"
                      }`}
                    >
                      {j.progress.youtube_published ? "已發布" : "未發布"}
                    </span>
                  </div>
                </div>

                {/* 操作列 */}
                <div className="flex items-center justify-between pt-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      void (async () => {
                        const ok = await selectJob(j.id);
                        if (ok) setTab("storyboard");
                      })();
                    }}
                    className="flex items-center text-xs text-amber-cta hover:text-amber-ctaHover font-medium"
                  >
                    <span>進入故事板</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </button>
                  <button
                    onClick={(e) => handleDeleteJobFromList(j.id, j.title, e)}
                    title="刪除此專案"
                    className="p-1.5 rounded hover:bg-red-950/60 text-cinema-muted hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
