import { type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "@/lib/cn";

type Tone = "default" | "primary" | "success" | "warning";

const TONE_BG: Record<Tone, string> = {
  default: "bg-white",
  primary: "bg-academia-700 text-white",
  success: "bg-emerald-600 text-white",
  warning: "bg-amber-500 text-white",
};

const TONE_LABEL: Record<Tone, string> = {
  default: "text-academia-500",
  primary: "text-academia-100",
  success: "text-emerald-100",
  warning: "text-amber-50",
};

const TONE_ICON: Record<Tone, string> = {
  default: "text-academia-400",
  primary: "text-academia-200",
  success: "text-emerald-100",
  warning: "text-amber-50",
};

export function MetricCard({
  label,
  value,
  unit,
  icon: Icon,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  icon?: LucideIcon;
  hint?: ReactNode;
  tone?: Tone;
}) {
  return (
    <div
      className={cn(
        "card p-4 flex flex-col gap-1 border",
        TONE_BG[tone],
        tone === "default" ? "border-academia-100" : "border-transparent",
      )}
    >
      <div className="flex items-center justify-between">
        <span className={cn("text-xs uppercase tracking-wide font-medium", TONE_LABEL[tone])}>
          {label}
        </span>
        {Icon && <Icon className={cn("h-4 w-4", TONE_ICON[tone])} aria-hidden />}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold leading-tight">{value}</span>
        {unit && (
          <span className={cn("text-xs", TONE_LABEL[tone])}>{unit}</span>
        )}
      </div>
      {hint && (
        <span className={cn("text-xs", TONE_LABEL[tone])}>{hint}</span>
      )}
    </div>
  );
}
