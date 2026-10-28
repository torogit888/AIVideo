import React from "react";
import { Loader2, Save, Sparkles, Trash2, Upload, Volume2, X } from "lucide-react";
import { AssetVoice } from "../types";
import {
  fileToBase64,
  OMNIVOICE_CATEGORIES,
  OMNIVOICE_PRESETS,
  updateVoiceInstructTag,
} from "./AssetsVoiceConfig";

interface AssetsVoicesSectionProps {
  voices: AssetVoice[];
  selectedVoice: AssetVoice | null;
  onSelectVoice: (v: AssetVoice) => void;
  onCloseDrawer: () => void;
  editVoiceName: string;
  setEditVoiceName: (v: string) => void;
  editVoiceGender: string;
  setEditVoiceGender: (v: string) => void;
  editVoiceMode: string;
  setEditVoiceMode: (v: string) => void;
  editVoiceSpeed: number;
  setEditVoiceSpeed: (v: number) => void;
  editVoiceTemp: number;
  setEditVoiceTemp: (v: number) => void;
  editVoiceInstruct: string;
  setEditVoiceInstruct: (v: string) => void;
  editVoiceRefText: string;
  setEditVoiceRefText: (v: string) => void;
  setEditVoiceAudioBase64: (v: string | null) => void;
  localAudioPreviewUrl: string | null;
  setLocalAudioPreviewUrl: (v: string | null) => void;
  testAudioUrl: string | null;
  testingVoice: boolean;
  testSentence: string;
  setTestSentence: (v: string) => void;
  saving: boolean;
  onTestVoice: () => Promise<void>;
  onSaveVoice: () => Promise<void>;
  onDeleteVoice: (id: string, name: string) => Promise<void>;
  isCreateVoiceOpen: boolean;
  setIsCreateVoiceOpen: (open: boolean) => void;
  newVoiceId: string;
  setNewVoiceId: (v: string) => void;
  newVoiceName: string;
  setNewVoiceName: (v: string) => void;
  newVoiceGender: string;
  setNewVoiceGender: (v: string) => void;
  newVoiceMode: string;
  setNewVoiceMode: (v: string) => void;
  newVoiceSpeed: number;
  setNewVoiceSpeed: (v: number) => void;
  newVoiceTemp: number;
  setNewVoiceTemp: (v: number) => void;
  newVoiceInstruct: string;
  setNewVoiceInstruct: (v: string) => void;
  newVoiceRefText: string;
  setNewVoiceRefText: (v: string) => void;
  newVoiceAudioBase64: string | null;
  setNewVoiceAudioBase64: (v: string | null) => void;
  onCreateVoice: () => Promise<void>;
}

