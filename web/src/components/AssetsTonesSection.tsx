import React from "react";
import { BookOpen, FileText, Loader2, Save, Sparkles, Trash2, Upload, X } from "lucide-react";
import { AI_TEXT_MODELS, AssetTone } from "../types";

interface AssetsTonesSectionProps {
  tones: AssetTone[];
  selectedTone: AssetTone | null;
  onSelectTone: (t: AssetTone) => void;
  onCloseDrawer: () => void;
  editToneTitle: string;
  setEditToneTitle: (v: string) => void;
  editToneSummary: string;
  setEditToneSummary: (v: string) => void;
  editToneTags: string;
  setEditToneTags: (v: string) => void;
  editToneVoice: string;
  setEditToneVoice: (v: string) => void;
  editToneContent: string;
  setEditToneContent: (v: string) => void;
  editToneTab: "manual" | "re-extract";
  setEditToneTab: (v: "manual" | "re-extract") => void;
  reExtractText: string;
  setReExtractText: (v: string) => void;
  reExtractKeepTitle: boolean;
  setReExtractKeepTitle: (v: boolean) => void;
  reExtracting: boolean;
  reExtractMsg: string;
  onReExtractFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onReExtractTone: () => Promise<void>;
  saving: boolean;
  onSaveTone: () => Promise<void>;
  onDeleteTone: (id: string, title: string) => Promise<void>;
  selectedAiModel: string;
  setSelectedAiModel: (m: string) => void;
  isCreateToneOpen: boolean;
  setIsCreateToneOpen: (open: boolean) => void;
  createToneMode: "vertex" | "manual";
  setCreateToneMode: (m: "vertex" | "manual") => void;
  extractText: string;
  setExtractText: (v: string) => void;
  extractToneId: string;
  setExtractToneId: (v: string) => void;
  extractToneTitle: string;
  setExtractToneTitle: (v: string) => void;
  extracting: boolean;
  extractMsg: string;
  onToneFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onExtractTone: () => Promise<void>;
  newToneId: string;
  setNewToneId: (v: string) => void;
  newToneTitle: string;
  setNewToneTitle: (v: string) => void;
  newToneSummary: string;
  setNewToneSummary: (v: string) => void;
  newToneTags: string;
  setNewToneTags: (v: string) => void;
  newToneVoice: string;
  setNewToneVoice: (v: string) => void;
  newToneContent: string;
  setNewToneContent: (v: string) => void;
  onCreateTone: () => Promise<void>;
}

