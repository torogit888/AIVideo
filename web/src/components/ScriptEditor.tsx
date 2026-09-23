import React, { useEffect, useState, useRef } from "react";
import {
  Sparkles,
  Copy,
  ArrowRight,
  Loader2,
  Image as ImageIcon,
  Palette,
  ChevronLeft,
  ChevronRight,
  Grid,
  CheckCircle2,
  X,
  Search,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { AssetStyle, AssetTone, AssetVoice } from "../types";

export const ScriptEditor: React.FC = () => {
  const { setTab, loadJobs } = useStudioStore();

  const [topic, setTopic] = useState("美國太空總署羅曼太空望遠鏡的秘密");
  const [scriptText, setScriptText] = useState(
    "如果你今天想看清整個宇宙最深處的終極秘密！\n你敢相信……NASA 接下來最強大的宇宙神鏡，它的心臟……居然是來自軍方情報機構淘汰不要的間諜衛星嗎？\n這不是地攤文學，這是貨真價實的航太傳奇。\n2012 年，美國國家偵察局突然打電話給 NASA，詢問要不要兩顆頂級哈勃等級望遠鏡鏡片。\n天文學家興奮得手舞足蹈，一場顛覆天文觀測的壯麗計畫就此展開……"
  );
  const [wordCount, setWordCount] = useState(1500);

  const [tones, setTones] = useState<AssetTone[]>([]);
  const [voices, setVoices] = useState<AssetVoice[]>([]);
  const [styles, setStyles] = useState<AssetStyle[]>([]);

  const [selectedTone, setSelectedTone] = useState("tech_business_deepdive");
  const [selectedVoice, setSelectedVoice] = useState("female01");
  const [selectedStyle, setSelectedStyle] = useState("otomo_katsuhiro");

  // 視覺風格選取增強狀態
  const [isGalleryOpen, setIsGalleryOpen] = useState(false);
  const [galleryFilter, setGalleryFilter] = useState("all");
  const [gallerySearch, setGallerySearch] = useState("");
  const styleScrollRef = useRef<HTMLDivElement>(null);

  const [generating, setGenerating] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);

  useEffect(() => {
    api.getTones().then(setTones).catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
    api.getStyles().then(setStyles).catch(() => {});
  }, []);

  const currentStyleObj = styles.find((s) => s.id === selectedStyle) || styles[0];

  const handleScrollStyles = (direction: "left" | "right") => {
    if (styleScrollRef.current) {
      const offset = direction === "left" ? -340 : 340;
      styleScrollRef.current.scrollBy({ left: offset, behavior: "smooth" });
    }
  };

  // 畫廊篩選
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

  const handleGenerateScript = async () => {
    if (!topic.trim()) return;
    setGenerating(true);
    try {
      const res = await api.generateScript(topic, selectedTone, wordCount);
      setScriptText(res.script);
    } catch (e: any) {
      alert("生成失敗: " + e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCreateProject = async () => {
    if (!scriptText.trim()) return;
    setCreatingProject(true);
    try {
      const res = await api.createJob({
        topic,
        script: scriptText,
        tone_id: selectedTone,
        voice_id: selectedVoice,
        style_id: selectedStyle,
        lines_per_scene: 2,
      });
      await loadJobs();
      useStudioStore.getState().selectJob(res.id);
      setTab("storyboard");
    } catch (e: any) {
      alert("建立專案失敗: " + e.message);
    } finally {
      setCreatingProject(false);
    }
  };

  // 腳本逐行分割
  const scriptLines = scriptText.split("\n");
  const totalChars = scriptText.replace(/\s/g, "").length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 max-w-5xl mx-auto space-y-5">
      {/* 標題與唯一實心主按鈕 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">故事發想與腳本創作</h2>
          <p className="text-xs text-cinema-muted">
            透過 Gemini 深度聯網搜集資料，套用專業說書人口吻，生成逐行口白腳本。
          </p>
        </div>
        <button
          onClick={handleGenerateScript}
          disabled={generating}
          className="flex items-center h-9 px-5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow glow-amber active:scale-95 disabled:opacity-50"
        >
          {generating ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
              <span>生成中 (需 15~30s)...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
              <span>生成腳本</span>
            </>
          )}
        </button>
      </div>

      {/* 故事主題與字數規模 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">腳本主題</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full h-10 px-3 rounded-md bg-cinema-card border border-cinema-border text-sm text-cinema-text focus:outline-none focus:border-amber-cta"
            placeholder="例如：光刻機霸主艾司摩爾的崛起傳奇、旅行者號金唱片的孤獨旅程"
          />
        </div>
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs font-medium text-cinema-muted">目標字數規模</label>
            <span className="text-xs font-mono text-amber-cta">{wordCount} 字 (約 {Math.round(wordCount / 220)} 分鐘)</span>
          </div>
          <input
            type="range"
            min={300}
            max={5000}
            step={100}
            value={wordCount}
            onChange={(e) => setWordCount(Number(e.target.value))}
            className="w-full accent-amber-cta cursor-pointer h-10"
          />
        </div>
      </div>

      {/* 說書人口吻與發音人 (兩欄) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 口吻選擇 */}
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">說書人口吻</label>
          <select
            value={selectedTone}
            onChange={(e) => setSelectedTone(e.target.value)}
            className="w-full h-9 px-3 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
          >
            {tones.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </div>

        {/* 發音人選擇 */}
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">發音人</label>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="w-full h-9 px-3 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.gender})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 電影級視覺分鏡風格膠卷選擇器 */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Palette className="w-4 h-4 text-amber-cta" />
            <label className="text-xs font-semibold text-cinema-text">視覺分鏡風格</label>
            <span className="text-[11px] text-amber-cta font-medium bg-amber-cta/10 px-2 py-0.5 rounded border border-amber-cta/20">
              {currentStyleObj?.name || "尚未選擇"}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsGalleryOpen(true)}
              className="flex items-center text-xs text-cinema-muted hover:text-amber-cta transition-colors px-2.5 py-1 rounded bg-cinema-card border border-cinema-border hover:border-cinema-muted"
            >
              <Grid className="w-3.5 h-3.5 mr-1.5" />
              <span>瀏覽風格畫廊 ({styles.length})</span>
            </button>
            <div className="flex items-center space-x-1">
              <button
                onClick={() => handleScrollStyles("left")}
                className="p-1 rounded bg-cinema-card border border-cinema-border text-cinema-muted hover:text-cinema-text transition-colors"
                title="向左滑動"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleScrollStyles("right")}
                className="p-1 rounded bg-cinema-card border border-cinema-border text-cinema-muted hover:text-cinema-text transition-colors"
                title="向右滑動"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* 橫向風格卡片滑動列 */}
        <div
          ref={styleScrollRef}
          className="flex space-x-3 overflow-x-auto pb-2 pt-1 scroll-smooth"
        >
          {styles.map((s) => {
            const isSelected = selectedStyle === s.id;
            return (
              <div
                key={s.id}
                onClick={() => setSelectedStyle(s.id)}
                className={`group w-44 shrink-0 rounded-lg bg-cinema-card border overflow-hidden cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? "border-amber-cta ring-2 ring-amber-cta/40 shadow-lg glow-amber scale-[1.02]"
                    : "border-cinema-border hover:border-cinema-muted hover:-translate-y-0.5"
                }`}
              >
                {/* 16:9 圖片縮圖 */}
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
                      <ImageIcon className="w-6 h-6" />
                    </div>
                  )}

                  {isSelected && (
                    <div className="absolute top-1.5 right-1.5 p-0.5 rounded-full bg-black/80 text-amber-cta">
                      <CheckCircle2 className="w-4 h-4 fill-amber-cta text-black" />
                    </div>
                  )}

                  {s.tags && s.tags[0] && (
                    <div className="absolute bottom-1 left-1.5 px-1.5 py-0.5 rounded bg-black/75 text-[9px] text-zinc-300">
                      {s.tags[0]}
                    </div>
                  )}
                </div>

                <div className="p-2.5">
                  <h4 className="text-xs font-semibold text-cinema-text truncate" title={s.name}>
                    {s.name}
                  </h4>
                  <p className="mt-0.5 text-[10px] text-cinema-muted line-clamp-1" title={s.description}>
                    {s.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* 選中風格詳細解構卡 */}
        {currentStyleObj && (
          <div className="p-3 rounded-lg bg-cinema-card border border-cinema-border/70 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-amber-cta">{currentStyleObj.name}</span>
                <span className="text-[10px] font-mono text-cinema-muted">({currentStyleObj.id})</span>
              </div>
              <p className="text-[11px] text-cinema-muted leading-relaxed line-clamp-2">
                {currentStyleObj.description}
              </p>
            </div>
            <div className="text-[10px] font-mono bg-cinema-darker p-2 rounded border border-cinema-border/60 text-zinc-400 max-w-sm truncate shrink-0">
              <span className="text-amber-cta/80 font-sans mr-1">風格關鍵詞:</span>
              {currentStyleObj.prefix}
            </div>
          </div>
        )}
      </div>

      {/* 腳本內容編輯器（帶行號） */}
      <div className="flex-1 flex flex-col rounded-lg bg-cinema-card border border-cinema-border overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-cinema-border/60 text-xs">
          <span className="font-medium text-cinema-text">口白腳本內容 (每行一句話)</span>
          <div className="flex items-center space-x-3 text-cinema-muted text-xs">
            <span className="font-mono">{totalChars} 字</span>
            <button
              onClick={() => navigator.clipboard.writeText(scriptText)}
              className="flex items-center hover:text-cinema-text transition-colors"
            >
              <Copy className="w-3.5 h-3.5 mr-1" />
              <span>複製</span>
            </button>
          </div>
        </div>

        {/* 編輯器容器 */}
        <div className="flex flex-1 min-h-[320px] p-2 bg-cinema-darker overflow-hidden">
          {/* 行號欄 */}
          <div className="w-8 py-1 text-right pr-2 text-cinema-muted/40 font-mono text-xs select-none leading-relaxed">
            {scriptLines.map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
          {/* 文字編輯區 */}
          <textarea
            value={scriptText}
            onChange={(e) => setScriptText(e.target.value)}
            className="flex-1 p-1 bg-transparent text-cinema-text text-xs font-sans leading-relaxed focus:outline-none resize-none"
            placeholder="貼上或撰寫逐句口白..."
          />
        </div>
      </div>

      {/* 建立專案卡片 */}
      <div className="flex items-center justify-between p-4 rounded-lg bg-cinema-card border border-cinema-border">
        <div>
          <div className="text-xs font-semibold text-cinema-text">準備進入分鏡工作台</div>
          <div className="text-[11px] text-cinema-muted">
            系統將自動擷取故事視覺錨點，按每 2 句口白切分為一幕分鏡，並生成英文提示詞。
          </div>
        </div>
        <button
          onClick={handleCreateProject}
          disabled={creatingProject || !scriptText.trim()}
          className="flex items-center h-9 px-4 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all disabled:opacity-50"
        >
          {creatingProject ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
              <span>解析中...</span>
            </>
          ) : (
            <>
              <span>建立專案並進入分鏡</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </>
          )}
        </button>
      </div>

      {/* 全螢幕視覺風格畫廊彈窗 */}
      {isGalleryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-5xl h-[85vh] flex flex-col rounded-xl bg-cinema-darker border border-cinema-border shadow-2xl overflow-hidden">
            {/* Modal 頂部 Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-cinema-border bg-cinema-card">
              <div className="flex items-center space-x-2.5">
                <Palette className="w-5 h-5 text-amber-cta" />
                <div>
                  <h3 className="text-sm font-semibold text-cinema-text">視覺分鏡風格畫廊</h3>
                  <p className="text-[11px] text-cinema-muted">
                    點選任一風格卡片即可立即套用（目前共收錄 {styles.length} 款大師級視覺美學）
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsGalleryOpen(false)}
                className="p-1.5 rounded-lg hover:bg-cinema-cardHover text-cinema-muted hover:text-cinema-text transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 篩選與搜尋工具列 */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-3 border-b border-cinema-border/70 bg-cinema-bg">
              {/* 分類標籤 */}
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

              {/* 搜尋框 */}
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
                        setSelectedStyle(s.id);
                        setIsGalleryOpen(false);
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
      )}
    </div>
  );
};
