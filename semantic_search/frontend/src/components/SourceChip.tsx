import { FileText } from "lucide-react";
import { Source } from "../types";

interface SourceChipProps {
  source: Source;
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  docx: "Word",
  xlsx: "Excel",
  pptx: "PowerPoint",
  csv: "CSV",
  txt: "Texte",
};

export const SourceChip = ({ source }: SourceChipProps) => {
  const typeLabel = SOURCE_TYPE_LABELS[source.source_type || "pdf"] || source.source_type || "PDF";

  return (
    <div className="group/chip relative inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-400 hover:bg-blue-500/20 transition-colors cursor-default">
      <FileText size={12} />
      <span>
        {source.title}, p.{source.page}
      </span>
      <span className="text-blue-400/50">({typeLabel})</span>

      {/* Tooltip on hover */}
      {source.content_preview && (
        <div className="absolute bottom-full left-0 mb-2 w-72 p-3 bg-popover border border-border rounded-lg shadow-xl text-xs text-muted-foreground opacity-0 group-hover/chip:opacity-100 pointer-events-none transition-opacity z-50">
          <div className="font-medium text-foreground mb-1">
            {source.title} — page {source.page}
          </div>
          <div className="line-clamp-4">{source.content_preview}</div>
          <div className="mt-1 text-blue-400">
            Pertinence: {(source.score * 100).toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
};
