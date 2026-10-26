import React, { useEffect } from "react";
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

  useEffect(() => {
    if (noPoll) return;
    refreshConnectionLights();
    const t = setInterval(refreshConnectionLights, 8000);
    return () => clearInterval(t);
  }, [refreshConnectionLights, noPoll]);

  return (
    <div
      className={`flex items-center ${compact ? "space-x-2" : "space-x-3"} select-none`}
      title={`API ${apiOnline ? "在線" : "斷線"} · Gemini 憑證${geminiOnline ? "已設定（模型可用性請至設定頁檢測）" : "未設定"} · Comfy ${comfyOnline ? "在線" : "離線"}`}
    >
      <Dot ok={geminiOnline} label="Gemini" okText="憑證已設定" failText="憑證未設定" />
      <Dot ok={comfyOnline} label="Comfy" />
      {!compact && <Dot ok={apiOnline} label="API" />}
    </div>
  );
};
