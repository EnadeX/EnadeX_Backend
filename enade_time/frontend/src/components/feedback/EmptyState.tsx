import { Inbox } from "lucide-react";
import { type ReactNode } from "react";

export function EmptyState({
  title = "Nenhum dado encontrado",
  description,
}: {
  title?: string;
  description?: ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center justify-center text-center py-10">
      <Inbox className="h-8 w-8 text-academia-400 mb-2" aria-hidden />
      <p className="text-sm font-medium text-academia-700">{title}</p>
      {description && (
        <p className="text-xs text-academia-500 mt-1">{description}</p>
      )}
    </div>
  );
}
