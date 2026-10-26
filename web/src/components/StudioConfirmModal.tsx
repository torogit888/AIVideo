import React, { useEffect, useState } from "react";
import { AlertCircle, Info } from "lucide-react";
import { useStudioStore } from "../store";

export const StudioConfirmModal: React.FC = () => {
  const { confirmDialog, closeConfirmDialog } = useStudioStore();
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (confirmDialog?.isOpen) {
      setInputValue(confirmDialog.defaultValue || "");
    }
  }, [confirmDialog]);

  useEffect(() => {
    if (!confirmDialog?.isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeConfirmDialog(confirmDialog.mode === "prompt" ? null : false);
      } else if (e.key === "Enter" && confirmDialog.mode === "confirm") {
        e.preventDefault();
        closeConfirmDialog(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmDialog, closeConfirmDialog]);

  if (!confirmDialog?.isOpen) return null;

  const isDanger = confirmDialog.variant === "danger";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      onClick={() => closeConfirmDialog(confirmDialog.mode === "prompt" ? null : false)}
    >
      <div
        className="w-full max-w-md rounded-xl bg-cinema-card border border-cinema-border shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 pt-5 pb-4 space-y-3">
          <div className="flex items-center gap-2.5">
            {isDanger ? (
              <div className="w-8 h-8 rounded-lg bg-red-950/80 border border-red-800/70 flex items-center justify-center shrink-0">
                <AlertCircle className="w-4 h-4 text-red-400" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
                <Info className="w-4 h-4 text-amber-cta" />
              </div>
            )}
            <h3 className="text-sm font-semibold text-cinema-text">{confirmDialog.title}</h3>
          </div>

          <p className="text-xs text-cinema-muted leading-relaxed whitespace-pre-line pl-0.5">
            {confirmDialog.message}
          </p>

          {confirmDialog.mode === "prompt" && (
            <input
              type="text"
              autoFocus
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  closeConfirmDialog(inputValue);
                }
              }}
              placeholder={confirmDialog.placeholder || "請輸入..."}
              className="w-full px-3 py-2 rounded-lg bg-cinema-bg border border-cinema-border text-xs text-cinema-text focus:outline-none focus:border-amber-cta"
            />
          )}
        </div>

        <div className="px-5 py-3 bg-cinema-darker/80 border-t border-cinema-border flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => closeConfirmDialog(confirmDialog.mode === "prompt" ? null : false)}
            className="px-3.5 py-1.5 rounded-lg bg-cinema-bg hover:bg-zinc-800 border border-cinema-border text-xs text-cinema-muted hover:text-cinema-text transition-colors"
          >
            {confirmDialog.cancelText}
          </button>
          <button
            type="button"
            onClick={() =>
              closeConfirmDialog(confirmDialog.mode === "prompt" ? inputValue : true)
            }
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow ${
              isDanger
                ? "bg-red-600 hover:bg-red-500 text-white"
                : "bg-amber-cta hover:bg-amber-ctaHover text-cinema-bg"
            }`}
          >
            {confirmDialog.confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
