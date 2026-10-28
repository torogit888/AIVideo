import React from "react";
import { Image as ImageIcon, Save, Sparkles, Trash2, Upload, X } from "lucide-react";
import { AssetStyle } from "../types";
import { fileToBase64 } from "./AssetsVoiceConfig";

interface AssetsStylesSectionProps {
  styles: AssetStyle[];
  selectedStyle: AssetStyle | null;
  onSelectStyle: (s: AssetStyle) => void;
  onCloseDrawer: () => void;
  editStyleName: string;
  setEditStyleName: (v: string) => void;
  editStyleDesc: string;
  setEditStyleDesc: (v: string) => void;
  editStylePrompt: string;
  setEditStylePrompt: (v: string) => void;
  editStyleNegative: string;
  setEditStyleNegative: (v: string) => void;
  editStylePreviewDisplay: string | null;
  setEditStylePreviewDisplay: (v: string | null) => void;
  setEditStylePreviewBase64: (v: string | null) => void;
  saving: boolean;
  onSaveStyle: () => Promise<void>;
  onDeleteStyle: (id: string, name: string) => Promise<void>;
  isCreateStyleOpen: boolean;
  setIsCreateStyleOpen: (open: boolean) => void;
  newStyleId: string;
  setNewStyleId: (v: string) => void;
  newStyleName: string;
  setNewStyleName: (v: string) => void;
  newStyleDesc: string;
  setNewStyleDesc: (v: string) => void;
  newStylePrompt: string;
  setNewStylePrompt: (v: string) => void;
  newStyleNegative: string;
  setNewStyleNegative: (v: string) => void;
  newStylePreviewBase64: string | null;
  setNewStylePreviewBase64: (v: string | null) => void;
  onCreateStyle: () => Promise<void>;
}

