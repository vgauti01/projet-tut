import { MessageSquare, Search } from "lucide-react";
import { AppMode } from "../types";

interface ModeSwitcherProps {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}

export const ModeSwitcher = ({ mode, onChange }: ModeSwitcherProps) => {
  return (
    <div className="flex items-center bg-muted/50 border border-border rounded-xl p-1">
      <button
        onClick={() => onChange("chat")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
          mode === "chat"
            ? "bg-blue-600 text-white shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <MessageSquare size={14} />
        Chat
      </button>
      <button
        onClick={() => onChange("search")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
          mode === "search"
            ? "bg-blue-600 text-white shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <Search size={14} />
        Recherche
      </button>
    </div>
  );
};
