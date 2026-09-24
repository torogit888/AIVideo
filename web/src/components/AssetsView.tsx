import React, { useEffect, useState } from "react";
import {
  Sparkles,
  Image as ImageIcon,
  Volume2,
  BookOpen,
  X,
  Save,
  Plus,
  Trash2,
  Upload,
  Loader2,
  FileText,
} from "lucide-react";
import { api } from "../api";
import { useStudioStore } from "../store";
import { AssetStyle, AssetTone, AssetVoice, AI_TEXT_MODELS } from "../types";

// 輔助函式：檔案轉 base64
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

export const AssetsView: React.FC = () => {
  const { showToast, selectedAiModel, setSelectedAiModel } = useStudioStore();
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
    if (!window.confirm(`確定要徹底刪除視覺風格【${name} (${id})】嗎？此操作無法復原！`)) return;
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
    if (!window.confirm(`確定要徹底刪除口吻範本【${title} (${id})】嗎？此操作無法復原！`)) return;
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
        auto_save: true,
        model: selectedAiModel,
      });
      showToast(`✨ Vertex AI (${currentModelName}) 已成功直接寫入專案：assets/tones/${created.id}.md`, "success");
      setIsCreateToneOpen(false);
      setExtractText("");
      setExtractToneId("");
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
    setEditVoiceRefText(v.reference_text || "");
    setEditVoiceAudioBase64(null);
    setLocalAudioPreviewUrl(null);
    setTestAudioUrl(v.test_audio_url || null);
  };

  const handleTestVoice = async () => {
    if (!selectedVoice) return;
    setTestingVoice(true);
    try {
      // 1. 自動先儲存當前修改之設定（包含新上傳音訊）
      if (editVoiceAudioBase64) {
        await api.updateVoice(selectedVoice.id, {
          name: editVoiceName,
          gender: editVoiceGender,
          mode: editVoiceMode,
          speed: editVoiceSpeed,
          position_temperature: editVoiceTemp,
          steps: editVoiceSteps,
          reference_text: editVoiceRefText,
          audio_base64: editVoiceAudioBase64,
        });
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
    if (!window.confirm(`確定要徹底刪除發音人音色【${name} (${id})】嗎？（將刪除其參考音訊與設定）`)) return;
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
        reference_text: newVoiceRefText.trim(),
        audio_base64: newVoiceAudioBase64,
      });
      showToast("成功建立新發音人角色庫！", "success");
      setIsCreateVoiceOpen(false);
      setNewVoiceId("");
      setNewVoiceName("");
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
          <div>
            <h2 className="text-lg font-semibold text-cinema-text">素材庫與風格資源</h2>
            <p className="text-xs text-cinema-muted">管理 AI 影片創作所需的視覺風格、說書人口吻與發音人音色。</p>
          </div>
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
                <span>建立發音人音色</span>
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
              <div
                key={t.id}
                onClick={() => handleSelectTone(t)}
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
        )}

        {/* 音色列表 */}
        {tab === "voices" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {voices.map((v) => (
              <div
                key={v.id}
                onClick={() => handleSelectVoice(v)}
                className={`p-4 rounded-lg bg-cinema-card border cursor-pointer transition-all space-y-2.5 ${
                  selectedVoice?.id === v.id
                    ? "border-amber-cta ring-2 ring-amber-cta/30"
                    : "border-cinema-border hover:border-cinema-muted"
                }`}
              >
                <div className="flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-cinema-text">{v.name}</h4>
                  <div className="flex items-center space-x-1.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cinema-darker text-cinema-muted border border-cinema-border">
                      {v.id}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-cinema-darker text-amber-cta border border-cinema-border">
                      {v.gender}
                    </span>
                  </div>
                </div>
                {v.reference_text && (
                  <p className="text-[11px] text-cinema-muted italic line-clamp-2">「{v.reference_text}」</p>
                )}
                {v.audio_sample_url && (
                  <audio
                    controls
                    src={v.audio_sample_url}
                    className="w-full h-8 mt-2"
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                <div className="text-[10px] text-cinema-muted/60 text-right pt-1">點擊開啟音色設定與管理 ▾</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 右側編輯風格抽屜 */}
      {selectedStyle && tab === "styles" && (
        <aside className="w-[380px] h-full flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-4 overflow-y-auto">
          <div className="flex justify-between items-center border-b border-cinema-border pb-3">
            <div>
              <span className="text-xs font-semibold text-cinema-text">編輯視覺風格</span>
              <div className="text-[10px] font-mono text-cinema-muted">ID: {selectedStyle.id}</div>
            </div>
            <button onClick={() => setSelectedStyle(null)} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] text-cinema-muted">風格示範預覽圖</label>
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
                <span>點擊更換示範圖片</span>
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
            <label className="block text-[11px] text-cinema-muted mb-1">風格顯示名稱</label>
            <input
              type="text"
              value={editStyleName}
              onChange={(e) => setEditStyleName(e.target.value)}
              className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">風格特色描述</label>
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
            <label className="block text-[11px] text-cinema-muted mb-1">負向過濾詞 (Negative Prompt)</label>
            <textarea
              value={editStyleNegative}
              onChange={(e) => setEditStyleNegative(e.target.value)}
              rows={2}
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <button
              onClick={() => handleDeleteStyle(selectedStyle.id, selectedStyle.name)}
              className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
              title="刪除此風格"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>刪除</span>
            </button>
            <button
              onClick={handleSaveStyle}
              disabled={saving}
              className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" />
              <span>{saving ? "儲存中..." : "儲存變更"}</span>
            </button>
          </div>
        </aside>
      )}

      {/* 右側編輯口吻範本抽屜 */}
      {selectedTone && tab === "tones" && (
        <aside className="w-[440px] h-full flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-3.5 overflow-y-auto">
          <div className="flex justify-between items-center border-b border-cinema-border pb-3">
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-amber-cta" />
              <div>
                <span className="text-xs font-semibold text-cinema-text">編輯說書人口吻</span>
                <div className="text-[10px] font-mono text-cinema-muted">ID: {selectedTone.id}</div>
              </div>
            </div>
            <button onClick={() => setSelectedTone(null)} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 模式切換 Tabs */}
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
              <span>手動修改設定</span>
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
              <span>✨ 逐字稿 AI 重新分析更新</span>
            </button>
          </div>

          {editToneTab === "manual" ? (
            /* 手動修改表單 */
            <>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">口吻中文名稱</label>
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
                  <label className="block text-[11px] text-cinema-muted mb-1">建議發音人指示</label>
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
                <label className="block text-[11px] text-cinema-muted mb-1">簡要描述與特徵</label>
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
                  onClick={() => handleDeleteTone(selectedTone.id, selectedTone.title)}
                  className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
                  title="刪除此口吻"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  <span>刪除</span>
                </button>
                <button
                  onClick={handleSaveTone}
                  disabled={saving}
                  className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
                >
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                  <span>{saving ? "儲存中..." : "儲存口吻變更"}</span>
                </button>
              </div>
            </>
          ) : (
            /* AI 逐字稿重新分析覆蓋面板 */
            <div className="flex-1 flex flex-col space-y-3.5">
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/90 leading-relaxed">
                <div className="flex items-center space-x-1.5 font-semibold text-amber-300 mb-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>覆蓋更新專案檔案</span>
                </div>
                在此貼上新的說書逐字稿，Vertex AI 會重新分析結構特徵與台詞規範，並<strong>直接覆蓋寫入專案原檔案（assets/tones/{selectedTone.id}.md）</strong>。
              </div>

              <div className="flex items-center justify-between">
                <label className="text-[11px] text-cinema-muted font-medium">新參考逐字稿 / 文本</label>
                <label className="cursor-pointer inline-flex items-center px-2 py-0.5 rounded bg-cinema-darker hover:bg-zinc-800 border border-cinema-border text-[10px] text-zinc-300 hover:text-white transition-colors">
                  <Upload className="w-3 h-3 mr-1 text-amber-cta" />
                  <span>載入文字檔 (.txt / .md)</span>
                  <input
                    type="file"
                    accept=".txt,.md"
                    onChange={handleReExtractFileUpload}
                    className="hidden"
                  />
                </label>
              </div>

              <textarea
                value={reExtractText}
                onChange={(e) => setReExtractText(e.target.value)}
                rows={9}
                disabled={reExtracting}
                placeholder="貼上新的影片逐字稿或示範文稿，AI 將重新提煉 7 步成片法、發音人建議與示範台詞..."
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
                    保留原名稱 ({editToneTitle})
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
                        {m.badge} ({m.name})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {reExtracting && (
                <div className="p-3 rounded-lg bg-cinema-darker border border-amber-cta/30 flex items-center space-x-2.5 text-xs text-amber-cta animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>{reExtractMsg || "Vertex AI 正在深度重新分析並覆蓋專案..."}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
                <button
                  onClick={() => setEditToneTab("manual")}
                  disabled={reExtracting}
                  className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
                >
                  返回手動修改
                </button>
                <button
                  onClick={handleReExtractTone}
                  disabled={reExtracting || !reExtractText.trim()}
                  className="flex items-center px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow disabled:opacity-50 transition-all"
                >
                  {reExtracting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      <span>重新分析中...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                      <span>由 Vertex AI 重新分析並覆蓋更新專案</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* 右側編輯發音人音色抽屜 */}
      {selectedVoice && tab === "voices" && (
        <aside className="w-[380px] h-full flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-3.5 overflow-y-auto">
          <div className="flex justify-between items-center border-b border-cinema-border pb-3">
            <div className="flex items-center space-x-2">
              <Volume2 className="w-4 h-4 text-amber-cta" />
              <div>
                <span className="text-xs font-semibold text-cinema-text">編輯發音人音色</span>
                <div className="text-[10px] font-mono text-cinema-muted">ID: {selectedVoice.id}</div>
              </div>
            </div>
            <button onClick={() => setSelectedVoice(null)} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">角色顯示名稱</label>
            <input
              type="text"
              value={editVoiceName}
              onChange={(e) => setEditVoiceName(e.target.value)}
              className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">性別標籤</label>
              <select
                value={editVoiceGender}
                onChange={(e) => setEditVoiceGender(e.target.value)}
                className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
              >
                <option value="女性">女性</option>
                <option value="男性">男性</option>
                <option value="中性">中性</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">合成模式</label>
              <select
                value={editVoiceMode}
                onChange={(e) => setEditVoiceMode(e.target.value)}
                className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
              >
                <option value="clone">聲音克隆 (Clone)</option>
                <option value="design">語氣設計 (Design)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="flex justify-between text-[11px] text-cinema-muted mb-1">
                <span>預設語速</span>
                <span className="font-mono text-amber-cta">{editVoiceSpeed}x</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={editVoiceSpeed}
                onChange={(e) => setEditVoiceSpeed(Number(e.target.value))}
                className="w-full accent-amber-cta cursor-pointer h-6"
              />
            </div>
            <div>
              <div className="flex justify-between text-[11px] text-cinema-muted mb-1">
                <span>位置溫度</span>
                <span className="font-mono text-amber-cta">{editVoiceTemp}</span>
              </div>
              <input
                type="range"
                min={0.0}
                max={1.0}
                step={0.05}
                value={editVoiceTemp}
                onChange={(e) => setEditVoiceTemp(Number(e.target.value))}
                className="w-full accent-amber-cta cursor-pointer h-6"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">
              參考音逐字稿 (reference.txt - 克隆模式必備)
            </label>
            <textarea
              value={editVoiceRefText}
              onChange={(e) => setEditVoiceRefText(e.target.value)}
              rows={3}
              placeholder="輸入與參考音訊 100% 吻合的中文文字..."
              className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between items-center text-[11px] text-cinema-muted">
              <span>參考音訊試聽與替換</span>
              {localAudioPreviewUrl && (
                <span className="text-amber-cta font-mono text-[10px]">● 已載入本機新音訊</span>
              )}
            </div>
            {(localAudioPreviewUrl || selectedVoice.audio_sample_url) && (
              <audio
                controls
                src={localAudioPreviewUrl || selectedVoice.audio_sample_url}
                key={localAudioPreviewUrl || selectedVoice.audio_sample_url}
                className="w-full h-8"
              />
            )}
            <label className="flex items-center justify-center h-8 rounded border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-xs text-cinema-text cursor-pointer transition-colors">
              <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
              <span>{localAudioPreviewUrl ? "已載入新音訊（可立即在上方試聽）" : "上傳替換參考音訊 (WAV/MP3)"}</span>
              <input
                type="file"
                accept="audio/*"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const objectUrl = URL.createObjectURL(file);
                    setLocalAudioPreviewUrl(objectUrl);
                    const b64 = await fileToBase64(file);
                    setEditVoiceAudioBase64(b64);
                  }
                }}
              />
            </label>
          </div>

          {/* 即時合成試聽區塊 */}
          <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-cinema-text flex items-center">
                <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-cta" />
                <span>合成試聽 (Audition)</span>
              </span>
              <span className="text-[10px] text-cinema-muted">依目前位置溫度即時合成</span>
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">測試朗讀台詞</label>
              <textarea
                value={testSentence}
                onChange={(e) => setTestSentence(e.target.value)}
                rows={2}
                className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                placeholder="輸入測試語句..."
              />
            </div>

            <button
              onClick={handleTestVoice}
              disabled={testingVoice || saving}
              className="w-full flex items-center justify-center h-8 rounded bg-cinema-card hover:bg-cinema-cardHover border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium transition-all shadow-sm active:scale-98 disabled:opacity-50"
            >
              {testingVoice ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>ComfyUI 合成中 (約 5~10 秒)...</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3.5 h-3.5 mr-1.5" />
                  <span>生成新參數試聽效果</span>
                </>
              )}
            </button>

            {testAudioUrl && (
              <div className="pt-1.5 space-y-1">
                <div className="flex justify-between items-center text-[10px] text-cinema-muted">
                  <span className="text-emerald-400 font-medium">🟢 最新合成試聽結果：</span>
                </div>
                <audio controls src={testAudioUrl} key={testAudioUrl} className="w-full h-8" />
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <button
              onClick={() => handleDeleteVoice(selectedVoice.id, selectedVoice.name)}
              className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
              title="刪除此發音人角色"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>刪除</span>
            </button>
            <button
              onClick={handleSaveVoice}
              disabled={saving}
              className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" />
              <span>{saving ? "儲存中..." : "儲存音色設定"}</span>
            </button>
          </div>
        </aside>
      )}

      {/* -------------------------
          新增視覺風格 Modal
         ------------------------- */}
      {isCreateStyleOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cinema-border pb-3">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">新增畫面視覺風格 (Style)</h3>
              </div>
              <button onClick={() => setIsCreateStyleOpen(false)} className="text-cinema-muted hover:text-cinema-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">英文 ID (如: makoto_watercolor)</label>
                <input
                  type="text"
                  value={newStyleId}
                  onChange={(e) => setNewStyleId(e.target.value)}
                  placeholder="英數與底線"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">風格顯示名稱</label>
                <input
                  type="text"
                  value={newStyleName}
                  onChange={(e) => setNewStyleName(e.target.value)}
                  placeholder="例如：新海誠水彩唯美風"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">風格特徵描述</label>
              <textarea
                value={newStyleDesc}
                onChange={(e) => setNewStyleDesc(e.target.value)}
                rows={2}
                placeholder="簡述畫風特色（如：光影、鏡頭氛圍、適用題材等）"
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
              <label className="block text-[11px] text-cinema-muted mb-1">負向過濾詞 (Negative Prompt)</label>
              <textarea
                value={newStyleNegative}
                onChange={(e) => setNewStyleNegative(e.target.value)}
                rows={2}
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border font-mono text-[11px] text-zinc-300 resize-none focus:outline-none focus:border-amber-cta"
              />
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">上傳風格示範預覽圖 (可選，JPG/PNG)</label>
              <label className="flex items-center justify-center h-9 rounded border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-xs text-cinema-text cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
                <span>{newStylePreviewBase64 ? "已選取預覽圖片" : "選取本機示範圖片"}</span>
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
                onClick={handleCreateStyle}
                disabled={saving}
                className="px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow"
              >
                {saving ? "建立中..." : "確認建立風格"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* -------------------------
          新增口吻範本 Modal
         ------------------------- */}
      {isCreateToneOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cinema-border pb-3">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">新增說書人口吻範本 (Tone)</h3>
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

            {/* 模式切換 Tabs */}
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
                <span>✨ Vertex AI 智慧萃取直接寫入 (推薦)</span>
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
                <span>手動填寫欄位</span>
              </button>
            </div>

            {createToneMode === "vertex" ? (
              /* Vertex AI 智慧萃取面板 */
              <div className="space-y-3.5 pt-1">
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/90 leading-relaxed">
                  <div className="flex items-center space-x-1.5 font-semibold text-amber-300 mb-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Vertex AI (Gemini Flash) 直接寫入專案</span>
                  </div>
                  輸入參考口白文字或上傳文字檔，Vertex AI 會自動分析語言節奏、敘事公式、發音人建議，並提煉成專案標準規範，<strong>直接儲存入專案 assets/tones/ 目錄</strong>。
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-cinema-muted font-medium">參考文本 / 說書逐字稿</label>
                  <label className="cursor-pointer inline-flex items-center px-2.5 py-1 rounded bg-cinema-darker hover:bg-zinc-800 border border-cinema-border text-[11px] text-zinc-300 hover:text-white transition-colors">
                    <Upload className="w-3 h-3 mr-1 text-amber-cta" />
                    <span>上傳文字檔 (.txt / .md)</span>
                    <input
                      type="file"
                      accept=".txt,.md"
                      onChange={handleToneFileUpload}
                      className="hidden"
                    />
                  </label>
                </div>

                <textarea
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  rows={8}
                  disabled={extracting}
                  placeholder="在此直接貼上您喜愛的說書影片逐字稿、範例故事或文稿段落（或點擊上方按鈕載入文字檔）..."
                  className="w-full p-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta leading-relaxed"
                />

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">
                      指定口吻英文 ID (選填，留空自動命名)
                    </label>
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
                    <label className="block text-[11px] text-cinema-muted mb-1">
                      Vertex AI 模型 (Gemini Flash)
                    </label>
                    <select
                      value={selectedAiModel}
                      onChange={(e) => setSelectedAiModel(e.target.value)}
                      disabled={extracting}
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium focus:outline-none focus:border-amber-cta cursor-pointer"
                    >
                      {AI_TEXT_MODELS.map((m) => (
                        <option key={m.id} value={m.id} className="bg-cinema-card text-cinema-text">
                          {m.name} ({m.badge})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {extracting && (
                  <div className="p-3 rounded-lg bg-cinema-darker border border-amber-cta/30 flex items-center space-x-2.5 text-xs text-amber-cta animate-pulse">
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>{extractMsg || "Vertex AI Gemini Flash 正在深度分析並寫入專案..."}</span>
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
                    onClick={handleExtractTone}
                    disabled={extracting || !extractText.trim()}
                    className="flex items-center px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow disabled:opacity-50 transition-all"
                  >
                    {extracting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        <span>萃取寫入中...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                        <span>由 Vertex AI Gemini Flash 萃取並直接寫入專案</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* 手動填寫面板 */
              <div className="space-y-3.5 pt-1">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">口吻英文 ID (如: tech_future)</label>
                    <input
                      type="text"
                      value={newToneId}
                      onChange={(e) => setNewToneId(e.target.value)}
                      placeholder="英數與底線"
                      className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-cinema-muted mb-1">口吻中文名稱</label>
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
                    <label className="block text-[11px] text-cinema-muted mb-1">建議發音人指示</label>
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
                  <label className="block text-[11px] text-cinema-muted mb-1">口吻簡短描述</label>
                  <textarea
                    value={newToneSummary}
                    onChange={(e) => setNewToneSummary(e.target.value)}
                    rows={2}
                    placeholder="描述此口吻的破題節奏、語言特色與適用故事題材"
                    className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">口白範本與句式結構 (Markdown)</label>
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
                    onClick={handleCreateTone}
                    disabled={saving}
                    className="px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow"
                  >
                    {saving ? "建立中..." : "確認建立口吻"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* -------------------------
          新增發音人音色 Modal
         ------------------------- */}
      {isCreateVoiceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cinema-border pb-3">
              <div className="flex items-center space-x-2">
                <Volume2 className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">建立新發音人角色庫 (OmniVoice)</h3>
              </div>
              <button onClick={() => setIsCreateVoiceOpen(false)} className="text-cinema-muted hover:text-cinema-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">音色英文 ID (如: host_tw_male)</label>
                <input
                  type="text"
                  value={newVoiceId}
                  onChange={(e) => setNewVoiceId(e.target.value)}
                  placeholder="英數與底線"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">角色顯示名稱</label>
                <input
                  type="text"
                  value={newVoiceName}
                  onChange={(e) => setNewVoiceName(e.target.value)}
                  placeholder="例如：旁白・台灣中年男聲"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">性別標籤</label>
                <select
                  value={newVoiceGender}
                  onChange={(e) => setNewVoiceGender(e.target.value)}
                  className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                >
                  <option value="女性">女性</option>
                  <option value="男性">男性</option>
                  <option value="中性">中性</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">合成模式</label>
                <select
                  value={newVoiceMode}
                  onChange={(e) => setNewVoiceMode(e.target.value)}
                  className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                >
                  <option value="clone">聲音克隆 (Voice Clone - 推薦)</option>
                  <option value="design">語氣設計 (Voice Design)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between text-[11px] text-cinema-muted mb-1">
                  <span>預設語速</span>
                  <span className="font-mono text-amber-cta">{newVoiceSpeed}x</span>
                </div>
                <input
                  type="range"
                  min={0.5}
                  max={2.0}
                  step={0.05}
                  value={newVoiceSpeed}
                  onChange={(e) => setNewVoiceSpeed(Number(e.target.value))}
                  className="w-full accent-amber-cta cursor-pointer h-6"
                />
              </div>
              <div>
                <div className="flex justify-between text-[11px] text-cinema-muted mb-1">
                  <span>位置溫度</span>
                  <span className="font-mono text-amber-cta">{newVoiceTemp}</span>
                </div>
                <input
                  type="range"
                  min={0.0}
                  max={1.0}
                  step={0.05}
                  value={newVoiceTemp}
                  onChange={(e) => setNewVoiceTemp(Number(e.target.value))}
                  className="w-full accent-amber-cta cursor-pointer h-6"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">
                上傳 5~15 秒乾淨參考音訊 (WAV/MP3，無背景音樂)
              </label>
              <label className="flex items-center justify-center h-9 rounded border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-xs text-cinema-text cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
                <span>{newVoiceAudioBase64 ? "已選取參考音訊檔" : "選取音訊檔案 (WAV/MP3)"}</span>
                <input
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const b64 = await fileToBase64(file);
                      setNewVoiceAudioBase64(b64);
                    }
                  }}
                />
              </label>
            </div>

            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">
                參考音逐字稿 (字詞需與上傳音訊完全吻合)
              </label>
              <textarea
                value={newVoiceRefText}
                onChange={(e) => setNewVoiceRefText(e.target.value)}
                rows={2}
                placeholder="例如：2012 年，美國國家偵察局突然打電話給 NASA..."
                className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
              <button
                onClick={() => setIsCreateVoiceOpen(false)}
                className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
              >
                取消
              </button>
              <button
                onClick={handleCreateVoice}
                disabled={saving}
                className="px-4 py-1.5 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide shadow"
              >
                {saving ? "建立中..." : "確認建立角色庫"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