export const AssetsStylesSection: React.FC<AssetsStylesSectionProps> = ({
  styles,
  selectedStyle,
  onSelectStyle,
  onCloseDrawer,
  editStyleName,
  setEditStyleName,
  editStyleDesc,
  setEditStyleDesc,
  editStylePrompt,
  setEditStylePrompt,
  editStyleNegative,
  setEditStyleNegative,
  editStylePreviewDisplay,
  setEditStylePreviewDisplay,
  setEditStylePreviewBase64,
  saving,
  onSaveStyle,
  onDeleteStyle,
  isCreateStyleOpen,
  setIsCreateStyleOpen,
  newStyleId,
  setNewStyleId,
  newStyleName,
  setNewStyleName,
  newStyleDesc,
  setNewStyleDesc,
  newStylePrompt,
  setNewStylePrompt,
  newStyleNegative,
  setNewStyleNegative,
  newStylePreviewBase64,
  setNewStylePreviewBase64,
  onCreateStyle,
}) => {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {styles.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelectStyle(s)}
            className={`group rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all ${
              selectedStyle?.id === s.id
                ? "border-amber-cta ring-2 ring-amber-cta/30"
                : "border-cinema-border hover:border-cinema-muted"
            }`}
          >
            <div className="aspect-video w-full bg-black/50 overflow-hidden relative flex items-center justify-center">
              {s.preview_url ? (
                <img
                  src={s.preview_url}
                  alt={s.name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                />
              ) : (
                <ImageIcon className="w-8 h-8 text-cinema-muted/40" />
              )}
              <div className="absolute top-2 left-2 flex space-x-1">
                {s.tags.map((t, i) => (
                  <span key={i} className="px-1.5 py-0.5 rounded bg-black/70 text-[10px] text-zinc-300">
                    {t}
                  </span>
                ))}
              </div>
            </div>
            <div className="p-3">
              <h4 className="text-xs font-semibold text-cinema-text truncate">{s.name}</h4>
              <p className="mt-1 text-[11px] text-cinema-muted line-clamp-2 leading-relaxed">{s.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 右側編輯風格抽屜 */}
      {selectedStyle && (
        <aside className="fixed right-0 top-12 bottom-0 w-[380px] z-30 flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-3.5 overflow-y-auto shadow-2xl">
          <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
            <div>
              <span className="text-xs font-semibold text-cinema-text">編輯視覺風格</span>
              <div className="text-[10px] font-mono text-cinema-muted">{selectedStyle.id}</div>
            </div>
            <button onClick={onCloseDrawer} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] text-cinema-muted">示範預覽圖</label>
            <div className="aspect-video w-full rounded bg-black/60 overflow-hidden border border-cinema-border relative group">
              {editStylePreviewDisplay ? (
                <img src={editStylePreviewDisplay} alt="" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-cinema-muted/40">
                  <ImageIcon className="w-8 h-8" />
                </div>
              )}
              <label className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center text-xs text-white cursor-pointer transition-opacity">
                <Upload className="w-5 h-5 mb-1 text-amber-cta" />
                <span>更換圖片</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const b64 = await fileToBase64(file);
                      setEditStylePreviewBase64(b64);
                      setEditStylePreviewDisplay(b64);
                    }
                  }}
                />
              </label>
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">風格名稱</label>
            <input
              type="text"
              value={editStyleName}
              onChange={(e) => setEditStyleName(e.target.value)}
              className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">風格描述</label>
            <textarea
              value={editStyleDesc}
              onChange={(e) => setEditStyleDesc(e.target.value)}
              rows={2}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">正向提示詞前綴 (Style Prefix)</label>
            <textarea
              value={editStylePrompt}
              onChange={(e) => setEditStylePrompt(e.target.value)}
              rows={4}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">負向過濾詞 (Negative)</label>
            <textarea
              value={editStyleNegative}
              onChange={(e) => setEditStyleNegative(e.target.value)}
              rows={2}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <button
              onClick={() => onDeleteStyle(selectedStyle.id, selectedStyle.name)}
              className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>刪除</span>
            </button>
            <button
              onClick={onSaveStyle}
              disabled={saving}
              className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" />
              <span>{saving ? "儲存中..." : "儲存變更"}</span>
            </button>
          </div>
        </aside>
      )}

      {/* 新增視覺風格 Modal */}
      {isCreateStyleOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-5 space-y-3.5">
            <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">新增視覺風格</h3>
              </div>
              <button onClick={() => setIsCreateStyleOpen(false)} className="text-cinema-muted hover:text-cinema-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">英文 ID</label>
                <input
                  type="text"
                  value={newStyleId}
                  onChange={(e) => setNewStyleId(e.target.value)}
                  placeholder="例如: makoto_watercolor"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">風格名稱</label>
                <input
                  type="text"
                  value={newStyleName}
                  onChange={(e) => setNewStyleName(e.target.value)}
                  placeholder="例如：水彩唯美風"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">風格描述</label>
              <textarea
                value={newStyleDesc}
                onChange={(e) => setNewStyleDesc(e.target.value)}
                rows={2}
                placeholder="簡述畫風特色..."
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
              />
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">正向前綴提示詞 (Style Prefix)</label>
              <textarea
                value={newStylePrompt}
                onChange={(e) => setNewStylePrompt(e.target.value)}
                rows={3}
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
              />
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">負向過濾詞 (Negative)</label>
              <textarea
                value={newStyleNegative}
                onChange={(e) => setNewStyleNegative(e.target.value)}
                rows={2}
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
              />
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">示範預覽圖 (選填)</label>
              <label className="flex items-center justify-center h-8 rounded border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-xs text-cinema-text cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
                <span>{newStylePreviewBase64 ? "已選取預覽圖" : "選取本機圖片"}</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const b64 = await fileToBase64(file);
                      setNewStylePreviewBase64(b64);
                    }
                  }}
                />
              </label>
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
              <button
                onClick={() => setIsCreateStyleOpen(false)}
                className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
              >
                取消
              </button>
              <button
                onClick={onCreateStyle}
                disabled={saving}
                className="px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow"
              >
                {saving ? "建立中..." : "確認建立"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
