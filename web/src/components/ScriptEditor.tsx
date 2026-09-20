import React, { useEffect, useState } from "react";
import { Sparkles, Copy, ArrowRight, Loader2, Image as ImageIcon } from "lucide-react";
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

  const [generating, setGenerating] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);

  useEffect(() => {
    api.getTones().then(setTones).catch(() => {});
    api.getVoices().then(setVoices).catch(() => {});
    api.getStyles().then(setStyles).catch(() => {});
  }, []);

  const currentStyleObj = styles.find((s) => s.id === selectedStyle) || styles[0];

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

      {/* 口吻、發音人與風格卡片 (三欄) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

        {/* 目前視覺風格卡片 (縮圖) */}
        <div>
          <label className="block text-xs font-medium text-cinema-muted mb-1.5">目前視覺風格</label>
          <div className="flex items-center space-x-3 p-2 rounded bg-cinema-card border border-cinema-border">
            <div className="w-14 h-9 rounded bg-black/60 overflow-hidden flex-shrink-0">
              {currentStyleObj?.preview_url ? (
                <img
                  src={currentStyleObj.preview_url}
                  alt=""
                  className="w-full h-full object-cover"
                />
              ) : (
                <ImageIcon className="w-full h-full p-2 text-cinema-muted/50" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-cinema-text truncate">
                {currentStyleObj?.name || "預設風格"}
              </div>
              <div className="text-[10px] text-cinema-muted truncate">
                {currentStyleObj?.tags?.join(" · ") || "16:9"}
              </div>
            </div>
            <select
              value={selectedStyle}
              onChange={(e) => setSelectedStyle(e.target.value)}
              className="h-7 text-[11px] rounded bg-cinema-darker border border-cinema-border text-amber-cta px-1.5"
            >
              {styles.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>
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
    </div>
  );
};
