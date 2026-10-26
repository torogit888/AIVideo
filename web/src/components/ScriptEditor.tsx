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
import {
  applyChannelPersonaToPrompt,
  asciiSlug,
  buildOpeningPromptLine,
  DEFAULT_CHANNEL_NAME,
  DEFAULT_CHANNEL_PRESETS,
  DEFAULT_CUSTOM_PROMPT,
  DEFAULT_VOICE_ID,
  detectChannelFromPrompt,
  scriptWorkspaceMode,
} from "../studioActions";

const getInitialChannelPresets = (): string[] => {
  if (typeof window !== "undefined") {
    try {
      const raw = localStorage.getItem("aivideo_channel_presets");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
  }
  return DEFAULT_CHANNEL_PRESETS;
};

const getActiveChannelDefaultPrompt = (): string => {
  if (typeof window !== "undefined") {
    const savedChannel = localStorage.getItem("aivideo_active_channel");
    if (savedChannel) {
      return buildOpeningPromptLine(savedChannel);
    }
  }
  return DEFAULT_CUSTOM_PROMPT;
};

export const ScriptEditor: React.FC = () => {
  const {
    setTab,
    loadJobs,
    loadScenes,
    selectedJobId,
    draftResetKey,
    jobs,
    showToast,
    requestConfirm,
    requestPrompt,
    selectedAiModel,
    startNewDraft,
    anchorsRevision,
    bumpAnchorsRevision,
    setScriptDirty,
  } = useStudioStore();
  const currentJob = jobs.find((j) => j.id === selectedJobId);
  const workspaceMode = scriptWorkspaceMode(selectedJobId);
  const isEditMode = workspaceMode === "edit";

  const [topic, setTopic] = useState("");
  const [channelPresets, setChannelPresets] = useState<string[]>(getInitialChannelPresets);
  const [customPrompt, setCustomPrompt] = useState(getActiveChannelDefaultPrompt);
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);
  const [outlineNotes, setOutlineNotes] = useState("");
  const [showOutlineBox, setShowOutlineBox] = useState(false);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [isExpandingScript, setIsExpandingScript] = useState(false);

  const [scriptText, setScriptText] = useState("");
  const [savedScript, setSavedScript] = useState("");
  const [showScriptBox, setShowScriptBox] = useState(true);
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
  const containerRef = useRef<HTMLDivElement>(null);
  const styleScrollRef = useRef<HTMLDivElement>(null);
  const scriptBoxRef = useRef<HTMLDivElement>(null);

  const [generating, setGenerating] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [isSavingOutlinePrompt, setIsSavingOutlinePrompt] = useState(false);

  // 視覺一致性主體分析狀態
  const [subjectAnchor, setSubjectAnchor] = useState("");
  const [environmentAnchor, setEnvironmentAnchor] = useState("");
  const [characters, setCharacters] = useState<
    { id: string; name: string; appearance: string; entity_type?: "character" | "object" }[]
  >([]);
  const [isAnalyzingAnchors, setIsAnalyzingAnchors] = useState(false);
  const [showAnchors, setShowAnchors] = useState(false);
  const [anchorsReanalyzed, setAnchorsReanalyzed] = useState(false);

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

  // 當定裝中心彈窗更新角色或環境錨點時，確保腳本頁的角色與環境錨點即時同步
  useEffect(() => {
    if (!selectedJobId || anchorsRevision === 0) return;
    api
      .getJobAnchors(selectedJobId)
      .then((data) => {
        setSubjectAnchor(data.subject || "");
        setEnvironmentAnchor(data.environment || "");
        setCharacters(
          (data.characters || []).map((c, i) => ({
            id: c.id || `char_${i + 1}`,
            name: c.name || `角色 ${i + 1}`,
            appearance: c.appearance || "",
            entity_type: (c.entity_type as "character" | "object") || "character",
          }))
        );
      })
      .catch(() => {});
  }, [selectedJobId, anchorsRevision]);

  // 切換不同專案或點擊「新建專案」時，自動載入該專案內容或完整重置為全新草稿
  useEffect(() => {
    let cancelled = false;

    if (!selectedJobId) {
      setTopic("");
      setScriptText("");
      setSavedScript("");
      setJobSlug("");
      setSlugTouched(false);
      setShowCustomPrompt(false);
      setShowOutlineBox(false);
      setShowAnchors(false);
      setSubjectAnchor("");
      setEnvironmentAnchor("");
      setCharacters([]);
      setSelectedTone(tones.length > 0 ? tones[0].id : "michelin_curious");
      setSelectedVoice(DEFAULT_VOICE_ID);
      setSelectedStyle("otomo_katsuhiro");
      setVisualPacing("balanced");

      const draftPrompt = localStorage.getItem("aivideo_draft_custom_prompt");
      const draftOutline = localStorage.getItem("aivideo_draft_outline") || "";
      setCustomPrompt(
        draftPrompt && draftPrompt.trim() ? draftPrompt : getActiveChannelDefaultPrompt()
      );
      setOutlineNotes(draftOutline);
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    api
      .getJobDetail(selectedJobId)
      .then((detail) => {
        if (cancelled) return;
        setTopic(detail.title || "");
        const sc = detail.script_content || "";
        setScriptText(sc);
        setSavedScript(sc);
        setSelectedVoice(detail.config?.voice_id || DEFAULT_VOICE_ID);
        setSelectedStyle(detail.config?.image?.style || "otomo_katsuhiro");
        setSelectedTone(detail.config?.tone_id || (tones[0]?.id || "michelin_curious"));
        const savedPacing = detail.config?.visual_pacing;
        if (savedPacing === "fast" || savedPacing === "balanced" || savedPacing === "slow") {
          setVisualPacing(savedPacing);
        } else {
          setVisualPacing("balanced");
        }

        const vAnchors = detail.config?.visual_anchors || {};
        setSubjectAnchor(vAnchors.subject || "");
        setEnvironmentAnchor(vAnchors.environment || "");
        setCharacters(
          Array.isArray(vAnchors.characters)
            ? vAnchors.characters.map((c: any, i: number) => ({
                id: c.id || `char_${i + 1}`,
                name: c.name || `角色 ${i + 1}`,
                appearance: c.appearance || "",
                entity_type: (c.entity_type as "character" | "object") || "character",
              }))
            : []
        );
        setShowAnchors(false);

        const savedPrompt =
          detail.custom_prompt || detail.config?.custom_prompt || getActiveChannelDefaultPrompt();
        setCustomPrompt(savedPrompt);
        setShowCustomPrompt(false);
        const savedOutline = detail.outline || detail.config?.outline || "";
        setOutlineNotes(savedOutline);
        setShowOutlineBox(Boolean(savedOutline.trim()));
        containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
      })
      .catch((e) => {
        if (!cancelled) console.error("載入專案詳情失敗", e);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedJobId, draftResetKey]);

  useEffect(() => {
    const dirty = selectedJobId ? scriptText !== savedScript : scriptText.trim().length > 0;
    if (useStudioStore.getState().scriptDirty !== dirty) {
      setScriptDirty(dirty);
    }
  }, [scriptText, savedScript, selectedJobId, setScriptDirty]);

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
        customPrompt.trim() || undefined,
        wordCount
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
        entity_type: (c.entity_type as "character" | "object") || "character",
      }));
      const finalChars = nextChars.length
        ? nextChars
        : res.subject_anchor
          ? [{ id: "main", name: "Main Subject", appearance: res.subject_anchor, entity_type: "character" as const }]
          : [];
      setCharacters(finalChars);
      setSubjectAnchor(res.subject_anchor || "");
      setEnvironmentAnchor(res.environment_anchor || "");
      setShowAnchors(true);
      setAnchorsReanalyzed(true);

      // 若目前正在編輯既有專案，立即寫入 anchors.yaml 並清空舊角色定裝圖，避免定裝中心殘留舊敘述與舊圖
      if (selectedJobId) {
        await api.updateJob(selectedJobId, {
          title: topic || undefined,
          style_id: selectedStyle,
          subject_anchor: (res.subject_anchor || "").trim() || undefined,
          environment_anchor: (res.environment_anchor || "").trim() || undefined,
          characters: finalChars,
          clear_hero_images: true,
        });
        await loadJobs();
        bumpAnchorsRevision();
        showToast(
          "✨ 已重新分析角色與世界觀，並自動寫入專案、清空舊定裝圖！可前往定裝中心重新生成定裝圖。",
          "success"
        );
      } else {
        showToast("✨ 已依目前生圖風格分析腳本，提煉出各角色外觀與環境光影。", "success");
      }
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
          .map((c) => ({
            id: c.id,
            name: c.name.trim(),
            appearance: c.appearance.trim(),
            entity_type: c.entity_type || "character",
          })),
        custom_prompt: customPrompt.trim() || undefined,
        outline: outlineNotes.trim() || undefined,
        use_pip: true,
      });
      // 成功建案後清理本機草稿快取
      localStorage.removeItem("aivideo_draft_custom_prompt");
      localStorage.removeItem("aivideo_draft_outline");
      await loadJobs();
      useStudioStore.getState().setScriptDirty(false);
      await useStudioStore.getState().selectJob(res.id);
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
        .map((c) => ({
          id: c.id,
          name: c.name.trim(),
          appearance: c.appearance.trim(),
          entity_type: c.entity_type || "character",
        }));

      await api.updateJob(selectedJobId, {
        title: topic,
        voice_id: selectedVoice,
        style_id: selectedStyle,
        tone_id: selectedTone,
        visual_pacing: visualPacing,
        script: scriptText,
        custom_prompt: customPrompt.trim() || undefined,
        outline: outlineNotes.trim() || undefined,
        subject_anchor: subjectAnchor.trim() || undefined,
        environment_anchor: environmentAnchor.trim() || undefined,
        characters: validChars.length ? validChars : undefined,
        clear_hero_images: anchorsReanalyzed ? true : undefined,
      });
      setSavedScript(scriptText);
      await loadJobs();
      bumpAnchorsRevision();
      const hasScenes = (currentJob?.progress.scenes_count || 0) > 0;
      const recut =
        hasScenes &&
        scriptText !== savedScript &&
        (await requestConfirm({
          title: "是否依新口白重切分鏡？",
          message: "口白已寫回此專案。要依新口白重切分鏡嗎？既有 takes 會依同鏡頭 id 保留。",
          confirmText: "重切分鏡",
          cancelText: "僅更新口白",
          variant: "primary",
        }));
      if (recut) {
        setAnchorsReanalyzed(false);
        setIsRecutting(true);
        await api.recutJob(selectedJobId, { script: scriptText, visual_pacing: visualPacing });
        await loadJobs();
        await loadScenes(selectedJobId);
        showToast("已儲存並重切分鏡", "success");
        setTab("storyboard");
      } else {
        // 選「僅更新口白」時，除非剛重新分析過視覺錨點（anchorsReanalyzed），否則絕不重刷全片英文生圖 Prompt
        if (hasScenes && anchorsReanalyzed) {
          setAnchorsReanalyzed(false);
          try {
            await api.syncScenePrompts(selectedJobId);
            await loadScenes(selectedJobId);
            showToast("已寫回此專案，並依新定裝同步更新全片分鏡出圖 Prompt！", "success");
          } catch (e: any) {
            await loadScenes(selectedJobId);
            showToast("口白已寫回，但英文出圖句子沒有全部更新: " + (e.message || "未知錯誤"), "error");
          }
        } else {
          setAnchorsReanalyzed(false);
          await loadScenes(selectedJobId);
          showToast("已寫回此專案（僅更新口白，保留原分鏡與英文 Prompt）", "success");
        }
      }
    } catch (e: any) {
      showToast("儲存失敗: " + e.message, "error");
    } finally {
      setCreatingProject(false);
      setIsRecutting(false);
    }
  };

  const detectedChannel = detectChannelFromPrompt(customPrompt);

  const handleSelectChannelPersona = (channelName: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_active_channel", channelName);
    }
    const nextPrompt = applyChannelPersonaToPrompt(customPrompt, channelName);
    setCustomPrompt(nextPrompt);
    setShowCustomPrompt(true);
    persistPromptAndOutline(nextPrompt, outlineNotes, true);
    showToast(
      channelName === "無自稱"
        ? "已切換為「無自稱（直接破題）」"
        : `已切換頻道主自稱為「${channelName}」（開頭: 大家好~我是${channelName}!）`,
      "info"
    );
  };

  const handleAddChannelPreset = async () => {
    const input = await requestPrompt({
      title: "新增頻道／說書人名稱",
      message: "請輸入新頻道／說書人名稱（例如：白兔、夜梟）：",
      placeholder: "例如：白兔",
      confirmText: "新增並套用",
    });
    const name = (input || "").trim();
    if (!name) return;
    const nextList = channelPresets.includes(name) ? channelPresets : [...channelPresets, name];
    setChannelPresets(nextList);
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_channel_presets", JSON.stringify(nextList));
    }
    handleSelectChannelPersona(name);
  };

  const handleRemoveChannelPreset = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (name === DEFAULT_CHANNEL_NAME) return;
    const nextList = channelPresets.filter((c) => c !== name);
    setChannelPresets(nextList);
    if (typeof window !== "undefined") {
      localStorage.setItem("aivideo_channel_presets", JSON.stringify(nextList));
    }
  };

  // 腳本逐行分割
  const scriptLines = scriptText.split("\n");
  const totalChars = scriptText.replace(/\s/g, "").length;

  return (
    <div
      ref={containerRef}
      className="flex-1 flex flex-col h-full overflow-y-auto p-5 pb-16 max-w-5xl mx-auto space-y-3.5"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2.5">
          <h2 className="text-base font-semibold text-cinema-text">
            {isEditMode ? "編輯專案腳本" : "新專案草稿"}
          </h2>
          {isEditMode && selectedJobId && (
            <span className="text-xs font-mono text-cinema-muted">{selectedJobId}</span>
          )}
        </div>
        {!isEditMode && (topic.trim() || scriptText.trim() || outlineNotes.trim()) && (
          <button
            type="button"
            onClick={() => {
              startNewDraft();
              showToast("已清空草稿內容", "info");
            }}
            className="h-7 px-2.5 rounded border border-cinema-border text-xs text-cinema-muted hover:text-amber-cta"
          >
            清空草稿
          </button>
        )}
      </div>

      {/* 第一排：主題、字數、資料夾代號（新專案） */}
      <div className={`grid grid-cols-1 ${!isEditMode ? "md:grid-cols-12" : "md:grid-cols-3"} gap-3`}>
        <div className={!isEditMode ? "md:col-span-6" : "md:col-span-2"}>
          <label className="block text-xs font-medium text-cinema-muted mb-1">腳本主題</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => {
              const v = e.target.value;
              setTopic(v);
              if (!slugTouched) setJobSlug(asciiSlug(v));
            }}
            className="w-full h-9 px-3 rounded-md bg-cinema-card border border-cinema-border text-sm text-cinema-text focus:outline-none focus:border-amber-cta"
            placeholder="輸入故事主題..."
          />
        </div>
        {!isEditMode && (
          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-cinema-muted mb-1">資料夾英文名</label>
            <input
              type="text"
              value={jobSlug}
              onChange={(e) => {
                setSlugTouched(true);
                setJobSlug(asciiSlug(e.target.value, ""));
              }}
              placeholder={asciiSlug(topic)}
              className="w-full h-9 px-2.5 rounded-md bg-cinema-card border border-cinema-border text-xs font-mono text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>
        )}
        <div className={!isEditMode ? "md:col-span-3" : "md:col-span-1"}>
          <div className="flex justify-between items-center mb-1">
            <label className="text-xs font-medium text-cinema-muted">目標字數</label>
            <span className="text-xs font-mono text-amber-cta">
              {wordCount} 字 (~{Math.max(1, Math.round(wordCount / 220))}分)
            </span>
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
            className="w-full accent-amber-cta cursor-pointer h-9"
          />
        </div>
      </div>

      {/* 第二排：口吻、發音人、視覺風格 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1">口吻風格</label>
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

        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1">發音人</label>
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
          <label className="block text-xs font-medium text-cinema-muted mb-1">視覺風格</label>
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

      {/* 第三排（緊湊收合）：故事要求／頻道自稱 ＆ 故事大綱 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* 左：故事要求與頻道自稱 */}
        <div className="p-2.5 rounded-lg bg-cinema-card/90 border border-cinema-border space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-1.5">
            <div className="flex items-center flex-wrap gap-1.5">
              <span className="text-xs font-semibold text-cinema-text mr-1">故事要求</span>
              {channelPresets.map((ch) => {
                const isActive = detectedChannel === ch;
                return (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => handleSelectChannelPersona(ch)}
                    className={`group flex items-center h-6 px-2 rounded-full text-[11px] font-medium border transition-colors cursor-pointer ${
                      isActive
                        ? "bg-amber-cta text-cinema-bg border-amber-cta font-semibold"
                        : "bg-cinema-darker text-cinema-text border-cinema-border hover:border-amber-cta/60"
                    }`}
                  >
                    <span>我是{ch}</span>
                    {ch !== DEFAULT_CHANNEL_NAME && (
                      <span
                        onClick={(e) => handleRemoveChannelPreset(ch, e)}
                        className={`ml-1 text-[10px] hover:text-red-400 ${
                          isActive ? "text-cinema-bg/70 hover:text-red-900" : "text-cinema-muted"
                        }`}
                        title="移除"
                      >
                        ×
                      </span>
                    )}
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => handleSelectChannelPersona("無自稱")}
                className={`flex items-center h-6 px-2 rounded-full text-[11px] border transition-colors cursor-pointer ${
                  detectedChannel === "無自稱"
                    ? "bg-amber-cta text-cinema-bg border-amber-cta font-semibold"
                    : "bg-cinema-darker text-cinema-muted border-cinema-border hover:text-cinema-text"
                }`}
              >
                無自稱
              </button>
              <button
                type="button"
                onClick={handleAddChannelPreset}
                className="flex items-center h-6 px-1.5 rounded-full text-[11px] bg-cinema-darker hover:bg-cinema-card text-amber-cta border border-dashed border-amber-cta/40 cursor-pointer"
                title="新增頻道名"
              >
                <Plus className="w-3 h-3" />
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowCustomPrompt(!showCustomPrompt)}
              className="flex items-center text-[11px] text-cinema-muted hover:text-cinema-text px-1.5 py-0.5 rounded border border-cinema-border/60 cursor-pointer"
            >
              <span className="mr-1">{showCustomPrompt ? "收起" : "展開"}</span>
              {showCustomPrompt ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>

          {showCustomPrompt && (
            <div className="space-y-1.5 pt-1">
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
                onBlur={() => {
                  if (selectedJobId) {
                    persistPromptAndOutline(customPrompt, outlineNotes, true);
                  }
                }}
                placeholder="輸入特定劇情看點或指定要求（選填）..."
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-y"
              />
              {customPrompt.trim() && (
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => persistPromptAndOutline(customPrompt, outlineNotes, false)}
                    disabled={isSavingOutlinePrompt}
                    className="flex items-center text-[11px] text-amber-cta hover:text-amber-300 cursor-pointer"
                  >
                    <Save className="w-3 h-3 mr-1" />
                    儲存
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCustomPrompt("");
                      persistPromptAndOutline("", outlineNotes, true);
                    }}
                    className="text-[11px] text-cinema-muted hover:text-red-400 cursor-pointer"
                  >
                    清空
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 右：故事大綱 */}
        <div className="p-2.5 rounded-lg bg-cinema-card/90 border border-cinema-border space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <FileText className="w-3.5 h-3.5 text-amber-cta" />
              <span className="text-xs font-semibold text-cinema-text">故事大綱</span>
              {outlineNotes.trim() && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  已就緒
                </span>
              )}
            </div>
            <div className="flex items-center space-x-1.5">
              <button
                type="button"
                onClick={handleGenerateOutline}
                disabled={isGeneratingOutline || !topic.trim()}
                className="flex items-center h-6 px-2.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-[11px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
              >
                {isGeneratingOutline ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    <span>規劃中...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3 mr-1" />
                    <span>{outlineNotes.trim() ? "重新規劃" : "規劃大綱"}</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => setShowOutlineBox(!showOutlineBox)}
                className="flex items-center text-[11px] text-cinema-muted hover:text-cinema-text px-1.5 py-0.5 rounded border border-cinema-border/60 cursor-pointer"
              >
                <span className="mr-1">{showOutlineBox ? "收起" : "展開"}</span>
                {showOutlineBox ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            </div>
          </div>

          {showOutlineBox && (
            <div className="space-y-1.5 pt-1">
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
                onBlur={() => {
                  if (selectedJobId) {
                    persistPromptAndOutline(customPrompt, outlineNotes, true);
                  }
                }}
                placeholder="點擊「規劃大綱」自動生成，或在此手動輸入各幕大綱..."
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-y"
              />
              {outlineNotes.trim() && (
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => persistPromptAndOutline(customPrompt, outlineNotes, false)}
                    disabled={isSavingOutlinePrompt}
                    className="flex items-center text-[11px] text-amber-cta hover:text-amber-300 cursor-pointer"
                  >
                    <Save className="w-3 h-3 mr-1" />
                    儲存
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOutlineNotes("");
                      persistPromptAndOutline(customPrompt, "", true);
                    }}
                    className="text-[11px] text-cinema-muted hover:text-red-400 cursor-pointer"
                  >
                    清空
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 主畫面：口白編輯器（支援收起/展開） */}
      <div
        ref={scriptBoxRef}
        className={`flex flex-col shrink-0 rounded-lg bg-cinema-card border border-cinema-border overflow-hidden transition-all shadow-md ${
          showScriptBox ? "min-h-[380px]" : ""
        }`}
      >
        <div
          className={`flex flex-col sm:flex-row sm:items-center justify-between px-4 py-2 text-xs bg-cinema-darker/60 gap-2 ${
            showScriptBox ? "border-b border-cinema-border/60" : ""
          }`}
        >
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-cinema-text">口白內容</span>
            <span className="font-mono text-amber-cta font-medium">
              {scriptLines.filter((l) => l.trim()).length} 句 · {totalChars} 字
            </span>
          </div>
          <div className="flex items-center space-x-2 text-cinema-muted text-xs">
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

            <button
              type="button"
              onClick={handleAutoFormatScript}
              disabled={generating || !scriptText.trim()}
              className="flex items-center hover:text-amber-cta transition-colors text-xs text-cinema-muted px-2 py-1 rounded bg-cinema-card border border-cinema-border cursor-pointer"
              title="將長句按標點自動拆為一句一行"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1 text-amber-cta" />
              <span>自動分行</span>
            </button>

            <button
              type="button"
              onClick={handleExpandScript}
              disabled={isExpandingScript || generating || !scriptText.trim()}
              className="flex items-center h-7 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover text-amber-cta border border-amber-cta/50 hover:border-amber-cta text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-40 cursor-pointer"
            >
              {isExpandingScript ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  <span>擴寫中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  <span>擴寫</span>
                </>
              )}
            </button>

            <button
              onClick={handleGenerateScript}
              disabled={generating || !topic.trim()}
              className="flex items-center h-7 px-3 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow glow-amber active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {generating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>生成中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  <span>{scriptText.trim() ? "重新生成" : "生成腳本"}</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setShowScriptBox(!showScriptBox)}
              className="flex items-center text-[11px] text-cinema-muted hover:text-cinema-text px-2 py-1 rounded bg-cinema-card border border-cinema-border/60 cursor-pointer"
            >
              <span className="mr-1">{showScriptBox ? "收起" : "展開"}</span>
              {showScriptBox ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* 編輯器容器 */}
        {showScriptBox && (
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
              placeholder="點擊右上角「生成腳本」或直接在此貼上/撰寫逐句口白..."
            />
          </div>
        )}
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

      {/* 底部設定與建案列（切鏡節奏 + 角色設定 + 建立/儲存主按鈕） */}
      <div className="shrink-0 rounded-lg bg-cinema-card border border-cinema-border overflow-hidden shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-cinema-darker/50">
          {/* 左：切鏡節奏三段式切換 */}
          <div className="flex items-center gap-2">
            <Film className="w-3.5 h-3.5 text-amber-cta shrink-0" />
            <span className="text-xs font-medium text-cinema-muted">切鏡節奏</span>
            <div className="flex rounded-md bg-cinema-card p-0.5 border border-cinema-border/80 text-xs">
              {[
                { id: "fast" as const, label: "快 (1~2句)" },
                { id: "balanced" as const, label: "標準 (2~4句)" },
                { id: "slow" as const, label: "慢 (3~5句)" },
              ].map((p) => {
                const isSelected = visualPacing === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setVisualPacing(p.id)}
                    className={`px-2.5 py-1 rounded text-[11px] transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-amber-cta text-cinema-bg font-semibold"
                        : "text-cinema-muted hover:text-cinema-text"
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 中：角色與世界觀設定開關 */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleAnalyzeAnchors}
              disabled={isAnalyzingAnchors || !scriptText.trim()}
              className="flex items-center h-7 px-2.5 rounded bg-amber-cta/15 hover:bg-amber-cta/25 text-amber-cta border border-amber-cta/40 text-[11px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
            >
              {isAnalyzingAnchors ? (
                <>
                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  <span>分析角色中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3 h-3 mr-1" />
                  <span>{characters.length || subjectAnchor ? "重分析角色" : "AI 分析角色"}</span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => setShowAnchors(!showAnchors)}
              className="flex items-center h-7 px-2.5 rounded bg-cinema-card hover:bg-cinema-cardHover border border-cinema-border text-[11px] text-cinema-muted hover:text-cinema-text cursor-pointer"
            >
              <span>角色設定 ({characters.length})</span>
              {showAnchors ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
            </button>
          </div>

          {/* 右：建立或儲存專案主按鈕 */}
          <button
            onClick={isEditMode ? handleSaveExisting : handleCreateProject}
            disabled={creatingProject || generating || isRecutting || !scriptText.trim()}
            className={`flex items-center h-8 px-4 rounded font-semibold text-xs tracking-wide transition-all ${
              !scriptText.trim()
                ? "bg-cinema-darker border border-cinema-border/70 text-cinema-muted/40 cursor-not-allowed opacity-40"
                : "bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg shadow glow-amber active:scale-95 disabled:opacity-50 cursor-pointer"
            }`}
          >
            {creatingProject || isRecutting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                <span>{isRecutting ? "重切分鏡中..." : isEditMode ? "寫回中..." : "建立中..."}</span>
              </>
            ) : (
              <>
                <span>{isEditMode ? "寫回此專案" : "建立專案並進入分鏡"}</span>
                <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </>
            )}
          </button>
        </div>

        {/* 展開之角色與環境編輯區（按需展開） */}
        {showAnchors && (
          <div className="p-4 space-y-3 border-t border-cinema-border/60 bg-cinema-card/50">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-cinema-muted">角色外觀設定</label>
              <button
                type="button"
                onClick={() =>
                  setCharacters((prev) => [
                    ...prev,
                    { id: `char_${prev.length + 1}`, name: "", appearance: "", entity_type: "character" },
                  ])
                }
                className="flex items-center h-6 px-2 rounded bg-cinema-darker hover:bg-cinema-card text-cinema-muted hover:text-amber-cta text-[11px] border border-cinema-border cursor-pointer"
              >
                <Plus className="w-3 h-3 mr-1" />
                新增角色
              </button>
            </div>
            {characters.length === 0 && (
              <p className="text-[11px] text-cinema-muted">尚無角色，可點「AI 分析角色」或「新增角色」。</p>
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
                    <select
                      value={ch.entity_type || "character"}
                      onChange={(e) => {
                        const newType = e.target.value as "character" | "object";
                        const updatedList = characters.map((x, i) =>
                          i === idx ? { ...x, entity_type: newType } : x
                        );
                        setCharacters(updatedList);
                        if (selectedJobId) {
                          const valid = updatedList
                            .filter((c) => c.name.trim() || c.appearance.trim())
                            .map((c) => ({
                              id: c.id,
                              name: c.name.trim(),
                              appearance: c.appearance.trim(),
                              entity_type: c.entity_type || "character",
                            }));
                          if (valid.length > 0) {
                            api
                              .updateJobAnchors(selectedJobId, { characters: valid })
                              .then(() => {
                                bumpAnchorsRevision();
                              })
                              .catch(() => {});
                          }
                        }
                      }}
                      className="h-7 px-1.5 rounded bg-cinema-card border border-cinema-border text-[11px] text-amber-cta font-medium focus:outline-none focus:border-amber-cta cursor-pointer"
                    >
                      <option value="character">👤 人物</option>
                      <option value="object">📦 物件</option>
                    </select>
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
                    rows={2}
                    value={ch.appearance}
                    onChange={(e) =>
                      setCharacters((prev) =>
                        prev.map((x, i) => (i === idx ? { ...x, appearance: e.target.value } : x))
                      )
                    }
                    placeholder="外觀特徵描述..."
                    className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
                  />
                </div>
              ))}
            </div>
            <div>
              <label className="block text-xs font-medium text-cinema-muted mb-1">環境與光影基調</label>
              <textarea
                rows={2}
                value={environmentAnchor}
                onChange={(e) => setEnvironmentAnchor(e.target.value)}
                placeholder="時代氛圍、空間構造、光影與材質..."
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text font-mono leading-relaxed focus:outline-none focus:border-amber-cta resize-none"
              />
            </div>
          </div>
        )}
      </div>

      {/* 全螢幕視覺風格畫廊彈窗 */}
      {isGalleryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-5xl h-[85vh] flex flex-col rounded-xl bg-cinema-darker border border-cinema-border shadow-2xl overflow-hidden">
            {/* Modal 頂部 Header */}
            <div className="flex items-center justify-between px-6 py-3.5 border-b border-cinema-border bg-cinema-card">
              <div className="flex items-center space-x-2">
                <Palette className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">選擇視覺風格 ({styles.length})</h3>
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