export const AssetsVoicesSection: React.FC<AssetsVoicesSectionProps> = ({
  voices,
  selectedVoice,
  onSelectVoice,
  onCloseDrawer,
  editVoiceName,
  setEditVoiceName,
  editVoiceGender,
  setEditVoiceGender,
  editVoiceMode,
  setEditVoiceMode,
  editVoiceSpeed,
  setEditVoiceSpeed,
  editVoiceTemp,
  setEditVoiceTemp,
  editVoiceInstruct,
  setEditVoiceInstruct,
  editVoiceRefText,
  setEditVoiceRefText,
  setEditVoiceAudioBase64,
  localAudioPreviewUrl,
  setLocalAudioPreviewUrl,
  testAudioUrl,
  testingVoice,
  testSentence,
  setTestSentence,
  saving,
  onTestVoice,
  onSaveVoice,
  onDeleteVoice,
  isCreateVoiceOpen,
  setIsCreateVoiceOpen,
  newVoiceId,
  setNewVoiceId,
  newVoiceName,
  setNewVoiceName,
  newVoiceGender,
  setNewVoiceGender,
  newVoiceMode,
  setNewVoiceMode,
  newVoiceSpeed,
  setNewVoiceSpeed,
  newVoiceTemp,
  setNewVoiceTemp,
  newVoiceInstruct,
  setNewVoiceInstruct,
  newVoiceRefText,
  setNewVoiceRefText,
  newVoiceAudioBase64,
  setNewVoiceAudioBase64,
  onCreateVoice,
}) => {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {voices.map((v) => (
          <div
            key={v.id}
            onClick={() => onSelectVoice(v)}
            className={`p-4 rounded-lg bg-cinema-card border cursor-pointer transition-all space-y-2 ${
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
                <span
                  className={`text-[10px] px-2 py-0.5 rounded border ${
                    v.mode === "design"
                      ? "bg-purple-950/60 text-purple-300 border-purple-800"
                      : "bg-cinema-darker text-amber-cta border-cinema-border"
                  }`}
                >
                  {v.mode === "design" ? "語氣設計" : "聲音克隆"}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-cinema-darker text-amber-cta border border-cinema-border">
                  {v.gender}
                </span>
              </div>
            </div>
            {v.mode === "design" && v.voice_instruct && (
              <div className="text-[11px] text-purple-300 font-mono bg-purple-950/30 px-2 py-1 rounded border border-purple-900/40 truncate">
                {v.voice_instruct}
              </div>
            )}
            {v.reference_text && v.mode !== "design" && (
              <p className="text-[11px] text-cinema-muted italic line-clamp-2">「{v.reference_text}」</p>
            )}
            {v.audio_sample_url && (
              <audio
                controls
                src={v.audio_sample_url}
                className="w-full h-8 mt-1"
                onClick={(e) => e.stopPropagation()}
              />
            )}
          </div>
        ))}
      </div>

      {/* 右側編輯發音人音色抽屜 */}
      {selectedVoice && (
        <aside className="fixed right-0 top-12 bottom-0 w-[380px] z-30 flex flex-col border-l border-cinema-border bg-cinema-card p-4 space-y-3 overflow-y-auto shadow-2xl">
          <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
            <div className="flex items-center space-x-2">
              <Volume2 className="w-4 h-4 text-amber-cta" />
              <div>
                <span className="text-xs font-semibold text-cinema-text">編輯發音人</span>
                <div className="text-[10px] font-mono text-cinema-muted">{selectedVoice.id}</div>
              </div>
            </div>
            <button onClick={onCloseDrawer} className="text-cinema-muted hover:text-cinema-text">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="block text-[11px] text-cinema-muted mb-1">顯示名稱</label>
            <input
              type="text"
              value={editVoiceName}
              onChange={(e) => setEditVoiceName(e.target.value)}
              className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-cinema-muted mb-1">性別</label>
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
              <label className="block text-[11px] text-cinema-muted mb-1">模式</label>
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
                <span>語速</span>
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

          {editVoiceMode === "design" ? (
            <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border space-y-2.5">
              <div className="text-xs font-semibold text-cinema-text flex items-center">
                <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-cta" />
                <span>語氣設計</span>
              </div>

              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">快速範本</label>
                <div className="flex flex-wrap gap-1">
                  {OMNIVOICE_PRESETS.map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => {
                        setEditVoiceInstruct(p.instruct);
                        if (p.instruct.includes("男")) setEditVoiceGender("男性");
                        if (p.instruct.includes("女")) setEditVoiceGender("女性");
                      }}
                      className={`px-2 py-0.5 rounded text-[10px] transition-colors border ${
                        editVoiceInstruct === p.instruct
                          ? "bg-amber-cta text-cinema-bg font-semibold border-amber-cta"
                          : "bg-cinema-card hover:bg-cinema-cardHover text-cinema-text border-cinema-border"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {OMNIVOICE_CATEGORIES.map((cat) => (
                <div key={cat.category} className="space-y-1">
                  <label className="block text-[10px] text-cinema-muted">{cat.label}</label>
                  <div className="flex flex-wrap gap-1">
                    {cat.options.map((opt) => {
                      const currentTags = editVoiceInstruct.split(/[,，]/).map((s) => s.trim());
                      const isSelected =
                        opt.value === ""
                          ? !cat.options.some((o) => o.value && currentTags.includes(o.value))
                          : currentTags.includes(opt.value);
                      return (
                        <button
                          key={opt.label}
                          type="button"
                          onClick={() => {
                            const updated = updateVoiceInstructTag(editVoiceInstruct, cat.options, opt.value);
                            setEditVoiceInstruct(updated);
                            if (opt.value === "男") setEditVoiceGender("男性");
                            if (opt.value === "女") setEditVoiceGender("女性");
                          }}
                          className={`px-2 py-1 rounded text-[11px] transition-all border ${
                            isSelected
                              ? "bg-amber-cta/20 text-amber-cta font-medium border-amber-cta/60"
                              : "bg-cinema-card hover:bg-cinema-cardHover text-cinema-muted hover:text-cinema-text border-cinema-border"
                          }`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              <div>
                <div className="flex justify-between items-center text-[11px] text-cinema-muted mb-1">
                  <span>語氣指令</span>
                  <button
                    type="button"
                    onClick={() => setEditVoiceInstruct("女，青年，中音调")}
                    className="text-[10px] text-amber-cta hover:underline"
                  >
                    重設
                  </button>
                </div>
                <textarea
                  value={editVoiceInstruct}
                  onChange={(e) => setEditVoiceInstruct(e.target.value)}
                  rows={2}
                  className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono resize-none focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">參考音逐字稿 (reference.txt)</label>
                <textarea
                  value={editVoiceRefText}
                  onChange={(e) => setEditVoiceRefText(e.target.value)}
                  rows={2}
                  placeholder="與參考音訊吻合的文字..."
                  className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-[11px] text-cinema-muted">
                  <span>參考音訊</span>
                  {localAudioPreviewUrl && <span className="text-amber-cta font-mono text-[10px]">● 已載入新音訊</span>}
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
                  <span>{localAudioPreviewUrl ? "已選取新音訊" : "上傳替換音訊 (WAV/MP3)"}</span>
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
            </>
          )}

          {/* 合成試聽 */}
          <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border space-y-2">
            <span className="text-xs font-semibold text-cinema-text flex items-center">
              <Sparkles className="w-3.5 h-3.5 mr-1 text-amber-cta" />
              <span>合成試聽</span>
            </span>
            <textarea
              value={testSentence}
              onChange={(e) => setTestSentence(e.target.value)}
              rows={2}
              className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
              placeholder="輸入測試語句..."
            />
            <button
              onClick={onTestVoice}
              disabled={testingVoice || saving}
              className="w-full flex items-center justify-center h-8 rounded bg-cinema-card hover:bg-cinema-cardHover border border-amber-cta/40 hover:border-amber-cta text-xs text-amber-cta font-medium transition-all disabled:opacity-50"
            >
              {testingVoice ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>合成中...</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3.5 h-3.5 mr-1.5" />
                  <span>試聽</span>
                </>
              )}
            </button>
            {testAudioUrl && <audio controls src={testAudioUrl} key={testAudioUrl} className="w-full h-8" />}
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <button
              onClick={() => onDeleteVoice(selectedVoice.id, selectedVoice.name)}
              className="flex items-center justify-center h-9 px-3 rounded bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 text-xs transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" />
              <span>刪除</span>
            </button>
            <button
              onClick={onSaveVoice}
              disabled={saving}
              className="flex-1 flex items-center justify-center h-9 rounded bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg font-semibold text-xs tracking-wide transition-all shadow"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" />
              <span>{saving ? "儲存中..." : "儲存設定"}</span>
            </button>
          </div>
        </aside>
      )}

      {/* 新增發音人 Modal */}
      {isCreateVoiceOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-cinema-card border border-cinema-border shadow-2xl p-5 space-y-3.5 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-cinema-border pb-2.5">
              <div className="flex items-center space-x-2">
                <Volume2 className="w-4 h-4 text-amber-cta" />
                <h3 className="text-sm font-semibold text-cinema-text">建立發音人</h3>
              </div>
              <button onClick={() => setIsCreateVoiceOpen(false)} className="text-cinema-muted hover:text-cinema-text">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">英文 ID</label>
                <input
                  type="text"
                  value={newVoiceId}
                  onChange={(e) => setNewVoiceId(e.target.value)}
                  placeholder="例如: host_tw_male"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">顯示名稱</label>
                <input
                  type="text"
                  value={newVoiceName}
                  onChange={(e) => setNewVoiceName(e.target.value)}
                  placeholder="例如：台灣男聲"
                  className="w-full h-8 px-2.5 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-cinema-muted mb-1">性別</label>
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
                <label className="block text-[11px] text-cinema-muted mb-1">模式</label>
                <select
                  value={newVoiceMode}
                  onChange={(e) => setNewVoiceMode(e.target.value)}
                  className="w-full h-8 px-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
                >
                  <option value="clone">聲音克隆 (Clone)</option>
                  <option value="design">語氣設計 (Design)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex justify-between text-[11px] text-cinema-muted mb-1">
                  <span>語速</span>
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

            {newVoiceMode === "design" ? (
              <div className="p-3 rounded-lg bg-cinema-darker border border-cinema-border space-y-2.5">
                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">快速範本</label>
                  <div className="flex flex-wrap gap-1">
                    {OMNIVOICE_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => {
                          setNewVoiceInstruct(p.instruct);
                          if (p.instruct.includes("男")) setNewVoiceGender("男性");
                          if (p.instruct.includes("女")) setNewVoiceGender("女性");
                        }}
                        className={`px-2 py-0.5 rounded text-[10px] transition-colors border ${
                          newVoiceInstruct === p.instruct
                            ? "bg-amber-cta text-cinema-bg font-semibold border-amber-cta"
                            : "bg-cinema-card hover:bg-cinema-cardHover text-cinema-text border-cinema-border"
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                {OMNIVOICE_CATEGORIES.map((cat) => (
                  <div key={cat.category} className="space-y-1">
                    <label className="block text-[10px] text-cinema-muted">{cat.label}</label>
                    <div className="flex flex-wrap gap-1">
                      {cat.options.map((opt) => {
                        const currentTags = newVoiceInstruct.split(/[,，]/).map((s) => s.trim());
                        const isSelected =
                          opt.value === ""
                            ? !cat.options.some((o) => o.value && currentTags.includes(o.value))
                            : currentTags.includes(opt.value);
                        return (
                          <button
                            key={opt.label}
                            type="button"
                            onClick={() => {
                              const updated = updateVoiceInstructTag(newVoiceInstruct, cat.options, opt.value);
                              setNewVoiceInstruct(updated);
                              if (opt.value === "男") setNewVoiceGender("男性");
                              if (opt.value === "女") setNewVoiceGender("女性");
                            }}
                            className={`px-2 py-1 rounded text-[11px] transition-all border ${
                              isSelected
                                ? "bg-amber-cta/20 text-amber-cta font-medium border-amber-cta/60"
                                : "bg-cinema-card hover:bg-cinema-cardHover text-cinema-muted hover:text-cinema-text border-cinema-border"
                            }`}
                          >
                            {opt.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}

                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">語氣指令</label>
                  <textarea
                    value={newVoiceInstruct}
                    onChange={(e) => setNewVoiceInstruct(e.target.value)}
                    rows={2}
                    className="w-full p-2 rounded bg-cinema-card border border-cinema-border text-xs text-cinema-text font-mono resize-none focus:outline-none focus:border-amber-cta"
                  />
                </div>
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-[11px] text-cinema-muted mb-1">參考音訊 (5~15 秒 WAV/MP3)</label>
                  <label className="flex items-center justify-center h-8 rounded border border-cinema-border bg-cinema-darker hover:bg-cinema-cardHover text-xs text-cinema-text cursor-pointer transition-colors">
                    <Upload className="w-3.5 h-3.5 mr-1.5 text-amber-cta" />
                    <span>{newVoiceAudioBase64 ? "已選取音訊" : "選取音訊檔案"}</span>
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
                  <label className="block text-[11px] text-cinema-muted mb-1">參考音逐字稿</label>
                  <textarea
                    value={newVoiceRefText}
                    onChange={(e) => setNewVoiceRefText(e.target.value)}
                    rows={2}
                    placeholder="輸入與音訊一致的文字..."
                    className="w-full p-2 rounded bg-cinema-darker border border-cinema-border text-xs text-cinema-text resize-none focus:outline-none focus:border-amber-cta"
                  />
                </div>
              </>
            )}

            <div className="flex justify-end space-x-2 pt-2 border-t border-cinema-border">
              <button
                onClick={() => setIsCreateVoiceOpen(false)}
                className="px-3.5 py-1.5 rounded hover:bg-cinema-darker text-xs text-cinema-muted hover:text-cinema-text"
              >
                取消
              </button>
              <button
                onClick={onCreateVoice}
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
