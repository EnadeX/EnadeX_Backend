import {
  BarChart3,
  Cpu,
  GraduationCap,
  Info,
  LayoutDashboard,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/cn";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const TOP_LEVEL: NavItem[] = [
  { to: "/", label: "Visão Geral", icon: LayoutDashboard },
  { to: "/sobre", label: "Sobre", icon: Info },
];

const ENADE_LINKS = [
  { to: "/enade/anual", label: "Por Ano" },
  { to: "/enade/regional", label: "Por Região" },
  { to: "/enade/uf", label: "Por UF" },
  { to: "/enade/ies", label: "Ranking IES" },
  { to: "/enade/comparar", label: "Comparar" },
  { to: "/enade/registros", label: "Registros" },
];

const SPD_LINKS = [
  { to: "/spd/comparativo", label: "Comparativo" },
  { to: "/spd/execucoes", label: "Execuções" },
  { to: "/spd/metricas", label: "Métricas" },
];

function topLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
    isActive
      ? "bg-academia-100 text-academia-900"
      : "text-academia-700 hover:bg-academia-100/60",
  );
}

function subLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "block px-3 py-1.5 rounded-md text-sm transition-colors",
    isActive
      ? "bg-academia-700 text-white"
      : "text-academia-700 hover:bg-academia-100",
  );
}

export function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-academia-100 bg-white">
      <nav className="p-4 space-y-6 sticky top-[73px]">
        <div className="space-y-1">
          {TOP_LEVEL.slice(0, 1).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} end className={topLinkClass}>
                <Icon className="h-4 w-4" aria-hidden />
                {item.label}
              </NavLink>
            );
          })}
        </div>

        <div>
          <div className="flex items-center gap-2 px-3 mb-1 text-xs uppercase tracking-wide text-academia-500 font-semibold">
            <GraduationCap className="h-3.5 w-3.5" aria-hidden />
            Análises ENADE
          </div>
          <div className="space-y-0.5">
            {ENADE_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} className={subLinkClass}>
                {l.label}
              </NavLink>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 px-3 mb-1 text-xs uppercase tracking-wide text-academia-500 font-semibold">
            <Cpu className="h-3.5 w-3.5" aria-hidden />
            Benchmark SPD
          </div>
          <div className="space-y-0.5">
            {SPD_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} className={subLinkClass}>
                {l.label}
              </NavLink>
            ))}
          </div>
        </div>

        <div className="space-y-1 pt-2 border-t border-academia-100">
          <NavLink to="/sobre" className={topLinkClass}>
            <Info className="h-4 w-4" aria-hidden />
            Sobre / Metodologia
          </NavLink>
        </div>

        <div className="text-xs text-academia-400 px-3 pt-4 border-t border-academia-100">
          <BarChart3 className="inline h-3 w-3 mr-1" aria-hidden />
          Versão dashboard 0.1.0
        </div>
      </nav>
    </aside>
  );
}
