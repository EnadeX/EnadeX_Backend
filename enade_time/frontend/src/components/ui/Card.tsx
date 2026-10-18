import { type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card p-4", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-3">
      <div>
        <h3 className="text-base font-semibold text-academia-900">{title}</h3>
        {description && (
          <p className="text-xs text-academia-600 mt-0.5">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
