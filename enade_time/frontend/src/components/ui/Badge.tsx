import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-academia-100 text-academia-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-red-100 text-red-700",
  info: "bg-academia-100 text-academia-700",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
