import React, { useState } from "react";
import { CheckCircle2, Image as ImageIcon, Palette, Search, X } from "lucide-react";
import { AssetStyle } from "../types";

interface StyleGalleryModalProps {
  isOpen: boolean;
  styles: AssetStyle[];
  selectedStyle: string;
  onSelectStyle: (styleId: string) => void;
  onClose: () => void;
}

export const StyleGalleryModal: React.FC<StyleGalleryModalProps> = ({
  isOpen,
  styles,
  selectedStyle,
  onSelectStyle,
  onClose,
}) => {
  const [galleryFilter, setGalleryFilter] = useState("all");
  const [gallerySearch, setGallerySearch] = useState("");

  if (!isOpen) return null;

  const filteredStyles = styles.filter((s) => {
    const matchSearch =
      !gallerySearch.trim() ||
      s.name.toLowerCase().includes(gallerySearch.toLowerCase()) ||
      s.description.toLowerCase().includes(gallerySearch.toLowerCase()) ||
      s.id.toLowerCase().includes(gallerySearch.toLowerCase());

    if (!matchSearch) return false;

    if (galleryFilter === "anime") {
      return /動漫|卡通|熱血|鳥山|尾田|TRIGGER|ufotable/i.test(s.name + s.description);
    }
    if (galleryFilter === "aesthetic") {
      return /新海誠|吉卜力|京都動畫|CLAMP|高橋/i.test(s.name + s.description);
    }
    if (galleryFilter === "scifi") {
      return /大友克洋|士郎正宗|弐瓶勉|科幻|龐克|三浦/i.test(s.name + s.description);
    }
    if (galleryFilter === "art") {
      return /手塚|井上雄彥|天野喜孝|松本大洋|水彩|墨繪/i.test(s.name + s.description);
    }
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-5xl h-[85vh] flex flex-col rounded-xl bg-cinema-darker border border-cinema-border shadow-2xl overflow-hidden">
        {/* Modal 頂部 Header */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-cinema-border bg-cinema-card">
          <div className="flex items-center space-x-2">
            <Palette className="w-4 h-4 text-amber-cta" />
            <h3 className="text-sm font-semibold text-cinema-text">選擇視覺風格 ({styles.length})</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-cinema-cardHover text-cinema-muted hover:text-cinema-text transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 篩選與搜尋工具列 */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-3 border-b border-cinema-border/70 bg-cinema-bg">
          <div className="flex items-center space-x-1.5 text-xs overflow-x-auto w-full sm:w-auto">
            {[
              { id: "all", label: "全部風格" },
              { id: "anime", label: "動漫熱血" },
              { id: "aesthetic", label: "唯美日系" },
              { id: "scifi", label: "硬核科幻" },
              { id: "art", label: "藝術手繪" },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setGalleryFilter(f.id)}
                className={`px-3 py-1 rounded-md transition-colors shrink-0 ${
                  galleryFilter === f.id
                    ? "bg-amber-cta text-cinema-bg font-semibold"
                    : "bg-cinema-card text-cinema-muted hover:text-cinema-text"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 text-cinema-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="搜尋風格名稱或關鍵字..."
              value={gallerySearch}
              onChange={(e) => setGallerySearch(e.target.value)}
              className="w-full h-8 pl-8 pr-3 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>
        </div>

        {/* 網格展示區 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filteredStyles.map((s) => {
              const isSelected = selectedStyle === s.id;
              return (
                <div
                  key={s.id}
                  onClick={() => {
                    onSelectStyle(s.id);
                    onClose();
                  }}
                  className={`group rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all duration-200 ${
                    isSelected
                      ? "border-amber-cta ring-2 ring-amber-cta/50 shadow-lg glow-amber"
                      : "border-cinema-border hover:border-cinema-muted hover:-translate-y-1"
                  }`}
                >
                  <div className="relative aspect-video w-full bg-black/60 overflow-hidden">
                    {s.preview_url ? (
                      <img
                        src={s.preview_url}
                        alt={s.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-cinema-muted/40">
                        <ImageIcon className="w-8 h-8" />
                      </div>
                    )}

                    {isSelected && (
                      <div className="absolute top-2 right-2 p-1 rounded-full bg-black/80 text-amber-cta">
                        <CheckCircle2 className="w-5 h-5 fill-amber-cta text-black" />
                      </div>
                    )}

                    <div className="absolute bottom-2 left-2 flex space-x-1">
                      {s.tags?.map((t, idx) => (
                        <span key={idx} className="px-1.5 py-0.5 rounded bg-black/80 text-[10px] text-zinc-300">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="p-3">
                    <h4 className="text-xs font-semibold text-cinema-text truncate">{s.name}</h4>
                    <p className="mt-1 text-[11px] text-cinema-muted line-clamp-2 leading-relaxed">
                      {s.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
