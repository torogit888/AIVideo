import React, { useEffect, useState } from "react";
import { Sparkles, Volume2, BookOpen, Plus } from "lucide-react";
import { api } from "../api";
import { useStudioStore } from "../store";
import { AssetStyle, AssetTone, AssetVoice, AI_TEXT_MODELS } from "../types";
import { AssetsStylesSection } from "./AssetsStylesSection";
import { AssetsTonesSection } from "./AssetsTonesSection";
import { AssetsVoicesSection } from "./AssetsVoicesSection";

export const AssetsView: React.FC = () => {
  const { showToast, requestConfirm, selectedAiModel, setSelectedAiModel } = useStudioStore();
  const [tab, setTab] = useState<"tones" | "voices" | "styles">("styles");

  const [styles, setStyles] = useState<AssetStyle[]>([]);
  const [tones, setTones] = useState<AssetTone[]>([]);
  const [voices, setVoices] = useState<AssetVoice[]>([]);

  // 風格編輯與選取
  const [selectedStyle, setSelectedStyle] = useState<AssetStyle | null>(null);
  const [editStyleName, setEditStyleName] = useState("");
  const [editStyleDesc, setEditStyleDesc] = useState("");
  const [editStylePrompt, setEditStylePrompt] = useState("");
  const [editStyleNegative, setEditStyleNegative] = useState("");
  const [editStylePreviewBase64, setEditStylePreviewBase64] = useState<string | null>(null);
  const [editStylePreviewDisplay, setEditStylePreviewDisplay] = useState<string | null>(null);

  // 口吻編輯與選取
  const [selectedTone, setSelectedTone] = useState<AssetTone | null>(null);
  const [editToneTitle, setEditToneTitle] = useState("");
  const [editToneSummary, setEditToneSummary] = useState("");
  const [editToneTags, setEditToneTags] = useState("");
  const [editToneVoice, setEditToneVoice] = useState("");
  const [editToneContent, setEditToneContent] = useState("");

  // 編輯舊口吻頁籤：'manual' (手動修改) | 're-extract' (AI 逐字稿重新分析覆蓋)
  const [editToneTab, setEditToneTab] = useState<"manual" | "re-extract">("manual");
  const [reExtractText, setReExtractText] = useState("");
  const [reExtractKeepTitle, setReExtractKeepTitle] = useState(true);
  const [reExtracting, setReExtracting] = useState(false);
  const [reExtractMsg, setReExtractMsg] = useState("");

  // 音色編輯與選取
  const [selectedVoice, setSelectedVoice] = useState<AssetVoice | null>(null);
  const [editVoiceName, setEditVoiceName] = useState("");
  const [editVoiceGender, setEditVoiceGender] = useState("女性");
  const [editVoiceMode, setEditVoiceMode] = useState("clone");
  const [editVoiceSpeed, setEditVoiceSpeed] = useState(1.0);
  const [editVoiceTemp, setEditVoiceTemp] = useState(0.1);
  const [editVoiceSteps, setEditVoiceSteps] = useState(32);
  const [editVoiceInstruct, setEditVoiceInstruct] = useState("女，青年，中音调");
  const [editVoiceSubInstruct, setEditVoiceSubInstruct] = useState("");
  const [editVoiceRefText, setEditVoiceRefText] = useState("");
  const [editVoiceAudioBase64, setEditVoiceAudioBase64] = useState<string | null>(null);
  const [localAudioPreviewUrl, setLocalAudioPreviewUrl] = useState<string | null>(null);
  const [testAudioUrl, setTestAudioUrl] = useState<string | null>(null);
  const [testingVoice, setTestingVoice] = useState(false);
  const [testSentence, setTestSentence] = useState(
    "歡迎使用智能影視創作系統，這是一段測試發音人音色與位置溫度的語音合成效果。"
  );

  // 通用狀態
  const [saving, setSaving] = useState(false);

  // 新增 Modal 狀態
  const [isCreateStyleOpen, setIsCreateStyleOpen] = useState(false);
  const [newStyleId, setNewStyleId] = useState("");
  const [newStyleName, setNewStyleName] = useState("");
  const [newStyleDesc, setNewStyleDesc] = useState("");
  const [newStylePrompt, setNewStylePrompt] = useState("賽博龐克霓虹風格，雨夜高對比光影，金屬機械質感，電影感寬銀幕構圖，16:9 橫式構圖");
  const [newStyleNegative, setNewStyleNegative] = useState("文字浮水印、現代3D塑料感、低細節模糊、走形手部");
  const [newStylePreviewBase64, setNewStylePreviewBase64] = useState<string | null>(null);

  const [isCreateToneOpen, setIsCreateToneOpen] = useState(false);
  const [createToneMode, setCreateToneMode] = useState<"vertex" | "manual">("vertex");
  const [extractText, setExtractText] = useState("");
  const [extractToneId, setExtractToneId] = useState("");
  const [extractToneTitle, setExtractToneTitle] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractMsg, setExtractMsg] = useState("");
  const [newToneId, setNewToneId] = useState("");
  const [newToneTitle, setNewToneTitle] = useState("");
  const [newToneSummary, setNewToneSummary] = useState("");
  const [newToneTags, setNewToneTags] = useState("說書, 傳奇, 商業");
  const [newToneVoice, setNewToneVoice] = useState("女，青年，中音调");
  const [newToneContent, setNewToneContent] = useState(`## 核心口白範例文本

> 如果你今天要去吃一頓全世界最頂級奢華的大餐！你敢相信……決定這家餐廳好不好吃的評審，居然是一家「賣輪胎的」嗎？
> 沒錯！就是那個白白胖胖的米其林寶寶！

## 核心句式與語氣特徵
1. 設問製造反差懸念
2. 生動親民的指認
3. 驚天反轉收尾
`);

  const [isCreateVoiceOpen, setIsCreateVoiceOpen] = useState(false);
  const [newVoiceId, setNewVoiceId] = useState("");
  const [newVoiceName, setNewVoiceName] = useState("");
  const [newVoiceGender, setNewVoiceGender] = useState("女性");
  const [newVoiceMode, setNewVoiceMode] = useState("clone");
  const [newVoiceSpeed, setNewVoiceSpeed] = useState(1.0);
  const [newVoiceTemp, setNewVoiceTemp] = useState(0.1);
  const newVoiceSteps = 32;
  const [newVoiceInstruct, setNewVoiceInstruct] = useState("女，青年，中音调");
  const [newVoiceRefText, setNewVoiceRefText] = useState("");
  const [newVoiceAudioBase64, setNewVoiceAudioBase64] = useState<string | null>(null);

  const loadData = () => {
    api.getStyles().then(setStyles).catch(() => {});
    api.getTones().then(setTones).catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
  };

  useEffect(() => {
    loadData();
  }, []);

  // -------------------------
  // 風格 Handlers
  // -------------------------
  const handleSelectStyle = (s: AssetStyle) => {
    setSelectedStyle(s);
    setEditStyleName(s.name);
    setEditStylePrompt(s.prefix || "");
    setEditStyleDesc(s.description || "");
    setEditStyleNegative(s.negative || "");
    setEditStylePreviewBase64(null);
    setEditStylePreviewDisplay(s.preview_url || null);
  };

  const handleSaveStyle = async () => {
    if (!selectedStyle) return;
    setSaving(true);
    try {
      await api.updateStyle(selectedStyle.id, {
        name: editStyleName,
        description: editStyleDesc,
        prefix: editStylePrompt,
        negative: editStyleNegative,
        preview_base64: editStylePreviewBase64,
      });
      showToast("風格已成功儲存！", "success");
      const updated = await api.getStyles();
      setStyles(updated);
      setSelectedStyle(updated.find((x) => x.id === selectedStyle.id) || null);
    } catch (e: any) {
      showToast("儲存失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteStyle = async (id: string, name: string) => {
    const ok = await requestConfirm({
      title: "刪除視覺風格",
      message: `確定要徹底刪除視覺風格【${name} (${id})】嗎？此操作無法復原！`,
      confirmText: "徹底刪除",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await api.deleteStyle(id);
      showToast("已成功刪除視覺風格！", "success");
      setSelectedStyle(null);
      loadData();
    } catch (e: any) {
      showToast("刪除失敗: " + e.message, "error");
    }
  };

  const handleCreateStyle = async () => {
    if (!newStyleId.trim() || !newStyleName.trim() || !newStylePrompt.trim()) {
      showToast("請填寫風格 ID、顯示名稱與正向前綴提示詞！", "error");
      return;
    }
    setSaving(true);
    try {
      await api.createStyle({
        id: newStyleId.trim(),
        name: newStyleName.trim(),
        description: newStyleDesc.trim(),
        prefix: newStylePrompt.trim(),
        negative: newStyleNegative.trim(),
        preview_base64: newStylePreviewBase64,
      });
      showToast("成功建立新視覺風格！已同步至選單。", "success");
      setIsCreateStyleOpen(false);
      setNewStyleId("");
      setNewStyleName("");
      setNewStyleDesc("");
      setNewStylePreviewBase64(null);
      loadData();
    } catch (e: any) {
      showToast("建立風格失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  // -------------------------
  // 口吻 Handlers
  // -------------------------
  const handleSelectTone = (t: AssetTone) => {
    setSelectedTone(t);
    setEditToneTitle(t.title);
    setEditToneSummary(t.summary);
    setEditToneTags(t.tags?.join(", ") || "");
    setEditToneVoice(t.recommended_voice_instruct || "");
    setEditToneContent(t.content);
    setEditToneTab("manual");
    setReExtractText("");
  };

  const handleReExtractTone = async () => {
    if (!selectedTone) return;
    if (!reExtractText.trim()) {
      showToast("請先貼上新的參考逐字稿或載入文字檔！", "error");
      return;
    }
    const currentModelName = AI_TEXT_MODELS.find((m) => m.id === selectedAiModel)?.name || "Gemini Flash";
    setReExtracting(true);
    setReExtractMsg(`Vertex AI (${currentModelName}) 正在重新分析逐字稿並覆蓋寫入專案...`);
    try {
      const updated = await api.extractAndSaveTone({
        text: reExtractText.trim(),
        tone_id: selectedTone.id,
        auto_save: true,
        model: selectedAiModel,
        title: reExtractKeepTitle ? editToneTitle.trim() : undefined,
      });
      showToast(`✨ Vertex AI 已成功重新分析並覆蓋更新：assets/tones/${selectedTone.id}.md`, "success");
      const list = await api.getTones();
      setTones(list);
      handleSelectTone(updated);
      setEditToneTab("manual");
    } catch (e: any) {
      showToast("重新分析失敗: " + e.message, "error");
    } finally {
      setReExtracting(false);
      setReExtractMsg("");
    }
  };

  const handleReExtractFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setReExtractText(content);
        showToast(`已載入文字檔：${file.name} (${content.length} 字)`, "info");
      }
    };
    reader.readAsText(file, "utf-8");
  };

  const handleSaveTone = async () => {
    if (!selectedTone) return;
    setSaving(true);
    try {
      const tagsArray = editToneTags
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      await api.updateTone(selectedTone.id, {
        title: editToneTitle,
        summary: editToneSummary,
        tags: tagsArray,
        recommended_voice_instruct: editToneVoice,
        content: editToneContent,
      });
      showToast("口吻範本已成功更新！", "success");
      const updated = await api.getTones();
      setTones(updated);
      setSelectedTone(updated.find((x) => x.id === selectedTone.id) || null);
    } catch (e: any) {
      showToast("儲存口吻失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTone = async (id: string, title: string) => {
    const ok = await requestConfirm({
      title: "刪除口吻範本",
      message: `確定要徹底刪除口吻範本【${title} (${id})】嗎？此操作無法復原！`,
      confirmText: "徹底刪除",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await api.deleteTone(id);
      showToast("已成功刪除口吻範本！", "success");
      setSelectedTone(null);
      loadData();
    } catch (e: any) {
      showToast("刪除失敗: " + e.message, "error");
    }
  };

  const handleCreateTone = async () => {
    if (!newToneId.trim() || !newToneTitle.trim() || !newToneContent.trim()) {
      showToast("請填寫口吻英文 ID、中文標題與範本 Markdown 內容！", "error");
      return;
    }
    setSaving(true);
    try {
      const tagsArray = newToneTags
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      await api.createTone({
        id: newToneId.trim(),
        title: newToneTitle.trim(),
        summary: newToneSummary.trim(),
        tags: tagsArray,
        recommended_voice_instruct: newToneVoice.trim(),
        content: newToneContent.trim(),
      });
      showToast("成功建立新說書人口吻！", "success");
      setIsCreateToneOpen(false);
      setNewToneId("");
      setNewToneTitle("");
      setNewToneSummary("");
      loadData();
    } catch (e: any) {
      showToast("建立口吻失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleExtractTone = async () => {
    if (!extractText.trim()) {
      showToast("請貼上參考口白/逐字稿或先上傳文字檔！", "error");
      return;
    }
    const currentModelName = AI_TEXT_MODELS.find((m) => m.id === selectedAiModel)?.name || "Gemini Flash";
    setExtracting(true);
    setExtractMsg(`Google Cloud Vertex AI (${currentModelName}) 正在深度分析文本風格與結構規範...`);
    try {
      const created = await api.extractAndSaveTone({
        text: extractText.trim(),
        tone_id: extractToneId.trim() || undefined,
        title: extractToneTitle.trim() || undefined,
        auto_save: true,
        model: selectedAiModel,
      });
      showToast(`✨ Vertex AI (${currentModelName}) 已成功直接寫入專案：assets/tones/${created.id}.md`, "success");
      setIsCreateToneOpen(false);
      setExtractText("");
      setExtractToneId("");
      setExtractToneTitle("");
      await loadData();
      handleSelectTone(created);
    } catch (e: any) {
      showToast("Vertex AI 萃取失敗: " + e.message, "error");
    } finally {
      setExtracting(false);
      setExtractMsg("");
    }
  };

  const handleToneFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setExtractText(content);
        showToast(`已載入文字檔：${file.name} (${content.length} 字)`, "info");
      }
    };
    reader.readAsText(file, "utf-8");
  };

  // -------------------------
  // 音色 Handlers
  // -------------------------
  const handleSelectVoice = (v: AssetVoice) => {
    setSelectedVoice(v);
    setEditVoiceName(v.name);
    setEditVoiceGender(v.gender || "女性");
    setEditVoiceMode(v.mode || "clone");
    setEditVoiceSpeed(v.speed ?? 1.0);
    setEditVoiceTemp(v.position_temperature ?? 0.1);
    setEditVoiceSteps(v.steps ?? 32);
    setEditVoiceInstruct(v.voice_instruct || "女，青年，中音调");
    setEditVoiceSubInstruct(v.instruct || "");
    setEditVoiceRefText(v.reference_text || "");
    setEditVoiceAudioBase64(null);
    setLocalAudioPreviewUrl(null);
    setTestAudioUrl(v.test_audio_url || null);
  };

  const handleTestVoice = async () => {
    if (!selectedVoice) return;
    setTestingVoice(true);
    try {
      // 1. 自動先儲存當前修改之設定（包含新上傳音訊與自訂提示詞）
      await api.updateVoice(selectedVoice.id, {
        name: editVoiceName,
        gender: editVoiceGender,
        mode: editVoiceMode,
        speed: editVoiceSpeed,
        position_temperature: editVoiceTemp,
        steps: editVoiceSteps,
        voice_instruct: editVoiceInstruct.trim(),
        instruct: editVoiceSubInstruct.trim(),
        reference_text: editVoiceRefText,
        audio_base64: editVoiceAudioBase64 || undefined,
      });
      if (editVoiceAudioBase64) {
        setEditVoiceAudioBase64(null);
        setLocalAudioPreviewUrl(null);
      }

      // 2. 觸發 ComfyUI 語音合成測試
      const res = await api.testVoice(selectedVoice.id, {
        text: testSentence,
        speed: editVoiceSpeed,
        position_temperature: editVoiceTemp,
        steps: editVoiceSteps,
        mode: editVoiceMode,
        voice_instruct: editVoiceInstruct.trim(),
        instruct: editVoiceSubInstruct.trim(),
      });
      setTestAudioUrl(res.test_audio_url);
      const updated = await api.getVoices();
      setVoices(updated);
      const matched = updated.find((x) => x.id === selectedVoice.id) || null;
      if (matched) setSelectedVoice(matched);
      showToast("新參數語音合成試聽已就緒！", "success");
    } catch (e: any) {
      showToast("試聽合成失敗: " + (e.message || "未知錯誤"), "error");
    } finally {
      setTestingVoice(false);
    }
  };

  const handleSaveVoice = async () => {
    if (!selectedVoice) return;
    setSaving(true);
    try {
      await api.updateVoice(selectedVoice.id, {
        name: editVoiceName,
        gender: editVoiceGender,
        mode: editVoiceMode,
        speed: editVoiceSpeed,
        position_temperature: editVoiceTemp,
        steps: editVoiceSteps,
        voice_instruct: editVoiceInstruct.trim(),
        instruct: editVoiceSubInstruct.trim(),
        reference_text: editVoiceRefText,
        audio_base64: editVoiceAudioBase64,
      });
      setEditVoiceAudioBase64(null);
      setLocalAudioPreviewUrl(null);
      showToast("發音人音色設定已成功更新！", "success");
      const updated = await api.getVoices();
      setVoices(updated);
      const matched = updated.find((x) => x.id === selectedVoice.id) || null;
      setSelectedVoice(matched);
      if (matched?.test_audio_url) {
        setTestAudioUrl(matched.test_audio_url);
      }
    } catch (e: any) {
      showToast("儲存音色失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteVoice = async (id: string, name: string) => {
    const ok = await requestConfirm({
      title: "刪除發音人音色",
      message: `確定要徹底刪除發音人音色【${name} (${id})】嗎？（將刪除其參考音訊與設定）`,
      confirmText: "徹底刪除",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await api.deleteVoice(id);
      showToast("已成功刪除發音人角色！", "success");
      setSelectedVoice(null);
      loadData();
    } catch (e: any) {
      showToast("刪除失敗: " + e.message, "error");
    }
  };

  const handleCreateVoice = async () => {
    if (!newVoiceId.trim() || !newVoiceName.trim()) {
      showToast("請填寫發音人英文 ID 與顯示名稱！", "error");
      return;
    }
    if (newVoiceMode === "clone" && !newVoiceAudioBase64) {
      showToast("克隆模式必須上傳 5~15 秒乾淨參考音訊 (WAV/MP3)！", "error");
      return;
    }
    setSaving(true);
    try {
      await api.createVoice({
        id: newVoiceId.trim(),
        name: newVoiceName.trim(),
        gender: newVoiceGender,
        mode: newVoiceMode,
        speed: newVoiceSpeed,
        position_temperature: newVoiceTemp,
        steps: newVoiceSteps,
        voice_instruct: newVoiceMode === "design" ? newVoiceInstruct.trim() : undefined,
        reference_text: newVoiceRefText.trim(),
        audio_base64: newVoiceAudioBase64,
      });
      showToast("成功建立新發音人角色庫！", "success");
      setIsCreateVoiceOpen(false);
      setNewVoiceId("");
      setNewVoiceName("");
      setNewVoiceInstruct("女，青年，中音调");
      setNewVoiceRefText("");
      setNewVoiceAudioBase64(null);
      loadData();
    } catch (e: any) {
      showToast("建立音色失敗: " + e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-cinema-bg">
      {/* 左主內容 */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-cinema-text">素材庫</h2>
          <div>
            {tab === "styles" && (
              <button
                onClick={() => setIsCreateStyleOpen(true)}
                className="flex items-center h-8 px-3.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-colors shadow"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                <span>新增視覺風格</span>
              </button>
            )}
            {tab === "tones" && (
              <button
                onClick={() => setIsCreateToneOpen(true)}
                className="flex items-center h-8 px-3.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-colors shadow"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                <span>新增口吻範本</span>
              </button>
            )}
            {tab === "voices" && (
              <button
                onClick={() => setIsCreateVoiceOpen(true)}
                className="flex items-center h-8 px-3.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-colors shadow"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                <span>建立發音人</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab 切換 */}
        <div className="flex items-center space-x-1 border-b border-cinema-border pb-2 text-xs">
          <button
            onClick={() => {
              setTab("tones");
              setSelectedStyle(null);
              setSelectedVoice(null);
            }}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "tones" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            <span>口吻範本</span>
          </button>
          <button
            onClick={() => {
              setTab("voices");
              setSelectedStyle(null);
              setSelectedTone(null);
            }}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "voices" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <Volume2 className="w-3.5 h-3.5 mr-1.5" />
            <span>發音人音色</span>
          </button>
          <button
            onClick={() => {
              setTab("styles");
              setSelectedTone(null);
              setSelectedVoice(null);
            }}
            className={`flex items-center px-4 py-1.5 rounded-md font-medium transition-colors ${
              tab === "styles" ? "bg-cinema-card text-amber-cta" : "text-cinema-muted hover:text-cinema-text"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            <span>視覺風格</span>
          </button>
        </div>

        {/* 視覺風格子元件 */}
        {tab === "styles" && (
          <AssetsStylesSection
            styles={styles}
            selectedStyle={selectedStyle}
            onSelectStyle={handleSelectStyle}
            onCloseDrawer={() => setSelectedStyle(null)}
            editStyleName={editStyleName}
            setEditStyleName={setEditStyleName}
            editStyleDesc={editStyleDesc}
            setEditStyleDesc={setEditStyleDesc}
            editStylePrompt={editStylePrompt}
            setEditStylePrompt={setEditStylePrompt}
            editStyleNegative={editStyleNegative}
            setEditStyleNegative={setEditStyleNegative}
            editStylePreviewDisplay={editStylePreviewDisplay}
            setEditStylePreviewDisplay={setEditStylePreviewDisplay}
            setEditStylePreviewBase64={setEditStylePreviewBase64}
            saving={saving}
            onSaveStyle={handleSaveStyle}
            onDeleteStyle={handleDeleteStyle}
            isCreateStyleOpen={isCreateStyleOpen}
            setIsCreateStyleOpen={setIsCreateStyleOpen}
            newStyleId={newStyleId}
            setNewStyleId={setNewStyleId}
            newStyleName={newStyleName}
            setNewStyleName={setNewStyleName}
            newStyleDesc={newStyleDesc}
            setNewStyleDesc={setNewStyleDesc}
            newStylePrompt={newStylePrompt}
            setNewStylePrompt={setNewStylePrompt}
            newStyleNegative={newStyleNegative}
            setNewStyleNegative={setNewStyleNegative}
            newStylePreviewBase64={newStylePreviewBase64}
            setNewStylePreviewBase64={setNewStylePreviewBase64}
            onCreateStyle={handleCreateStyle}
          />
        )}

        {/* 發音人音色子元件 */}
        {tab === "voices" && (
          <AssetsVoicesSection
            voices={voices}
            selectedVoice={selectedVoice}
            onSelectVoice={handleSelectVoice}
            onCloseDrawer={() => setSelectedVoice(null)}
            editVoiceName={editVoiceName}
            setEditVoiceName={setEditVoiceName}
            editVoiceGender={editVoiceGender}
            setEditVoiceGender={setEditVoiceGender}
            editVoiceMode={editVoiceMode}
            setEditVoiceMode={setEditVoiceMode}
            editVoiceSpeed={editVoiceSpeed}
            setEditVoiceSpeed={setEditVoiceSpeed}
            editVoiceTemp={editVoiceTemp}
            setEditVoiceTemp={setEditVoiceTemp}
            editVoiceInstruct={editVoiceInstruct}
            setEditVoiceInstruct={setEditVoiceInstruct}
            editVoiceRefText={editVoiceRefText}
            setEditVoiceRefText={setEditVoiceRefText}
            setEditVoiceAudioBase64={setEditVoiceAudioBase64}
            localAudioPreviewUrl={localAudioPreviewUrl}
            setLocalAudioPreviewUrl={setLocalAudioPreviewUrl}
            testAudioUrl={testAudioUrl}
            testingVoice={testingVoice}
            testSentence={testSentence}
            setTestSentence={setTestSentence}
            saving={saving}
            onTestVoice={handleTestVoice}
            onSaveVoice={handleSaveVoice}
            onDeleteVoice={handleDeleteVoice}
            isCreateVoiceOpen={isCreateVoiceOpen}
            setIsCreateVoiceOpen={setIsCreateVoiceOpen}
            newVoiceId={newVoiceId}
            setNewVoiceId={setNewVoiceId}
            newVoiceName={newVoiceName}
            setNewVoiceName={setNewVoiceName}
            newVoiceGender={newVoiceGender}
            setNewVoiceGender={setNewVoiceGender}
            newVoiceMode={newVoiceMode}
            setNewVoiceMode={setNewVoiceMode}
            newVoiceSpeed={newVoiceSpeed}
            setNewVoiceSpeed={setNewVoiceSpeed}
            newVoiceTemp={newVoiceTemp}
            setNewVoiceTemp={setNewVoiceTemp}
            newVoiceInstruct={newVoiceInstruct}
            setNewVoiceInstruct={setNewVoiceInstruct}
            newVoiceRefText={newVoiceRefText}
            setNewVoiceRefText={setNewVoiceRefText}
            newVoiceAudioBase64={newVoiceAudioBase64}
            setNewVoiceAudioBase64={setNewVoiceAudioBase64}
            onCreateVoice={handleCreateVoice}
          />
        )}

        {/* 口吻範本子元件 */}
        {tab === "tones" && (
          <AssetsTonesSection
            tones={tones}
            selectedTone={selectedTone}
            onSelectTone={handleSelectTone}
            onCloseDrawer={() => setSelectedTone(null)}
            editToneTitle={editToneTitle}
            setEditToneTitle={setEditToneTitle}
            editToneSummary={editToneSummary}
            setEditToneSummary={setEditToneSummary}
            editToneTags={editToneTags}
            setEditToneTags={setEditToneTags}
            editToneVoice={editToneVoice}
            setEditToneVoice={setEditToneVoice}
            editToneContent={editToneContent}
            setEditToneContent={setEditToneContent}
            editToneTab={editToneTab}
            setEditToneTab={setEditToneTab}
            reExtractText={reExtractText}
            setReExtractText={setReExtractText}
            reExtractKeepTitle={reExtractKeepTitle}
            setReExtractKeepTitle={setReExtractKeepTitle}
            reExtracting={reExtracting}
            reExtractMsg={reExtractMsg}
            onReExtractFileUpload={handleReExtractFileUpload}
            onReExtractTone={handleReExtractTone}
            saving={saving}
            onSaveTone={handleSaveTone}
            onDeleteTone={handleDeleteTone}
            selectedAiModel={selectedAiModel}
            setSelectedAiModel={setSelectedAiModel}
            isCreateToneOpen={isCreateToneOpen}
            setIsCreateToneOpen={setIsCreateToneOpen}
            createToneMode={createToneMode}
            setCreateToneMode={setCreateToneMode}
            extractText={extractText}
            setExtractText={setExtractText}
            extractToneId={extractToneId}
            setExtractToneId={setExtractToneId}
            extractToneTitle={extractToneTitle}
            setExtractToneTitle={setExtractToneTitle}
            extracting={extracting}
            extractMsg={extractMsg}
            onToneFileUpload={handleToneFileUpload}
            onExtractTone={handleExtractTone}
            newToneId={newToneId}
            setNewToneId={setNewToneId}
            newToneTitle={newToneTitle}
            setNewToneTitle={setNewToneTitle}
            newToneSummary={newToneSummary}
            setNewToneSummary={setNewToneSummary}
            newToneTags={newToneTags}
            setNewToneTags={setNewToneTags}
            newToneVoice={newToneVoice}
            setNewToneVoice={setNewToneVoice}
            newToneContent={newToneContent}
            setNewToneContent={setNewToneContent}
            onCreateTone={handleCreateTone}
          />
        )}
      </div>
    </div>
  );
};
