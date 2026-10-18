import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import type { FiltrosAnalise } from "@/types/api";

const KEYS: (keyof FiltrosAnalise)[] = [
  "nu_ano",
  "co_regiao",
  "co_uf",
  "co_ies",
  "co_grupo",
  "co_modalidade",
  "co_categad",
  "co_orgacad",
];

function parseInt0(v: string | null): number | undefined {
  if (v === null || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export function useFiltrosUrl() {
  const [params, setParams] = useSearchParams();

  const filtros = useMemo<FiltrosAnalise>(() => {
    const f: FiltrosAnalise = {};
    for (const k of KEYS) {
      const v = parseInt0(params.get(k));
      if (v !== undefined) f[k] = v;
    }
    return f;
  }, [params]);

  const setFiltros = useCallback(
    (next: FiltrosAnalise) => {
      const sp = new URLSearchParams(params);
      for (const k of KEYS) {
        const v = next[k];
        if (v === undefined || v === null) sp.delete(k);
        else sp.set(k, String(v));
      }
      setParams(sp, { replace: true });
    },
    [params, setParams],
  );

  const limpar = useCallback(() => {
    const sp = new URLSearchParams(params);
    for (const k of KEYS) sp.delete(k);
    setParams(sp, { replace: true });
  }, [params, setParams]);

  return { filtros, setFiltros, limpar };
}
