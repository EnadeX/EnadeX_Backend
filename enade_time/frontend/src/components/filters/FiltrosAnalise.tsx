import { useEffect, useState } from "react";
import { Filter, X } from "lucide-react";

import {
  useAnos,
  useCategoriasAdm,
  useGrupos,
  useModalidades,
  useOrganizacoesAcademicas,
  useRegioes,
  useUFs,
} from "@/hooks/useDimensoes";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import type { FiltrosAnalise } from "@/types/api";

function toNumOrUndef(v: string): number | undefined {
  if (v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export function FiltrosAnaliseBar() {
  const { filtros, setFiltros, limpar } = useFiltrosUrl();
  const [local, setLocal] = useState<FiltrosAnalise>(filtros);

  useEffect(() => {
    setLocal(filtros);
  }, [filtros]);

  const regioes = useRegioes();
  const ufs = useUFs(local.co_regiao);
  const anos = useAnos();
  const grupos = useGrupos();
  const modalidades = useModalidades();
  const categorias = useCategoriasAdm();
  const orgacads = useOrganizacoesAcademicas();

  const update = <K extends keyof FiltrosAnalise>(k: K, v: FiltrosAnalise[K]) => {
    setLocal((p) => ({ ...p, [k]: v }));
  };

  const aplicar = () => {
    setFiltros(local);
  };

  const algumFiltro = Object.values(local).some((v) => v !== undefined);

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-academia-800">
        <Filter className="h-4 w-4" aria-hidden />
        Filtros
        {algumFiltro && (
          <button
            type="button"
            onClick={() => {
              setLocal({});
              limpar();
            }}
            className="ml-auto inline-flex items-center gap-1 text-xs text-academia-600 hover:text-academia-900"
          >
            <X className="h-3 w-3" aria-hidden />
            Limpar
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <label className="text-xs text-academia-700">
          Ano
          <select
            className="select mt-1"
            value={local.nu_ano ?? ""}
            onChange={(e) => update("nu_ano", toNumOrUndef(e.target.value))}
          >
            <option value="">Todos</option>
            {anos.data?.map((a) => (
              <option key={a.co_ano} value={a.co_ano}>
                {a.co_ano}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Região
          <select
            className="select mt-1"
            value={local.co_regiao ?? ""}
            onChange={(e) => {
              const v = toNumOrUndef(e.target.value);
              setLocal((p) => ({ ...p, co_regiao: v, co_uf: undefined }));
            }}
          >
            <option value="">Todas</option>
            {regioes.data?.map((r) => (
              <option key={r.co_regiao} value={r.co_regiao}>
                {r.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          UF
          <select
            className="select mt-1"
            value={local.co_uf ?? ""}
            onChange={(e) => update("co_uf", toNumOrUndef(e.target.value))}
          >
            <option value="">Todas</option>
            {ufs.data?.map((u) => (
              <option key={u.co_uf} value={u.co_uf}>
                {u.sigla} — {u.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Grupo (curso)
          <select
            className="select mt-1"
            value={local.co_grupo ?? ""}
            onChange={(e) => update("co_grupo", toNumOrUndef(e.target.value))}
          >
            <option value="">Todos</option>
            {grupos.data?.map((g) => (
              <option key={g.co_grupo} value={g.co_grupo}>
                {g.co_grupo} — {g.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Modalidade
          <select
            className="select mt-1"
            value={local.co_modalidade ?? ""}
            onChange={(e) =>
              update("co_modalidade", toNumOrUndef(e.target.value))
            }
          >
            <option value="">Todas</option>
            {modalidades.data?.map((m) => (
              <option key={m.co_modalidade} value={m.co_modalidade}>
                {m.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Categoria Adm.
          <select
            className="select mt-1"
            value={local.co_categad ?? ""}
            onChange={(e) => update("co_categad", toNumOrUndef(e.target.value))}
          >
            <option value="">Todas</option>
            {categorias.data?.map((c) => (
              <option key={c.co_categad} value={c.co_categad}>
                {c.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Org. Acadêmica
          <select
            className="select mt-1"
            value={local.co_orgacad ?? ""}
            onChange={(e) => update("co_orgacad", toNumOrUndef(e.target.value))}
          >
            <option value="">Todas</option>
            {orgacads.data?.map((o) => (
              <option key={o.co_orgacad} value={o.co_orgacad}>
                {o.nome}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-academia-700">
          Cód. IES
          <input
            type="number"
            inputMode="numeric"
            placeholder="ex.: 1234"
            className="input mt-1"
            value={local.co_ies ?? ""}
            onChange={(e) => update("co_ies", toNumOrUndef(e.target.value))}
          />
        </label>
      </div>

      <div className="flex justify-end gap-2 mt-4">
        <button type="button" className="btn-secondary" onClick={() => setLocal(filtros)}>
          Cancelar
        </button>
        <button type="button" className="btn-primary" onClick={aplicar}>
          Aplicar
        </button>
      </div>
    </div>
  );
}
