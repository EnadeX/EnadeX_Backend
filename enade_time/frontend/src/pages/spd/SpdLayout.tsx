import { NavLink, Outlet, useLocation } from "react-router-dom";

import { PageContainer } from "@/components/layout/PageContainer";
import { cn } from "@/lib/cn";

const TABS = [
  { to: "/spd/comparativo", label: "Comparativo" },
  { to: "/spd/execucoes", label: "Execuções" },
  { to: "/spd/metricas", label: "Métricas" },
];

function tabClass({ isActive }: { isActive: boolean }) {
  return cn(
    "px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
    isActive
      ? "border-academia-700 text-academia-900"
      : "border-transparent text-academia-600 hover:text-academia-900",
  );
}

export default function SpdLayout() {
  const { pathname } = useLocation();
  const dentroEtapas = pathname.startsWith("/spd/etapas/");

  return (
    <PageContainer
      title="Benchmark SPD"
      description="Resultados do experimento de processamento paralelo dos microdados ENADE. Comparação entre execução sequencial e paralela (2 e 4 workers)."
    >
      {!dentroEtapas && (
        <nav className="flex gap-1 border-b border-academia-200">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} className={tabClass}>
              {t.label}
            </NavLink>
          ))}
        </nav>
      )}
      <Outlet />
    </PageContainer>
  );
}
