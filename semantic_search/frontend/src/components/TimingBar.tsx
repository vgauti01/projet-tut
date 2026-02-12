import { Clock, Search, Database, Shuffle, BarChart3, Cpu } from "lucide-react";
import { SearchTimings } from "../types";

const SEARCH_MODE_LABELS: Record<string, string> = {
  hybrid: "Hybride",
  meili_only: "BM25 uniquement",
  qdrant_only: "Vectoriel uniquement",
  failed: "Échec",
};

const SEARCH_MODE_COLORS: Record<string, string> = {
  hybrid: "text-green-400",
  meili_only: "text-amber-400",
  qdrant_only: "text-amber-400",
  failed: "text-red-400",
};

interface TimingPillProps {
  icon: React.ReactNode;
  label: string;
  value: number | undefined;
}

const TimingPill = ({ icon, label, value }: TimingPillProps) => {
  if (value === undefined) return null;
  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-muted/50 border border-border/50 rounded-md text-[11px] text-muted-foreground">
      {icon}
      <span className="font-medium text-foreground/70">{label}</span>
      <span className="text-blue-400 font-mono">{value.toFixed(0)}ms</span>
    </div>
  );
};

interface TimingBarProps {
  timings?: SearchTimings;
  searchMode?: string;
  variant?: "inline" | "block";
}

export const TimingBar = ({ timings, searchMode, variant = "inline" }: TimingBarProps) => {
  if (!timings && !searchMode) return null;

  const modeLabel = searchMode ? SEARCH_MODE_LABELS[searchMode] || searchMode : null;
  const modeColor = searchMode ? SEARCH_MODE_COLORS[searchMode] || "text-muted-foreground" : "";

  const totalSearch =
    (timings?.meilisearch_ms || 0) +
    (timings?.qdrant_ms || 0) +
    (timings?.rrf_fusion_ms || 0) +
    (timings?.reranking_ms || 0);

  const isBlock = variant === "block";

  return (
    <div
      className={`flex ${isBlock ? "flex-col gap-2" : "flex-wrap items-center gap-1.5"} text-[11px]`}
    >
      {/* Search mode badge */}
      {modeLabel && (
        <div
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-border/50 font-medium ${modeColor} bg-muted/30`}
        >
          <Search size={10} />
          <span>Mode : {modeLabel}</span>
        </div>
      )}

      {/* Timing pills */}
      {timings && (
        <div className="flex flex-wrap items-center gap-1.5">
          <TimingPill
            icon={<Database size={10} />}
            label="Meilisearch"
            value={timings.meilisearch_ms}
          />
          <TimingPill
            icon={<Database size={10} />}
            label="Qdrant"
            value={timings.qdrant_ms}
          />
          <TimingPill
            icon={<Shuffle size={10} />}
            label="RRF Fusion"
            value={timings.rrf_fusion_ms}
          />
          <TimingPill
            icon={<BarChart3 size={10} />}
            label="Reranking"
            value={timings.reranking_ms}
          />
          <TimingPill
            icon={<Cpu size={10} />}
            label="LLM TTFT"
            value={timings.llm_ttft_ms}
          />
          <TimingPill
            icon={<Cpu size={10} />}
            label="LLM Total"
            value={timings.llm_total_ms}
          />

          {/* Total search time */}
          {totalSearch > 0 && (
            <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-500/10 border border-blue-500/20 rounded-md text-[11px] text-blue-400">
              <Clock size={10} />
              <span className="font-medium">Total recherche</span>
              <span className="font-mono">{totalSearch.toFixed(0)}ms</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