export const AssetsTonesSection: React.FC<AssetsTonesSectionProps> = ({
  tones,
  selectedTone,
  onSelectTone,
  onCloseDrawer,
  editToneTitle,
  setEditToneTitle,
  editToneSummary,
  setEditToneSummary,
  editToneTags,
  setEditToneTags,
  editToneVoice,
  setEditToneVoice,
  editToneContent,
  setEditToneContent,
  editToneTab,
  setEditToneTab,
  reExtractText,
  setReExtractText,
  reExtractKeepTitle,
  setReExtractKeepTitle,
  reExtracting,
  reExtractMsg,
  onReExtractFileUpload,
  onReExtractTone,
  saving,
  onSaveTone,
  onDeleteTone,
  selectedAiModel,
  setSelectedAiModel,
  isCreateToneOpen,
  setIsCreateToneOpen,
  createToneMode,
  setCreateToneMode,
  extractText,
  setExtractText,
  extractToneId,
  setExtractToneId,
  extractToneTitle,
  setExtractToneTitle,
  extracting,
  extractMsg,
  onToneFileUpload,
  onExtractTone,
  newToneId,
  setNewToneId,
  newToneTitle,
  setNewToneTitle,
  newToneSummary,
  setNewToneSummary,
  newToneTags,
  setNewToneTags,
  newToneVoice,
  setNewToneVoice,
  newToneContent,
  setNewToneContent,
  onCreateTone,
}) => {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {tones.map((t) => (
          <div
            key={t.id}
            onClick={() => onSelectTone(t)}
            className={`p-4 rounded-lg bg-cinema-card border cursor-pointer transition-all space-y-2.5 ${
              selectedTone?.id === t.id
                ? "border-amber-cta ring-2 ring-amber-cta/30"
                : "border-cinema-border hover:border-cinema-muted"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <h4 className="text-xs font-semibold text-amber-cta leading-snug">{t.title}</h4>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cinema-darker text-cinema-muted border border-cinema-border shrink-0">
                {t.id}
              </span>
            </div>

            {t.tags && t.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {t.tags.map((tag, i) => (
                  <span key={i} className="px-1.5 py-0.5 rounded bg-amber-cta/10 text-amber-cta/80 text-[10px]">
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            <p className="text-xs text-cinema-muted leading-relaxed line-clamp-3">{t.summary}</p>

            {t.recommended_voice_instruct && (
              <div className="text-[11px] text-zinc-400 bg-cinema-darker/60 px-2 py-1 rounded border border-cinema-border/50 flex items-center space-x-1.5">
                <span className="text-amber-cta/80 font-medium shrink-0">建議音色：</span>
                <span className="truncate">{t.recommended_voice_instruct}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 右側編輯口吻範本抽屜 */}
      {selectedTone && (
        <aside className="fixed right-0 top-12 bottom-0 w-[440px] z-30 flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-3 overflow-y-auto shadow-2xl">
          <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-amber-cta" />
              <div>
                <span className="text-xs font-semibold text-cinema-text">編輯口吻範本</span>
                <div className="text-[10px] font-mono text-cinema-muted">{selectedTone.id}</div>
              </div>
            </div>
            <button onClick={onCloseDrawer} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex border-b border-cinema-border">
            <button
              type="button"
              onClick={() => setEditToneTab("manual")}
              className={`flex items-center px-3 py-1.5 text-xs font-medium border-b-2 transition-all ${
                editToneTab === "manual"
                  ? "border-amber-cta text-amber-cta font-semibold"
                  : "border-transparent text-cinema-muted hover:text-cinema-text"
              }`}
            >
              <FileText className="w-3.5 h-3.5 mr-1" />
              <span>手動修改</span>
            </button>
            <button
              type="button"
              onClick={() => setEditToneTab("re-extract")}
              className={`flex items-center px-3 py-1.5 text-xs font-medium border-b-2 transition-all ${
                editToneTab === "re-extract"
                  ? "border-amber-cta text-amber-cta font-semibold"
                  : "border-transparent text-cinema-muted hover:text-cinema-text"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-cta" />
              <span>逐字稿 AI 重新分析</span>
            </button>
          </div>

          {editToneTab === "manual" ? (
            <>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">口吻名稱</label>
                <input
                  type="text"
                  value={editToneTitle}
                  onChange={(e) => setEditToneTitle(e.target.value)}
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">標籤 (逗號分隔)</label>
                  <input
                    type="text"
                    value={editToneTags}
                    onChange={(e) => setEditToneTags(e.target.value)}
                    placeholder="科普, 懸念, 幽默"
                    className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">建議音色</label>
                  <input
                    type="text"
                    value={editToneVoice}
                    onChange={(e) => setEditToneVoice(e.target.value)}
                    placeholder="女，青年，中音调"
                    className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">簡要描述</label>
                <textarea
                  value={editToneSummary}
                  onChange={(e) => setEditToneSummary(e.target.value)}
                  rows={2}
                  className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                />
              </div>

              <div className="flex-1 flex flex-col min-h-[220px] space-y-1">
                <label className="text-[11px] text-cinema-muted font-medium">口白範本與結構規範 (Markdown)</label>
                <textarea
                  value={editToneContent}
                  onChange={(e) => setEditToneContent(e.target.value)}
                  className="flex-1 p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-zinc-300 font-mono resize-none focus:outline-none focus:border-amber-cta leading-relaxed"
                />
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <button
                  onClick={() => onDeleteTone(selectedTone.id, selectedTone.title)}
                  className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  <span>刪除</span>
                </button>
                <button
                  onClick={onSaveTone}
                  disabled={saving}
                  className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
                >
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                  <span>{saving ? "儲存中..." : "儲存變更"}</span>
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-[11px] text-cinema-muted font-medium">新參考逐字稿</label>
                <label className="cursor-pointer inline-flex items-center px-2 py-0.5 rounded bg-cinema-darker hover:bg-zinc-800 border border-cinema-border text-[10px] text-zinc-300 hover:text-white transition-colors">
                  <Upload className="w-3 h-3 mr-1 text-amber-cta" />
                  <span>載入檔案 (.txt / .md)</span>
                  <input type="file" accept=".txt,.md" onChange={onReExtractFileUpload} className="hidden" />
                </label>
              </div>

              <textarea
                value={reExtractText}
                onChange={(e) => setReExtractText(e.target.value)}
                rows={9}
                disabled={reExtracting}
                placeholder="貼上新的逐字稿或示範文稿..."
                className="flex-1 min-h-[180px] p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta leading-relaxed"
              />

              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center space-x-2 pt-2">
                  <input
                    type="checkbox"
                    id="keep_title_chk"
                    checked={reExtractKeepTitle}
                    onChange={(e) => setReExtractKeepTitle(e.target.checked)}
                    className="rounded bg-cinema-darker border-cinema-border text-amber-cta focus:ring-0 cursor-pointer"
                  />
                  <label htmlFor="keep_title_chk" className="text-[11px] text-cinema-muted cursor-pointer select-none">
                    保留原名稱
                  </label>
                </div>
                <div>
                  <select
                    value={selectedAiModel}
                    onChange={(e) => setSelectedAiModel(e.target.value)}
                    disabled={reExtracting}
                    className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-amber-cta font-medium focus:outline-none focus:border-amber-cta cursor-pointer"
                  >
                    {AI_TEXT_MODELS.map((m) => (
                      <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text">
                        {m.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {reExtracting && (
                <div className="p-2.5 rounded-lg bg-cinema-darker border border-amber-cta/30 flex items-center space-x-2 text-xs text-amber-cta animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>{reExtractMsg || "正在重新分析並覆蓋..."}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
                <button
                  onClick={() => setEditToneTab("manual")}
                  disabled={reExtracting}
                  className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
                >
                  返回
                </button>
                <button
                  onClick={onReExtractTone}
                  disabled={reExtracting || !reExtractText.trim()}
                  className="flex items-center px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow disabled:opacity-50 transition-all"
                >
                  {reExtracting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      <span>分析中...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                      <span>重新分析並覆蓋</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* 新增口吻範本 Modal */}
      {isCreateToneOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-5 space-y-3.5">
            <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">新增口吻範本</h3>
              </div>
              <button
                onClick={() => {
                  if (!extracting) setIsCreateToneOpen(false);
                }}
                className="text-cinema-muted hover:text-cinema-text"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex border-b border-cinema-border">
              <button
                type="button"
                onClick={() => setCreateToneMode("vertex")}
                className={`flex items-center px-4 py-2 text-xs font-medium border-b-2 transition-all ${
                  createToneMode === "vertex"
                    ? "border-amber-cta text-amber-cta font-semibold"
                    : "border-transparent text-cinema-muted hover:text-cinema-text"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>AI 逐字稿萃取</span>
              </button>
              <button
                type="button"
                onClick={() => setCreateToneMode("manual")}
                className={`flex items-center px-4 py-2 text-xs font-medium border-b-2 transition-all ${
                  createToneMode === "manual"
                    ? "border-amber-cta text-amber-cta font-semibold"
                    : "border-transparent text-cinema-muted hover:text-cinema-text"
                }`}
              >
                <FileText className="w-3.5 h-3.5 mr-1.5" />
                <span>手動填寫</span>
              </button>
            </div>

            {createToneMode === "vertex" ? (
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-cinema-muted font-medium">參考文本 / 說書逐字稿</label>
                  <label className="cursor-pointer inline-flex items-center px-2.5 py-1 rounded bg-cinema-darker hover:bg-zinc-800 border border-cinema-border text-[11px] text-zinc-300 hover:text-white transition-colors">
                    <Upload className="w-3 h-3 mr-1 text-amber-cta" />
                    <span>上傳檔案 (.txt / .md)</span>
                    <input type="file" accept=".txt,.md" onChange={onToneFileUpload} className="hidden" />
                  </label>
                </div>

                <textarea
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  rows={7}
                  disabled={extracting}
                  placeholder="貼上參考說書影片逐字稿或文稿..."
                  className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta leading-relaxed"
                />

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">口吻名稱 (選填)</label>
                    <input
                      type="text"
                      value={extractToneTitle}
                      onChange={(e) => setExtractToneTitle(e.target.value)}
                      disabled={extracting}
                      placeholder="留空由 AI 命名"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">英文 ID (選填)</label>
                    <input
                      type="text"
                      value={extractToneId}
                      onChange={(e) => setExtractToneId(e.target.value)}
                      disabled={extracting}
                      placeholder="例如: tech_deepdive"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">分析模型</label>
                    <select
                      value={selectedAiModel}
                      onChange={(e) => setSelectedAiModel(e.target.value)}
                      disabled={extracting}
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium focus:outline-none focus:border-amber-cta cursor-pointer"
                    >
                      {AI_TEXT_MODELS.map((m) => (
                        <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text">
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {extracting && (
                  <div className="p-2.5 rounded-lg bg-cinema-darker border border-amber-cta/30 flex items-center space-x-2 text-xs text-amber-cta animate-pulse">
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>{extractMsg || "正在分析並寫入專案..."}</span>
                  </div>
                )}

                <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
                  <button
                    onClick={() => setIsCreateToneOpen(false)}
                    disabled={extracting}
                    className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
                  >
                    取消
                  </button>
                  <button
                    onClick={onExtractTone}
                    disabled={extracting || !extractText.trim()}
                    className="flex items-center px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow disabled:opacity-50 transition-all"
                  >
                    {extracting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        <span>萃取中...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                        <span>AI 萃取並儲存</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 pt-1">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">英文 ID</label>
                    <input
                      type="text"
                      value={newToneId}
                      onChange={(e) => setNewToneId(e.target.value)}
                      placeholder="例如: tech_future"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">口吻名稱</label>
                    <input
                      type="text"
                      value={newToneTitle}
                      onChange={(e) => setNewToneTitle(e.target.value)}
                      placeholder="例如：硬核商業傳奇風"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">標籤 (逗號分隔)</label>
                    <input
                      type="text"
                      value={newToneTags}
                      onChange={(e) => setNewToneTags(e.target.value)}
                      placeholder="商業, 傳奇, 說書"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">建議音色</label>
                    <input
                      type="text"
                      value={newToneVoice}
                      onChange={(e) => setNewToneVoice(e.target.value)}
                      placeholder="女，青年，中音调"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">簡要描述</label>
                  <textarea
                    value={newToneSummary}
                    onChange={(e) => setNewToneSummary(e.target.value)}
                    rows={2}
                    placeholder="描述此口吻的破題節奏與特色..."
                    className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">口白範本與結構規範 (Markdown)</label>
                  <textarea
                    value={newToneContent}
                    onChange={(e) => setNewToneContent(e.target.value)}
                    rows={5}
                    className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta leading-relaxed"
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
                  <button
                    onClick={() => setIsCreateToneOpen(false)}
                    className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
                  >
                    取消
                  </button>
                  <button
                    onClick={onCreateTone}
                    disabled={saving}
                    className="px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow"
                  >
                    {saving ? "建立中..." : "確認建立"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
