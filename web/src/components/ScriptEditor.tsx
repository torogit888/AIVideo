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
  Film,
  Info,
  Plus,
  Trash2,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { AssetStyle, AssetTone, AssetVoice, AI_TEXT_MODELS } from "../types";

export const ScriptEditor: React.FC = () => {
  const { setTab, loadJobs, selectedJobId, jobs, showToast, selectedAiModel, setSelectedAiModel } = useStudioStore();
  const currentJob = jobs.find((j) => j.id === selectedJobId);

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
  const [visualPacing, setVisualPacing] = useState<"fast" | "balanced" | "slow">("balanced");

  // 視覺風格選取增強狀態
  const [isGalleryOpen, setIsGalleryOpen] = useState(false);
  const [galleryFilter, setGalleryFilter] = useState("all");
  const [gallerySearch, setGallerySearch] = useState("");
  const styleScrollRef = useRef<HTMLDivElement>(null);
  const scriptBoxRef = useRef<HTMLDivElement>(null);

  const [generating, setGenerating] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);

  // 視覺一致性主體分析狀態
  const [subjectAnchor, setSubjectAnchor] = useState("");
  const [environmentAnchor, setEnvironmentAnchor] = useState("");
  const [characters, setCharacters] = useState<{ id: string; name: string; appearance: string }[]>([]);
  const [isAnalyzingAnchors, setIsAnalyzingAnchors] = useState(false);
  const [showAnchors, setShowAnchors] = useState(false);

  useEffect(() => {
    api.getTones().then(setTones).catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
    api.getStyles().then(setStyles).catch(() => {});
  }, []);

  // 監聽專案發音人變更（從抽屜或故事板更改時即時同步）
  useEffect(() => {
    if (currentJob?.voice_id) {
      setSelectedVoice(currentJob.voice_id);
    }
  }, [currentJob?.voice_id]);

  // 切換不同專案時自動載入該專案的最新腳本內容與設定
  useEffect(() => {
    if (!selectedJobId) return;
    api
      .getJobDetail(selectedJobId)
      .then((detail) => {
        if (detail.title) setTopic(detail.title);
        if (detail.script_content) setScriptText(detail.script_content);
        if (detail.config?.voice_id) setSelectedVoice(detail.config.voice_id);
        if (detail.config?.image?.style) setSelectedStyle(detail.config.image.style);
      })
      .catch((e) => console.error("載入專案詳情失敗", e));
  }, [selectedJobId]);

  const handleVoiceChange = async (voiceId: string) => {
    setSelectedVoice(voiceId);
    if (selectedJobId) {
      try {
        await api.updateJob(selectedJobId, { voice_id: voiceId });
        await loadJobs();
      } catch (e: any) {
        console.error("更新發音人失敗", e);
      }
    }
  };

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
      const res = await api.generateScript(topic, selectedTone, wordCount, selectedAiModel);
      setScriptText(res.script);
      showToast("深度故事腳本生成完成！已自動移至下方預覽區", "success");
      // 生成完成後平滑滾動至預覽編輯框
      setTimeout(() => {
        scriptBoxRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 150);
    } catch (e: any) {
      showToast("生成失敗: " + e.message, "error");
    } finally {
      setGenerating(false);
    }
  };

  const handleAnalyzeAnchors = async () => {
    if (!scriptText.trim()) {
      showToast("請先生成或填寫腳本口白！", "error");
      return;
    }
    setIsAnalyzingAnchors(true);
    try {
      const res = await api.analyzeAnchors(topic, scriptText, selectedStyle);
      const nextChars = (res.characters || []).map((c, i) => ({
        id: c.id || `char_${i + 1}`,
        name: c.name || `角色 ${i + 1}`,
        appearance: c.appearance || "",
      }));
      setCharacters(
        nextChars.length
          ? nextChars
          : res.subject_anchor
            ? [{ id: "main", name: "Main Subject", appearance: res.subject_anchor }]
            : []
      );
      setSubjectAnchor(res.subject_anchor || "");
      setEnvironmentAnchor(res.environment_anchor || "");
      setShowAnchors(true);
      showToast("✨ 已依目前生圖風格分析腳本，提煉出各角色外觀與環境光影。", "success");
    } catch (e: any) {
      showToast("分析視覺錨點失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsAnalyzingAnchors(false);
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
        visual_pacing: visualPacing,
        subject_anchor: subjectAnchor.trim() || undefined,
        environment_anchor: environmentAnchor.trim() || undefined,
        characters: characters
          .filter((c) => c.name.trim() || c.appearance.trim())
          .map((c) => ({ id: c.id, name: c.name.trim(), appearance: c.appearance.trim() })),
      });
      await loadJobs();
      useStudioStore.getState().selectJob(res.id);
      showToast(`專案【${topic}】建立成功！`, "success");
      setTab("storyboard");
    } catch (e: any) {
      showToast("建立專案失敗: " + e.message, "error");
    } finally {
      setCreatingProject(false);
    }
  };

  // 腳本逐行分割
  const scriptLines = scriptText.split("\n");
  const totalChars = scriptText.replace(/\s/g, "").length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 max-w-5xl mx-auto space-y-5">
      {/* 標題與引導說明 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">故事發想與腳本創作</h2>
          <p className="text-xs text-cinema-muted">
            設定故事主題與各項規格，於下方生成深度腳本並直接預覽編輯，滿意後一鍵進入分鏡。
          </p>
        </div>
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

      {/* 說書人口吻、發音人與 AI 核心模型 (三欄) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 口吻選擇 */}
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">說書人口吻風格</label>
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
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs font-medium text-cinema-muted">專案發音人 (OmniVoice)</label>
            {selectedJobId && (
              <span className="text-[10px] text-amber-cta/80 font-mono">已同步</span>
            )}
          </div>
          <select
            value={selectedVoice}
            onChange={(e) => handleVoiceChange(e.target.value)}
            className="w-full h-9 px-3 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta cursor-pointer"
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.gender})
              </option>
            ))}
          </select>
        </div>

        {/* AI 創作核心模型選擇 */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs font-medium text-cinema-muted">AI 創作核心模型</label>
            <span className="text-[10px] text-amber-cta font-mono">⚡ Vertex AI</span>
          </div>
          <select
            value={selectedAiModel}
            onChange={(e) => {
              setSelectedAiModel(e.target.value);
              const m = AI_TEXT_MODELS.find((item) => item.id === e.target.value);
              if (m) showToast(`已切換核心 AI 模型為 ${m.name}`, "info");
            }}
            className="w-full h-9 px-3 rounded bg-cinema-card border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium focus:outline-none focus:border-amber-cta cursor-pointer"
          >
            {AI_TEXT_MODELS.map((m) => (
              <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text">
                {m.name} ({m.tag})
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

      {/* 腳本內容即時預覽與編輯器（帶行號） */}
      <div
        ref={scriptBoxRef}
        className="flex flex-col min-h-[380px] shrink-0 rounded-lg bg-cinema-card border border-cinema-border overflow-hidden transition-all shadow-md"
      >
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-cinema-border/60 text-xs bg-cinema-darker/60">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-cinema-text">📖 故事腳本即時預覽與編輯區</span>
            <span className="text-[10px] text-cinema-muted">（每行一句話，可直接在此微調）</span>
          </div>
          <div className="flex items-center space-x-3 text-cinema-muted text-xs">
            <span className="font-mono text-amber-cta font-medium">
              {scriptLines.filter((l) => l.trim()).length} 句口白 · 共 {totalChars} 字
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(scriptText);
                showToast("已複製腳本內容至剪貼簿！", "info");
              }}
              className="flex items-center hover:text-cinema-text transition-colors text-xs text-cinema-muted"
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

      {/* 視覺切鏡節奏 (Visual Pacing) */}
      <div className="space-y-2 p-3.5 rounded-lg bg-cinema-card border border-cinema-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Film className="w-4 h-4 text-amber-cta" />
            <label className="text-xs font-semibold text-cinema-text">視覺切鏡節奏 (AI 智能語意分鏡)</label>
          </div>
          <span className="text-[11px] text-cinema-muted">
            由 AI 依據情節單元與視覺轉折自動決定段落合併，並參考此節奏
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {[
            {
              id: "fast" as const,
              icon: "🚀",
              title: "緊湊快節奏",
              badge: "約 1~2 句 / 圖",
              desc: "頻繁變換特寫與視角，適合緊張懸念、動作衝突或名場面反轉",
            },
            {
              id: "balanced" as const,
              icon: "🎬",
              title: "標準電影感",
              badge: "約 2~4 句 / 圖（推薦）",
              desc: "依情節單元與時空變換自然切鏡，兼顧視覺舒適度與觀看沉浸感",
            },
            {
              id: "slow" as const,
              icon: "☕",
              title: "沉浸長鏡頭",
              badge: "約 3~5 句 / 圖",
              desc: "宏觀大遠景與慢速推拉，適合歷史紀錄、深空宇宙或深沉思考",
            },
          ].map((p) => {
            const isSelected = visualPacing === p.id;
            return (
              <div
                key={p.id}
                onClick={() => setVisualPacing(p.id)}
                className={`p-2.5 rounded-md border cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? "bg-amber-cta/10 border-amber-cta text-cinema-text shadow-sm"
                    : "bg-cinema-darker/60 border-cinema-border/70 text-cinema-muted hover:border-cinema-muted hover:text-cinema-text"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5 font-medium text-xs">
                    <span>{p.icon}</span>
                    <span className={isSelected ? "text-amber-cta font-semibold" : ""}>{p.title}</span>
                  </div>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isSelected
                        ? "bg-amber-cta text-cinema-bg font-bold"
                        : "bg-cinema-card border border-cinema-border text-cinema-muted"
                    }`}
                  >
                    {p.badge}
                  </span>
                </div>
                <div className="text-[11px] leading-relaxed opacity-80">{p.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 主體一致性與角色特徵分析 (Pre-production Character & Entity Bible) */}
      <div className="p-4 rounded-lg bg-cinema-card border border-cinema-border space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cinema-border/50 pb-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-cta" />
            <div>
              <span className="text-xs font-semibold text-cinema-text">
                🎭 視覺一致性特徵分析 (Character & Entity Bible)
              </span>
              <p className="text-[11px] text-cinema-muted">
                依上方選擇的生圖風格掃描腳本，為每位角色寫外觀錨點，並提煉世界觀光影。
              </p>
            </div>
          </div>
          <button
            onClick={handleAnalyzeAnchors}
            disabled={isAnalyzingAnchors || !scriptText.trim()}
            className="flex items-center justify-center h-8 px-3 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-40 cursor-pointer"
          >
            {isAnalyzingAnchors ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                <span>分析腳本中...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>{characters.length || subjectAnchor ? "重新分析主體與風格" : "✨ AI 分析腳本主體與世界觀"}</span>
              </>
            )}
          </button>
        </div>

        {/* 展開之錨點編輯區：每人一段外觀 + 共用環境 */}
        {(showAnchors || subjectAnchor || characters.length > 0) && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-cinema-muted">
                角色外觀錨點（每人獨立，建案後可各出一張定裝圖）
              </label>
              <button
                type="button"
                onClick={() =>
                  setCharacters((prev) => [
                    ...prev,
                    { id: `char_${prev.length + 1}`, name: "", appearance: "" },
                  ])
                }
                className="flex items-center h-7 px-2 rounded bg-cinema-darker hover:bg-cinema-card text-cinema-muted hover:text-amber-cta text-[11px] border border-cinema-border"
              >
                <Plus className="w-3 h-3 mr-1" />
                新增角色
              </button>
            </div>
            {characters.length === 0 && (
              <p className="text-[11px] text-cinema-muted">尚無角色。可點「新增角色」或重新分析腳本。</p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {characters.map((ch, idx) => (
                <div key={ch.id + idx} className="p-2.5 rounded bg-cinema-darker border border-cinema-border/80 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <input
                      value={ch.name}
                      onChange={(e) =>
                        setCharacters((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, name: e.target.value } : x))
                        )
                      }
                      placeholder={`角色 ${idx + 1} 名稱`}
                      className="flex-1 h-7 px-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                    />
                    <button
                      type="button"
                      onClick={() => setCharacters((prev) => prev.filter((_, i) => i !== idx))}
                      className="p-1 rounded text-cinema-muted hover:text-red-400"
                      title="移除此角色"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={ch.appearance}
                    onChange={(e) =>
                      setCharacters((prev) =>
                        prev.map((x, i) => (i === idx ? { ...x, appearance: e.target.value } : x))
                      )
                    }
                    placeholder="此角色在目前生圖風格下的臉、髮、體型、服裝配色..."
                    className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
                  />
                </div>
              ))}
            </div>
            <div>
              <label className="block text-xs font-medium text-cinema-muted mb-1">
                環境與光影基調錨點（全片共用，依生圖風格書寫）
              </label>
              <textarea
                rows={3}
                value={environmentAnchor}
                onChange={(e) => setEnvironmentAnchor(e.target.value)}
                placeholder="此風格下的時代氛圍、空間構造、光影與材質..."
                className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
              />
            </div>
          </div>
        )}

        {!showAnchors && !subjectAnchor && (
          <div className="text-[11px] text-cinema-muted/70 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-amber-cta/70 shrink-0" />
            <span>點擊上方按鈕可預先檢視並微調主體特徵；若直接建立專案，系統亦會在後台自動進行分析約束。</span>
          </div>
        )}
      </div>

      {/* 底部控制台：腳本生成與進入分鏡 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between p-4 rounded-lg bg-cinema-card border border-cinema-border gap-4">
        <div>
          <div className="text-xs font-semibold text-cinema-text">準備進入分鏡工作台</div>
          <div className="text-[11px] text-cinema-muted mt-0.5">
            填寫主題與設定後，先點擊「生成腳本」由 AI 聯網生成口白預覽；確認內容無誤後，即可點擊「建立專案並進入分鏡」。
          </div>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          {/* 生成腳本按鈕 */}
          <button
            onClick={handleGenerateScript}
            disabled={generating || !topic.trim()}
            className="flex items-center h-9 px-4 rounded bg-cinema-darker hover:bg-cinema-cardHover border border-amber-cta/60 hover:border-amber-cta text-amber-cta font-medium text-xs tracking-wide transition-all shadow-sm active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
            title={!topic.trim() ? "請先填寫腳本主題" : "由 AI 聯網生成逐句口白腳本並於上方預覽"}
          >
            {generating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                <span>生成中 (需 15~30s)...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                <span>{scriptText.trim() ? "重新生成腳本" : "✨ 生成腳本"}</span>
              </>
            )}
          </button>

          {/* 建立專案並進入分鏡（沒有腳本時反灰） */}
          <button
            onClick={handleCreateProject}
            disabled={creatingProject || generating || !scriptText.trim()}
            className={`flex items-center h-9 px-4 rounded font-semibold text-xs tracking-wide transition-all ${
              !scriptText.trim()
                ? "bg-cinema-darker border border-cinema-border/70 text-cinema-muted/40 cursor-not-allowed opacity-40 shadow-none"
                : "bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg shadow glow-amber active:scale-95 disabled:opacity-50"
            }`}
            title={!scriptText.trim() ? "目前尚無腳本，請先點擊「生成腳本」或於上方手動輸入口白" : "建立專案並進入分鏡"}
          >
            {creatingProject ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                <span>解析分鏡中...</span>
              </>
            ) : (
              <>
                <span>建立專案並進入分鏡</span>
                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </>
            )}
          </button>
        </div>
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
