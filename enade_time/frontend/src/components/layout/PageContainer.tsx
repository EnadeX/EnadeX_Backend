import { type ReactNode } from "react";

export function PageContainer({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-academia-900">{title}</h2>
          {description && (
            <p className="text-sm text-academia-600 mt-1 max-w-3xl">
              {description}
            </p>
          )}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}
