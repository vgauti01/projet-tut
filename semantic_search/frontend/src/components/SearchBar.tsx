import { Search, Loader2 } from "lucide-react";
import { cn } from "./ui-utils";

interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
  onSearch: () => void;
  loading: boolean;
  hasResults: boolean;
}

export const SearchBar = ({ value, onChange, onSearch, loading, hasResults }: SearchBarProps) => {
  return (
    <div className={cn(
      "w-full max-w-2xl mx-auto transition-all duration-500 ease-out",
      hasResults ? "translate-y-0" : "translate-y-[20vh]"
    )}>
      {!hasResults && (
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            Hybrid Knowledge Base
          </h1>
          <p className="text-muted-foreground">
            Search across your technical documentation using AI.
          </p>
        </div>
      )}

      <div className="relative group">
        <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        <div className="relative flex items-center bg-muted/50 border border-border rounded-2xl shadow-2xl overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500/50 transition-all">
          <Search className="ml-4 text-muted-foreground w-5 h-5" />
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
            placeholder="Ask anything (e.g., 'Power consumption in standby mode?')..."
            className="w-full bg-transparent border-none px-4 py-4 text-lg focus:outline-none placeholder:text-muted-foreground/50 text-foreground"
          />
          <div className="pr-2">
            <button
              onClick={onSearch}
              disabled={loading || !value.trim()}
              className="p-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <div className="px-3 text-sm font-medium">Search</div>
              )}
            </button>
          </div>
        </div>
      </div>

      {!hasResults && (
        <div className="mt-8 flex justify-center gap-2 text-xs text-muted-foreground/60">
          <span className="bg-muted px-2 py-1 rounded-md border border-border">BM25 Lexical</span>
          <span>+</span>
          <span className="bg-muted px-2 py-1 rounded-md border border-border">Vector Embeddings</span>
          <span>+</span>
          <span className="bg-muted px-2 py-1 rounded-md border border-border">Cross-Encoder Reranking</span>
        </div>
      )}
    </div>
  );
};
