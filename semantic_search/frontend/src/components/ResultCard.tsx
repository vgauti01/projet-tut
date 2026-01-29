import { motion } from "framer-motion";
import { FileText, ArrowUpRight } from "lucide-react";
import { Badge } from "./ui-utils";

interface Source {
  title: string;
  page: number;
  path: string;
  score: number;
}

interface Excerpt {
  content: string;
  source: Source;
  relevance_score: number;
}

interface ResultCardProps {
  excerpt: Excerpt;
  index: number;
}

export const ResultCard = ({ excerpt, index }: ResultCardProps) => {
  // Transformation du markdown **text** en HTML pour le style
  const formattedContent = excerpt.content.replace(
    /\*\*(.*?)\*\*/g,
    '<span class="highlight-text">$1</span>'
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className="group relative bg-card border border-border/50 rounded-xl p-5 hover:border-blue-500/30 hover:bg-muted/30 transition-all duration-300"
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 group-hover:scale-110 transition-transform">
            <FileText size={18} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-foreground/90 leading-none mb-1">
              {excerpt.source.title}
            </h3>
            <p className="text-xs text-muted-foreground">
              Page {excerpt.source.page} • PDF Document
            </p>
          </div>
        </div>
        <Badge score={excerpt.relevance_score} />
      </div>

      <div 
        className="text-sm text-muted-foreground leading-relaxed mb-4 pl-1"
        dangerouslySetInnerHTML={{ __html: formattedContent }}
      />

      <div className="flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
        <button className="flex items-center gap-1 text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors">
          View Context <ArrowUpRight size={12} />
        </button>
      </div>
    </motion.div>
  );
};
