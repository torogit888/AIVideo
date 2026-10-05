import React from "react";
import {
  LayoutDashboard,
  FileText,
  Film,
  PlaySquare,
  Sparkles,
  Settings,
  ChevronLeft,
  ChevronRight,
  Video,
} from "lucide-react";
import { useStudioStore } from "../store";
import { NavTab } from "../types";

interface NavItem {
  key: NavTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { key: "overview", label: "總覽", icon: LayoutDashboard },
  { key: "script", label: "腳本", icon: FileText },
  { key: "storyboard", label: "分鏡", icon: Film },
  { key: "film", label: "成片", icon: PlaySquare },
  { key: "assets", label: "素材", icon: Sparkles },
  { key: "settings", label: "設定", icon: Settings },
];

export const SidebarRail: React.FC = () => {
  const { currentTab, setTab, isSidebarExpanded, toggleSidebar } = useStudioStore();

  return (
    <aside
      className={`relative flex flex-col justify-between border-r border-cinema-border bg-cinema-darker transition-all duration-200 select-none ${
        isSidebarExpanded ? "w-[220px]" : "w-[64px]"
      }`}
    >
      <div>
        <div className="flex h-12 items-center px-4 border-b border-cinema-border/50">
          <div className="flex items-center space-x-2 text-amber-cta font-semibold">
            <Video className="w-5 h-5 flex-shrink-0" />
            {isSidebarExpanded && (
              <span className="text-sm tracking-wide text-cinema-text">
                AIVideo <span className="text-xs text-amber-cta font-mono">Studio</span>
              </span>
            )}
          </div>
        </div>

        <nav className="p-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                title={item.label}
                className={`relative flex items-center w-full h-10 px-3 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-cinema-card text-amber-cta"
                    : "text-cinema-muted hover:text-cinema-text hover:bg-cinema-card/50"
                } ${!isSidebarExpanded && "justify-center px-0"}`}
              >
                {isActive && (
                  <div className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-amber-cta" />
                )}
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-amber-cta" : "text-cinema-muted"}`} />
                {isSidebarExpanded && <span className="ml-3 truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-2 border-t border-cinema-border/50">
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full h-8 rounded text-cinema-muted hover:text-cinema-text hover:bg-cinema-card transition-colors text-xs"
        >
          {isSidebarExpanded ? (
            <>
              <ChevronLeft className="w-4 h-4 mr-1" />
              <span>收合導航</span>
            </>
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
};
