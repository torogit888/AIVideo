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
  FileText,
  ChevronDown,
  ChevronUp,
  Save,
  Wand2,
} from "lucide-react";
import { useStudioStore } from "../store";
import { api } from "../api";
import { AssetStyle, AssetTone, AssetVoice } from "../types";
import { asciiSlug, DEFAULT_VOICE_ID, scriptWorkspaceMode } from "../studioActions";

export const ScriptEditor: React.FC = () => {
  const { setTab, loadJobs, selectedJobId, jobs, showToast, selectedAiModel, startNewDraft } = useStudioStore();
  const currentJob = jobs.find((j) => j.id === selectedJobId);
  const workspaceMode = scriptWorkspaceMode(selectedJobId);
  const isEditMode = workspaceMode === "edit";

  const [topic, setTopic] = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);
  const [outlineNotes, setOutlineNotes] = useState("");
  const [showOutlineBox, setShowOutlineBox] = useState(false);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [isExpandingScript, setIsExpandingScript] = useState(false);

  const [scriptText, setScriptText] = useState("");
  const [savedScript, setSavedScript] = useState("");
  const [isRecutting, setIsRecutting] = useState(false);
  const [wordCount, setWordCount] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("aivideo_target_word_count");
      if (saved && !isNaN(Number(saved))) {
        return Number(saved);
      }
    }
    return 1500;
  });

  const [tones, setTones] = useState<AssetTone[]>([]);
  const [voices, setVoices] = useState<AssetVoice[]>([]);
  const [styles, setStyles] = useState<AssetStyle[]>([]);

  const [selectedTone, setSelectedTone] = useState("michelin_curious");
  const [selectedVoice, setSelectedVoice] = useState(DEFAULT_VOICE_ID);
  const [jobSlug, setJobSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
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
  const [isSavingOutlinePrompt, setIsSavingOutlinePrompt] = useState(false);

  // 視覺一致性主體分析狀態
  const [subjectAnchor, setSubjectAnchor] = useState("");
  const [environmentAnchor, setEnvironmentAnchor] = useState("");
  const [characters, setCharacters] = useState<{ id: string; name: string; appearance: string }[]>([]);
  const [isAnalyzingAnchors, setIsAnalyzingAnchors] = useState(false);
  const [showAnchors, setShowAnchors] = useState(false);
  const [metaphorStyle, setMetaphorStyle] = useState<"fantasy" | "vintage_realistic" | "symbolic">("fantasy");

  useEffect(() => {
    api
      .getTones()
      .then((list) => {
        setTones(list);
        if (list.length > 0) {
          setSelectedTone((prev) => (list.some((t) => t.id === prev) ? prev : list[0].id));
        }
      })
      .catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
    api.getStyles().then(setStyles).catch(() => {});
  }, []);

  // 監聽專案發音人變更（從抽屜或故事板更改時即時同步）
  useEffect(() => {
    if (currentJob?.voice_id) {
      setSelectedVoice(currentJob.voice_id);
    }
  }, [currentJob?.voice_id]);

  // 切換不同專案時自動載入該專案的最新腳本內容與設定（含指定 Prompt 與 6 幕大綱）
  useEffect(() => {
    if (!selectedJobId) {
      setTopic("");
      setScriptText("");
      setSavedScript("");
      setJobSlug("");
      setSlugTouched(false);
      setShowCustomPrompt(false);
      setShowOutlineBox(false);
      setShowAnchors(false);
      const draftPrompt = localStorage.getItem("aivideo_draft_custom_prompt") || "";
      const draftOutline = localStorage.getItem("aivideo_draft_outline") || "";
      setCustomPrompt(draftPrompt);
      setOutlineNotes(draftOutline);
      return;
    }
    api
      .getJobDetail(selectedJobId)
      .then((detail) => {
        if (detail.title) setTopic(detail.title);
        const sc = detail.script_content || "";
        if (sc) {
          setScriptText(sc);
          setSavedScript(sc);
        }
        if (detail.config?.voice_id) setSelectedVoice(detail.config.voice_id);
        if (detail.config?.image?.style) setSelectedStyle(detail.config.image.style);
        if (detail.config?.tone_id) setSelectedTone(detail.config.tone_id);
        if (detail.config?.metaphor_style) setMetaphorStyle(detail.config.metaphor_style as any);

        const savedPrompt = detail.custom_prompt || detail.config?.custom_prompt || "";
        setCustomPrompt(savedPrompt);
        const savedOutline = detail.outline || detail.config?.outline || "";
        setOutlineNotes(savedOutline);
      })
      .catch((e) => console.error("載入專案詳情失敗", e));
  }, [selectedJobId]);

  // 儲存或同步指定 Prompt 與 6 幕大綱
  const persistPromptAndOutline = async (
    promptVal: string,
    outlineVal: string,
    silent: boolean = false
  ) => {
    setIsSavingOutlinePrompt(true);
    try {
      if (selectedJobId) {
        await api.updateJob(selectedJobId, {
          custom_prompt: promptVal,
          outline: outlineVal,
        });
        if (!silent) showToast("已儲存故事要求與大綱", "success");
      } else {
        localStorage.setItem("aivideo_draft_custom_prompt", promptVal);
        localStorage.setItem("aivideo_draft_outline", outlineVal);
        if (!silent) showToast("已儲存故事要求與大綱至本機草稿", "success");
      }
    } catch (e: any) {
      if (!silent) showToast("儲存失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setIsSavingOutlinePrompt(false);
    }
  };

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

  const handleGenerateOutline = async () => {
    if (!topic.trim()) {
      showToast("請先輸入腳本主題！", "error");
      return;
    }
    setIsGeneratingOutline(true);
    try {
      const res = await api.generateOutline(
        topic,
        selectedTone,
        selectedAiModel,
        customPrompt.trim() || undefined
      );
      setOutlineNotes(res.outline);
      setShowOutlineBox(true);
      // 自動持久化儲存大綱與指定 Prompt
      await persistPromptAndOutline(customPrompt, res.outline, true);
      showToast(
        customPrompt.trim()
          ? "已緊扣指定 Prompt 規劃出 6 幕深度大綱，並已自動儲存！"
          : "AI 6 幕深度大綱規劃完成，並已自動儲存！可微調後生成逐句台詞",
        "success"
      );
    } catch (e: any) {
      showToast("大綱規劃失敗: " + e.message, "error");
    } finally {
      setIsGeneratingOutline(false);
    }
  };

  const handleGenerateScript = async () => {
    if (!topic.trim()) return;
    setGenerating(true);
    try {
      const res = await api.generateScript(
        topic,
        selectedTone,
        wordCount,
        selectedAiModel,
        outlineNotes.trim() || undefined,
        customPrompt.trim() || undefined
      );
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

  const handleExpandScript = async () => {
    if (!scriptText.trim()) {
      showToast("目前尚無腳本內容可供擴寫！", "error");
      return;
    }
    setIsExpandingScript(true);
    try {
      // 若目前字數尚未達到使用者設定的 wordCount，以 wordCount 為目標精準補足；
      // 若目前字數已達到或超越設定值，則依現有長度微幅擴展 20%
      const currentWords = scriptText.replace(/\s/g, "").length;
      const targetWords = currentWords < wordCount ? wordCount : Math.round(currentWords * 1.2);

      const res = await api.expandScript(
        scriptText,
        topic,
        selectedTone,
        targetWords,
        selectedAiModel
      );
      setScriptText(res.script);
      showToast(`腳本情節深度擴寫完成！目標精準控制在約 ${targetWords} 字`, "success");
    } catch (e: any) {
      showToast("情節擴寫失敗: " + e.message, "error");
    } finally {
      setIsExpandingScript(false);
    }
  };

  // 智慧斷句排版：將長句子自動拆解為「一句一行」（約 15~25 字）
  const handleAutoFormatScript = () => {
    if (!scriptText.trim()) return;
    const lines: string[] = [];
    const preSplit = scriptText.replace(/[。；]/g, "\n").split("\n");
    for (const rawLine of preSplit) {
      let line = rawLine.trim();
      if (!line) continue;
      line = line
        .replace(/[「」『』\"'“”‘’《》〈〉（）()]/g, "")
        .replace(/[、：:]/g, "，")
        .replace(/[—…]+/g, "，")
        .replace(/！+/g, "！")
        .replace(/？+/g, "？")
        .replace(/，+/g, "，")
        .replace(/^[，,]+/, "")
        .trim();
      if (!line) continue;

      if (line.length <= 30 || !line.includes("，")) {
        lines.push(line);
      } else {
        const parts = line.split("，").map((p) => p.trim()).filter(Boolean);
        let currentChunk = "";
        for (const p of parts) {
          if (!currentChunk) {
            currentChunk = p;
          } else if (currentChunk.length + p.length + 1 <= 30) {
            currentChunk += "，" + p;
          } else {
            lines.push(currentChunk + "，");
            currentChunk = p;
          }
        }
        if (currentChunk) lines.push(currentChunk);
      }
    }
    const formatted = lines.join("\n");
    setScriptText(formatted);
    showToast("✨ 已完成智慧斷句排版，每行呈現一句獨立口白！", "success");
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
        slug: (jobSlug.trim() || asciiSlug(topic)),
        script: scriptText,
        tone_id: selectedTone,
        voice_id: selectedVoice,
        style_id: selectedStyle,
        image_model: useStudioStore.getState().selectedImageModel,
        visual_pacing: visualPacing,
        subject_anchor: subjectAnchor.trim() || undefined,
        environment_anchor: environmentAnchor.trim() || undefined,
        characters: characters
          .filter((c) => c.name.trim() || c.appearance.trim())
          .map((c) => ({ id: c.id, name: c.name.trim(), appearance: c.appearance.trim() })),
        custom_prompt: customPrompt.trim() || undefined,
        outline: outlineNotes.trim() || undefined,
        use_pip: true,
        metaphor_style: metaphorStyle,
      });
      // 成功建案後清理本機草稿快取
      localStorage.removeItem("aivideo_draft_custom_prompt");
      localStorage.removeItem("aivideo_draft_outline");
      await loadJobs();
      useStudioStore.getState().selectJob(res.id);
      showToast(`專案【${topic}】建立成功`, "success");
      setTab("storyboard");
    } catch (e: any) {
      showToast("建立專案失敗: " + e.message, "error");
    } finally {
      setCreatingProject(false);
    }
  };

  const handleSaveExisting = async () => {
    if (!selectedJobId || !scriptText.trim()) return;
    setCreatingProject(true);
    try {
      const validChars = characters
        .filter((c) => c.name.trim() || c.appearance.trim())
        .map((c) => ({ id: c.id, name: c.name.trim(), appearance: c.appearance.trim() }));

      await api.updateJob(selectedJobId, {
        title: topic,
        voice_id: selectedVoice,
        style_id: selectedStyle,
        tone_id: selectedTone,
        script: scriptText,
        custom_prompt: customPrompt.trim() || undefined,
        outline: outlineNotes.trim() || undefined,
        subject_anchor: subjectAnchor.trim() || undefined,
        environment_anchor: environmentAnchor.trim() || undefined,
        characters: validChars.length ? validChars : undefined,
        metaphor_style: metaphorStyle,
      });
      setSavedScript(scriptText);
      await loadJobs();
      const hasScenes = (currentJob?.progress.scenes_count || 0) > 0;
      const recut =
        hasScenes &&
        scriptText !== savedScript &&
        window.confirm("口白已寫回此專案。要依新口白重切分鏡嗎？既有 takes 會依同鏡頭 id 保留。");
      if (recut) {
        setIsRecutting(true);
        await api.recutJob(selectedJobId, { script: scriptText, visual_pacing: visualPacing, metaphor_style: metaphorStyle });
        await loadJobs();
        showToast("已儲存並重切分鏡", "success");
        setTab("storyboard");
      } else {
        // 若未重切分鏡，但有分鏡且更新了定裝或風格，提醒或自動同步 Prompt
        if (hasScenes && validChars.length > 0) {
          try {
            await api.syncScenePrompts(selectedJobId);
            showToast("已寫回此專案，並同步更新全片分鏡出圖 Prompt！", "success");
          } catch {
            showToast("已寫回此專案", "success");
          }
        } else {
          showToast("已寫回此專案", "success");
        }
      }
    } catch (e: any) {
      showToast("儲存失敗: " + e.message, "error");
    } finally {
      setCreatingProject(false);
      setIsRecutting(false);
    }
  };

  // 腳本逐行分割
  const scriptLines = scriptText.split("\n");
  const totalChars = scriptText.replace(/\s/g, "").length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 pb-20 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-cinema-text">
            {isEditMode ? "編輯此專案口白" : "新專案草稿"}
          </h2>
          <p className="text-xs text-cinema-muted">
            {isEditMode
              ? `寫回 ${selectedJobId}。改口白後可選擇是否重切分鏡。`
              : "空白草稿。可貼上已有口白，或填主題後生成。"}
          </p>
        </div>
        {isEditMode && (
          <button
            type="button"
            onClick={() => startNewDraft()}
            className="h-8 px-3 rounded border border-cinema-border text-xs text-cinema-muted hover:text-amber-cta"
          >
            開始新草稿
          </button>
        )}
      </div>

      {/* 故事主題與字數規模 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">腳本主題</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => {
              const v = e.target.value;
              setTopic(v);
              if (!slugTouched) setJobSlug(asciiSlug(v));
            }}
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
            onChange={(e) => {
              const val = Number(e.target.value);
              setWordCount(val);
              if (typeof window !== "undefined") {
                localStorage.setItem("aivideo_target_word_count", String(val));
              }
            }}
            className="w-full accent-amber-cta cursor-pointer h-10"
          />
        </div>
      </div>

      {!isEditMode && (
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">資料夾英文名（slug）</label>
          <input
            type="text"
            value={jobSlug}
            onChange={(e) => {
              setSlugTouched(true);
              setJobSlug(asciiSlug(e.target.value, ""));
            }}
            placeholder={asciiSlug(topic)}
            className="w-full h-10 px-3 rounded-md bg-cinema-card border border-cinema-border text-sm font-mono text-cinema-text focus:outline-none focus:border-amber-cta"
          />
          <p className="text-[10px] text-cinema-muted mt-1">
            建案資料夾：jobs/日期_{jobSlug.trim() || asciiSlug(topic)}（僅 ASCII）
          </p>
        </div>
      )}

      {/* 區塊一：自訂故事要求與指定 Prompt（獨立永久保存，不被大綱生成覆蓋） */}
      <div className="p-3.5 rounded-lg bg-cinema-card/90 border border-cinema-border space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-amber-cta text-sm">🎯</span>
            <span className="text-xs font-semibold text-cinema-text">
              故事要求／必寫看點（選填）
            </span>
            {customPrompt.trim() && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-cta/15 text-amber-cta border border-amber-cta/30 font-mono">
                {customPrompt.trim().length} 字 Prompt
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {customPrompt.trim() && (
              <>
                <button
                  type="button"
                  onClick={() => persistPromptAndOutline(customPrompt, outlineNotes, false)}
                  disabled={isSavingOutlinePrompt}
                  className="flex items-center text-[11px] text-amber-cta hover:text-amber-300 transition-colors mr-1 cursor-pointer"
                  title="儲存指定 Prompt 與特定要求"
                >
                  <Save className="w-3 h-3 mr-1" />
                  <span>儲存</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCustomPrompt("");
                    persistPromptAndOutline("", outlineNotes, true);
                  }}
                  className="text-[11px] text-cinema-muted/60 hover:text-red-400 transition-colors mr-1 cursor-pointer"
                >
                  清空 Prompt
                </button>
              </>
            )}
            <button
              type="button"
              onClick={() => setShowCustomPrompt(!showCustomPrompt)}
              className="p-1 rounded text-cinema-muted hover:text-cinema-text border border-cinema-border/60 hover:border-cinema-border cursor-pointer"
              title={showCustomPrompt ? "收起 Prompt 輸入框" : "展開 Prompt 輸入框"}
            >
              {showCustomPrompt ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {showCustomPrompt || customPrompt.trim() ? (
          <div className="space-y-1">
            <textarea
              rows={3}
              value={customPrompt}
              onChange={(e) => {
                const val = e.target.value;
                setCustomPrompt(val);
                if (!selectedJobId) {
                  localStorage.setItem("aivideo_draft_custom_prompt", val);
                }
              }}
              onBlur={() => persistPromptAndOutline(customPrompt, outlineNotes, true)}
              placeholder="在此輸入您個人的指定 Prompt、特定劇情限制或核心看點...例如：
- 希望視角聚焦在台積電林本堅如何說服張忠謀賭上浸潤式微影
- 必須描繪阿斯麥與德國蔡司鏡頭千錘百鍊的同盟生死戰
- 開場要製造強烈好奇心懸念，切勿冗長客套
（此處輸入的內容永久獨立保存，點擊下方「規劃 6 幕大綱」時不會被覆蓋，且生成腳本時會一併約束 AI）"
              className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-y"
            />
            <div className="text-[10px] text-cinema-muted flex items-center justify-between">
              <span>💡 提示：輸入完畢後自動保存；點擊下方「⚡ 依上方 Prompt 規劃 6 幕大綱」即可展開骨架；生成腳本時亦會深度遵循此處要求。</span>
            </div>
          </div>
        ) : (
          <div className="text-[11px] text-cinema-muted flex items-center justify-between py-0.5">
            <span>有特定想講的衝突、名場面或指定劇情？可先在此輸入，內容獨立保留不被大綱覆蓋。</span>
            <button
              type="button"
              onClick={() => setShowCustomPrompt(true)}
              className="text-amber-cta text-[11px] hover:underline ml-2 shrink-0 cursor-pointer"
            >
              輸入故事要求
            </button>
          </div>
        )}
      </div>

      {/* 區塊二：6 幕故事大綱（依上方 Prompt 智慧規劃或手動微調） */}
      <div className="p-3.5 rounded-lg bg-cinema-card/90 border border-cinema-border space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-amber-cta" />
            <span className="text-xs font-semibold text-cinema-text">
              📑 6 幕故事大綱（長篇 3500+ 字必備骨架）
            </span>
            {outlineNotes.trim() && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                大綱已就緒
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {outlineNotes.trim() && (
              <button
                type="button"
                onClick={() => persistPromptAndOutline(customPrompt, outlineNotes, false)}
                disabled={isSavingOutlinePrompt}
                className="flex items-center h-7 px-2 rounded bg-cinema-darker hover:bg-cinema-card border border-cinema-border hover:border-amber-cta text-amber-cta text-[11px] font-medium transition-colors cursor-pointer mr-0.5"
                title="儲存 6 幕故事大綱"
              >
                <Save className="w-3 h-3 mr-1" />
                <span>儲存大綱</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleGenerateOutline}
              disabled={isGeneratingOutline || !topic.trim()}
              className="flex items-center h-7 px-2.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-[11px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
              title={
                customPrompt.trim()
                  ? "依據上方指定的 Prompt 要求，聯網規劃出 6~8 幕深度大綱"
                  : "由 AI 聯網檢索該主題並規劃 6~8 幕核心情節大綱"
              }
            >
              {isGeneratingOutline ? (
                <>
                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  <span>規劃大綱中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3 h-3 mr-1" />
                  <span>
                    {customPrompt.trim()
                      ? "⚡ 依上方 Prompt 規劃 6 幕大綱"
                      : outlineNotes.trim()
                      ? "重新規劃 6 幕大綱"
                      : "⚡ AI 智慧規劃 6 幕大綱"}
                  </span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => setShowOutlineBox(!showOutlineBox)}
              className="p-1 rounded text-cinema-muted hover:text-cinema-text border border-cinema-border/60 hover:border-cinema-border cursor-pointer"
              title={showOutlineBox ? "收起大綱輸入框" : "展開大綱輸入框"}
            >
              {showOutlineBox ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* 大綱文字編輯區 */}
        {showOutlineBox || outlineNotes.trim() ? (
          <div className="space-y-1.5">
            <textarea
              rows={4}
              value={outlineNotes}
              onChange={(e) => {
                const val = e.target.value;
                setOutlineNotes(val);
                if (!selectedJobId) {
                  localStorage.setItem("aivideo_draft_outline", val);
                }
              }}
              onBlur={() => persistPromptAndOutline(customPrompt, outlineNotes, true)}
              placeholder="點擊右上角「⚡ 規劃 6 幕大綱」後，生成的大綱會出現在此處，不會覆蓋上方的指定 Prompt；您亦可直接手動條列大綱..."
              className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-y"
            />
            <div className="flex items-center justify-between text-[10px] text-cinema-muted">
              <span>💡 提示：大綱規劃產出在此並已自動保存，可自由微調；上方指定 Prompt 依然被完整保留。</span>
              {outlineNotes.trim() && (
                <button
                  type="button"
                  onClick={() => {
                    setOutlineNotes("");
                    persistPromptAndOutline(customPrompt, "", true);
                  }}
                  className="text-cinema-muted/60 hover:text-red-400 cursor-pointer"
                >
                  清空大綱
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="text-[11px] text-cinema-muted flex items-center justify-between py-0.5">
            <span>點擊右側按鈕即可一鍵規劃 6 幕大綱（若上方有指定 Prompt 將自動融合）。</span>
            <button
              type="button"
              onClick={() => setShowOutlineBox(true)}
              className="text-amber-cta text-[11px] hover:underline ml-2 shrink-0 cursor-pointer"
            >
              手動輸入大綱 / 展開
            </button>
          </div>
        )}
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

        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">視覺風格</label>
          <button
            type="button"
            onClick={() => setIsGalleryOpen(true)}
            className="w-full h-9 px-3 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text hover:border-amber-cta flex items-center justify-between"
          >
            <span className="truncate">{currentStyleObj?.name || "選擇風格"}</span>
            <span className="text-amber-cta shrink-0 ml-2">更換</span>
          </button>
        </div>
      </div>

      {/* 腳本內容即時預覽與編輯器（含 AI 生成腳本主按鈕） */}
      <div
        ref={scriptBoxRef}
        className="flex flex-col min-h-[380px] shrink-0 rounded-lg bg-cinema-card border border-cinema-border overflow-hidden transition-all shadow-md"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2.5 border-b border-cinema-border/60 text-xs bg-cinema-darker/60 gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-cinema-text">📖 故事腳本即時預覽與編輯區</span>
            <span className="text-[10px] text-cinema-muted">（每行一句話，可直接編輯）</span>
          </div>
          <div className="flex items-center space-x-2.5 text-cinema-muted text-xs">
            <span className="font-mono text-amber-cta font-medium hidden sm:inline">
              {scriptLines.filter((l) => l.trim()).length} 句口白 · 共 {totalChars} 字
            </span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(scriptText);
                showToast("已複製腳本內容至剪貼簿！", "info");
              }}
              className="flex items-center hover:text-cinema-text transition-colors text-xs text-cinema-muted px-2 py-1 rounded bg-cinema-card border border-cinema-border cursor-pointer"
              title="複製腳本"
            >
              <Copy className="w-3.5 h-3.5 mr-1" />
              <span>複製</span>
            </button>

            {/* 智慧斷句分行按鈕 */}
            <button
              type="button"
              onClick={handleAutoFormatScript}
              disabled={generating || !scriptText.trim()}
              className="flex items-center hover:text-amber-cta transition-colors text-xs text-cinema-muted px-2 py-1 rounded bg-cinema-card border border-cinema-border cursor-pointer"
              title="將長段落或長句自動按標點拆分為標準的一句一行（每行約 15~25 字）"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1 text-amber-cta" />
              <span>智慧分行</span>
            </button>

            {/* 深度擴寫情節按鈕 */}
            <button
              type="button"
              onClick={handleExpandScript}
              disabled={isExpandingScript || generating || !scriptText.trim()}
              className="flex items-center h-8 px-3 rounded bg-cinema-card hover:bg-cinema-cardHover text-amber-cta border border-amber-cta/50 hover:border-amber-cta text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-40 cursor-pointer shadow-sm active:scale-95"
              title={!scriptText.trim() ? "請先生成或填寫腳本口白後再進行擴寫" : "針對目前情節對白、衝突與歷史數據深入展開，大幅增加篇幅與字數"}
            >
              {isExpandingScript ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>AI 深度擴寫中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  <span>🔍 深度擴寫情節</span>
                </>
              )}
            </button>

            {/* 生成腳本主按鈕 */}
            <button
              onClick={handleGenerateScript}
              disabled={generating || !topic.trim()}
              className="flex items-center h-8 px-3.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow glow-amber active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              title={!topic.trim() ? "請先填寫腳本主題" : "由 AI 聯網生成逐句口白腳本並於下方編輯區顯示"}
            >
              {generating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>AI 生成中 (15~30s)...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  <span>{scriptText.trim() ? "重新生成腳本" : "✨ 生成逐句腳本"}</span>
                </>
              )}
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
            placeholder="點擊右上角「生成逐句腳本」或直接在此貼上/撰寫逐句口白..."
          />
        </div>
      </div>

      {/* 風格大海報牆改由 modal「更換」開啟 */}
      <div className="hidden space-y-2.5">
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

      <div className="shrink-0 space-y-2 p-3.5 rounded-lg bg-cinema-card border border-cinema-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Film className="w-4 h-4 text-amber-cta" />
            <label className="text-xs font-semibold text-cinema-text">切鏡節奏（進階）</label>
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

      {/* 視覺轉譯風格視角 (二階視覺轉換：奇幻 / 寫實 / 象徵) */}
      <div className="shrink-0 space-y-2 p-3.5 rounded-lg bg-cinema-card border border-cinema-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-cta" />
            <label className="text-xs font-semibold text-cinema-text">視覺轉譯風格 (出圖 Prompt 轉譯視角)</label>
          </div>
          <span className="text-[11px] text-cinema-muted">
            切鏡時自動依此視角將抽象口白「轉譯」為電影級英文出圖 Prompt
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {[
            {
              id: "fantasy" as const,
              icon: "🌟",
              title: "超現實主義 (Surrealism)",
              badge: "預設推薦",
              desc: "表現荒誕、夢境與誇張比例，A surreal conceptual art piece 模板構建",
            },
            {
              id: "vintage_realistic" as const,
              icon: "🏛️",
              title: "電影寫實 (Cinematic)",
              badge: "歷史現場",
              desc: "具歷史感、真實環境氛圍，Cinematic wide shot, 35mm film 模板構建",
            },
            {
              id: "symbolic" as const,
              icon: "🎭",
              title: "象徵概念 (Symbolic)",
              badge: "哲思隱喻",
              desc: "探討抽象概念、政治隱喻，An epic symbolic digital illustration 模板構建",
            },
          ].map((m) => {
            const isSelected = metaphorStyle === m.id;
            return (
              <div
                key={m.id}
                onClick={() => setMetaphorStyle(m.id)}
                className={`p-2.5 rounded-md border cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? "bg-amber-cta/10 border-amber-cta text-cinema-text shadow-sm"
                    : "bg-cinema-darker/60 border-cinema-border/70 text-cinema-muted hover:border-cinema-muted hover:text-cinema-text"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5 font-medium text-xs">
                    <span>{m.icon}</span>
                    <span className={isSelected ? "text-amber-cta font-semibold" : ""}>{m.title}</span>
                  </div>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isSelected
                        ? "bg-amber-cta text-cinema-bg font-bold"
                        : "bg-cinema-card border border-cinema-border text-cinema-muted"
                    }`}
                  >
                    {m.badge}
                  </span>
                </div>
                <div className="text-[11px] leading-relaxed opacity-80">{m.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 視覺一致性特徵分析與進入分鏡工作台（整合一體化前製面板） */}
      <div className="shrink-0 rounded-lg bg-cinema-card border border-cinema-border overflow-hidden shadow-md">
        {/* 卡片頂部 Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border-b border-cinema-border/60 bg-cinema-darker/40">
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-4 h-4 text-amber-cta shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-cinema-text">
                  🎭 視覺一致性特徵分析與前製設定 (Character & Entity Bible)
                </span>
                {(characters.length > 0 || subjectAnchor) && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                    已建立 {characters.length} 個角色錨點
                  </span>
                )}
              </div>
              <p className="text-[11px] text-cinema-muted mt-0.5">
                依選定的生圖風格掃描腳本，提煉每位角色的外觀錨點與世界觀光影，確保全片分鏡畫風連貫。
              </p>
            </div>
          </div>

          <button
            onClick={handleAnalyzeAnchors}
            disabled={isAnalyzingAnchors || !scriptText.trim()}
            className="flex items-center justify-center h-8 px-3 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-40 cursor-pointer shrink-0"
            title={!scriptText.trim() ? "請先生成或填寫腳本內容後再進行分析" : "依據目前腳本與風格提煉角色特徵"}
          >
            {isAnalyzingAnchors ? (
              <>
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                <span>分析腳本主體中...</span>
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
        {showAnchors || subjectAnchor || characters.length > 0 ? (
          <div className="p-4 space-y-3 bg-cinema-card/50">
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
                className="flex items-center h-7 px-2.5 rounded bg-cinema-darker hover:bg-cinema-card text-cinema-muted hover:text-amber-cta text-[11px] border border-cinema-border transition-colors cursor-pointer"
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
        ) : (
          <div className="p-4 bg-cinema-card/30 text-[11px] text-cinema-muted/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-amber-cta/80 shrink-0" />
              <span>點擊上方「✨ AI 分析」可預先檢視並微調主體特徵；若直接建立專案，系統亦會在後台自動進行分析約束。</span>
            </div>
            <button
              type="button"
              onClick={() => setShowAnchors(true)}
              className="text-amber-cta hover:underline shrink-0 text-xs ml-2 cursor-pointer"
            >
              手動自訂錨點
            </button>
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 border-t border-cinema-border/70 bg-cinema-darker/70 gap-3">
          <div className="text-[11px] text-cinema-muted">
            {isEditMode
              ? "寫回此專案後，若口白有改會再問是否重切分鏡。"
              : scriptText.trim()
              ? "可貼上已有口白或從主題生成，滿意後建立專案。"
              : "請貼入口白，或先填主題再生成腳本。"}
          </div>

          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={isEditMode ? handleSaveExisting : handleCreateProject}
              disabled={creatingProject || generating || isRecutting || !scriptText.trim()}
              className={`flex items-center h-9 px-5 rounded font-semibold text-xs tracking-wide transition-all ${
                !scriptText.trim()
                  ? "bg-cinema-darker border border-cinema-border/70 text-cinema-muted/40 cursor-not-allowed opacity-40 shadow-none"
                  : "bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg shadow glow-amber active:scale-95 disabled:opacity-50 cursor-pointer"
              }`}
            >
              {creatingProject || isRecutting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>{isRecutting ? "重切分鏡中..." : isEditMode ? "寫回中..." : "解析分鏡中..."}</span>
                </>
              ) : (
                <>
                  <span>{isEditMode ? "寫回此專案" : "建立專案並進入分鏡"}</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </>
              )}
            </button>
          </div>
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
