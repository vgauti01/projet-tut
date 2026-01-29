import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const Badge = ({ score }: { score: number }) => {
  let colorClass = "bg-gray-500/10 text-gray-400 border-gray-500/20";
  let label = "Low";

  if (score > 80) {
    colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    label = "High";
  } else if (score > 50) {
    colorClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    label = "Medium";
  }

  return (
    <div className={cn("flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-medium", colorClass)}>
      <div className="w-1.5 h-1.5 rounded-full bg-current" />
      <span>{score.toFixed(1)}% Match</span>
    </div>
  );
};
