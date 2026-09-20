import React, { useEffect, useState } from "react";
import { Sparkles, Image as ImageIcon, Volume2, BookOpen, X, Save } from "lucide-react";
import { api } from "../api";
import { AssetStyle, AssetTone, AssetVoice } from "../types";

export const AssetsView: React.FC = () => {
  const [tab, setTab] = useState<"tones" | "voices" | "styles">("styles");

  const [styles, setStyles] = useState<AssetStyle[]>([]);
  const [tones, setTones] = useState<AssetTone[]>([]);
  const [voices, setVoices] = useState<AssetVoice[]>([]);

  const [selectedStyle, setSelectedStyle] = useState<AssetStyle | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getStyles().then(setStyles).catch(() => {});
    api.getTones().then(setTones).catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
  }, []);

  const handleSelectStyle = (s: AssetStyle) => {
    setSelectedStyle(s);
    setEditPrompt(s.prefix || "");
    setEditDesc(s.description || "");
  };

  const handleSaveStyle = async () => {
    if (!selectedStyle) return;
    setSaving(true);
    try {
      await fetch(`/api/v1/assets/styles/${selectedStyle.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: selectedStyle.name,
          description: editDesc,
          prefix: editPrompt,
          negative: selectedStyle.negative,
        }),
      });
      alert("風格已成功儲存！");
      const updated = await api.getStyles();
      setStyles(updated);
    } catch (e: any) {
      alert("儲存失敗: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-cinema-bg">
      {/* 左主內容 */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">素材庫與風格資源</h2>
          <p className="text-xs text-cinema-muted">管理 AI 影片創作所需的視覺風格、說書人口吻與發音人音色。</p>
        </div>

        {/* Tab 切換 */}
        <div className="flex items-center space-x-1 border-b border-cinema-border pb-2 text-xs">
          <button
            onClick={() => setTab("tones")}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "tones" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            <span>口吻範本</span>
          </button>
          <button
            onClick={() => setTab("voices")}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "voices" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <Volume2 className="w-3.5 h-3.5 mr-1.5" />
            <span>發音人音色</span>
          </button>
          <button
            onClick={() => setTab("styles")}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "styles" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            <span>視覺風格</span>
          </button>
        </div>

        {/* 視覺風格卡片網格 */}
        {tab === "styles" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {styles.map((s) => (
              <div
                key={s.id}
                onClick={() => handleSelectStyle(s)}
                className={`group rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all ${
                  selectedStyle?.id === s.id ? "border-amber-cta ring-2 ring-amber-cta/30" : "border-cinema-border hover:border-cinema-muted"
                }`}
              >
                <div className="aspect-video w-full bg-black/50 overflow-hidden relative">
                  {s.preview_url ? (
                    <img src={s.preview_url} alt={s.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  ) : (
                    <ImageIcon className="w-8 h-8 m-auto text-cinema-muted/40" />
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
        )}

        {/* 口吻列表 */}
        {tab === "tones" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tones.map((t) => (
              <div key={t.id} className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-2">
                <h4 className="text-xs font-semibold text-amber-cta">{t.title}</h4>
                <p className="text-xs text-cinema-muted leading-relaxed">{t.summary}</p>
              </div>
            ))}
          </div>
        )}

        {/* 音色列表 */}
        {tab === "voices" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {voices.map((v) => (
              <div key={v.id} className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-2">
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-cinema-text">{v.name}</h4>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-cinema-darker text-cinema-muted border border-cinema-border">
                    {v.gender}
                  </span>
                </div>
                {v.reference_text && <p className="text-[11px] text-cinema-muted italic">「{v.reference_text}」</p>}
                {v.audio_sample_url && (
                  <audio controls src={v.audio_sample_url} className="w-full h-8 mt-2" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 右側編輯風格抽屜 */}
      {selectedStyle && tab === "styles" && (
        <aside className="w-[360px] h-full flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-4">
          <div className="flex justify-between items-center border-b border-cinema-border pb-3">
            <span className="text-xs font-semibold text-cinema-text">編輯風格</span>
            <button onClick={() => setSelectedStyle(null)} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="aspect-video w-full rounded bg-black/60 overflow-hidden border border-cinema-border">
            {selectedStyle.preview_url && (
              <img src={selectedStyle.preview_url} alt="" className="w-full h-full object-cover" />
            )}
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">名稱</label>
            <input
              type="text"
              readOnly
              value={selectedStyle.name}
              className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">描述</label>
            <textarea
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
              rows={2}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">前置提示詞 (Prompt Prefix)</label>
            <textarea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              rows={4}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <button
            onClick={handleSaveStyle}
            disabled={saving}
            className="w-full flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            <span>{saving ? "儲存中..." : "儲存變更"}</span>
          </button>
        </aside>
      )}
    </div>
  );
};
