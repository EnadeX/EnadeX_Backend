import { AlertTriangle } from "lucide-react";

import { LIMIAR_AMOSTRA } from "@/lib/constants";

export interface OcorrenciaAmostra {
  grupo: string;
  nu_ano: number;
  n: number;
}

export function AlertaAmostra({
  ocorrencias,
  limiar = LIMIAR_AMOSTRA,
}: {
  ocorrencias: OcorrenciaAmostra[];
  limiar?: number;
}) {
  if (ocorrencias.length === 0) return null;

  return (
    <div className="card border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" aria-hidden />
        <div>
          <h4 className="text-sm font-semibold text-amber-900">
            Amostra reduzida (n &lt; {limiar})
          </h4>
          <p className="text-xs text-amber-800 mt-1">
            As combinações abaixo têm poucos registros — a média pode ser
            estatisticamente instável e deve ser interpretada com cautela:
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {ocorrencias.map((o) => (
              <li
                key={`${o.grupo}-${o.nu_ano}`}
                className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
              >
                {o.grupo} · {o.nu_ano}: n={o.n}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
