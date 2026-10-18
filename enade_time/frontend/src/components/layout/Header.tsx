import { Activity } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { APP_SUBTITLE, APP_TITLE } from "@/lib/constants";
import { useHealth } from "@/hooks/useHealth";

export function Header() {
  const health = useHealth();

  let tone: "success" | "warning" | "danger" = "warning";
  let label = "verificando…";
  if (health.isSuccess && health.data?.status === "ok") {
    tone = "success";
    label = "API online";
  } else if (health.isError) {
    tone = "danger";
    label = "API offline";
  }

  return (
    <header className="bg-white border-b border-academia-100 sticky top-0 z-30">
      <div className="max-w-screen-2xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-academia-900">{APP_TITLE}</h1>
          <p className="text-xs text-academia-600 mt-0.5">{APP_SUBTITLE}</p>
        </div>
        <Badge tone={tone}>
          <Activity className="h-3 w-3" aria-hidden />
          {label}
          {health.data?.version && (
            <span className="text-academia-500 font-normal ml-1">
              · v{health.data.version}
            </span>
          )}
        </Badge>
      </div>
    </header>
  );
}
