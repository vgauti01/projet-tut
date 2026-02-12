import { FileText, Maximize2 } from "lucide-react";
import { Source } from "../types";
import { useState } from "react";

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
  const [showFullContent, setShowFullContent] = useState(false);
  const hasFullContent = source.full_content && source.full_content !== source.content_preview;

  return (
    <>
      <div className="group/chip relative inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-400 hover:bg-blue-500/20 transition-colors cursor-default">
        <FileText size={12} />
        <span>
          {source.title}, p.{source.page}
        </span>
        <span className="text-blue-400/50">({typeLabel})</span>
        
        {/* Bouton pour voir le contenu complet */}
        {hasFullContent && (
          <button
            onClick={() => setShowFullContent(true)}
            className="ml-1 p-0.5 hover:bg-blue-500/30 rounded transition-colors"
            title="Voir l'extrait complet"
          >
            <Maximize2 size={10} />
          </button>
        )}

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

      {/* Modal pour le contenu complet */}
      {showFullContent && hasFullContent && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] p-4"
          onClick={() => setShowFullContent(false)}
        >
          <div 
            className="bg-background border border-border rounded-lg shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="px-6 py-4 border-b border-border flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-foreground">
                  {source.title}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Page {source.page} · {typeLabel} · Pertinence: {(source.score * 100).toFixed(1)}%
                </p>
              </div>
              <button
                onClick={() => setShowFullContent(false)}
                className="text-muted-foreground hover:text-foreground transition-colors text-xl leading-none"
              >
                ×
              </button>
            </div>

            {/* Content */}
            <div className="px-6 py-4 overflow-y-auto flex-1">
              <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                {source.full_content}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-border flex justify-end">
              <button
                onClick={() => setShowFullContent(false)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
