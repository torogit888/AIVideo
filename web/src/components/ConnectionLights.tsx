import React, { useEffect, useState } from "react";
import { useStudioStore } from "../store";

function Dot({
  ok,
  label,
  okText = "在線",
  failText = "未連",
}: {
  ok: boolean | null;
  label: string;
  okText?: string;
  failText?: string;
}) {
  const color =
    ok === true
      ? "bg-emerald-400 shadow-[0_0_6px_#34d399]"
      : ok === false
      ? "bg-red-400 shadow-[0_0_6px_#f87171]"
      : "bg-cinema-muted";
  const text = ok === true ? okText : ok === false ? failText : "檢測中";
  return (
    <span className="flex items-center space-x-1" title={`${label} ${text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      <span className="text-[10px] font-mono text-cinema-muted">{label}</span>
    </span>
  );
}

export const ConnectionLights: React.FC<{ compact?: boolean; noPoll?: boolean }> = ({
  compact,
  noPoll,
}) => {
  const { geminiOnline, comfyOnline, apiOnline, refreshConnectionLights } = useStudioStore();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 初次載入時僅檢測 1 次，平時 0 輪詢
  useEffect(() => {
    if (noPoll) return;
    refreshConnectionLights();
  }, [refreshConnectionLights, noPoll]);

  const handleManualRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      await refreshConnectionLights();
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div
      className={`flex items-center ${
        compact ? "space-x-2" : "space-x-3"
      } select-none cursor-pointer hover:opacity-80 transition-opacity ${
        isRefreshing ? "opacity-50 animate-pulse" : ""
      }`}
      onClick={handleManualRefresh}
      title={`點擊手動刷新連線狀態（純按需模式，無背景輪詢）\nAPI: ${apiOnline ? "在線" : "斷線"} · Gemini 憑證: ${
        geminiOnline ? "已設定" : "未設定"
      } · Comfy: ${comfyOnline ? "在線" : "離線"}`}
    >
      <Dot ok={geminiOnline} label="Gemini" okText="憑證已設定" failText="憑證未設定" />
      <Dot ok={comfyOnline} label="Comfy" />
      {!compact && <Dot ok={apiOnline} label="API" />}
    </div>
  );
};
