import { useEffect, useMemo, useRef, useState } from "react";
import { Download, FileText, ImageDown } from "lucide-react";

import { LineComparativoGrupos } from "@/components/charts/LineComparativoGrupos";
import { AlertaAmostra, type OcorrenciaAmostra } from "@/components/feedback/AlertaAmostra";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Card, CardHeader } from "@/components/ui/Card";
import { useResumoAnual } from "@/hooks/useAnalises";
import { useCategoriasAdm, useRegioes, useUFs } from "@/hooks/useDimensoes";
import { LIMIAR_AMOSTRA } from "@/lib/constants";
import {
  exportarGraficoSVG,
  exportarRelatorioMarkdown,
  exportarSerieCSV,
  type DadosComparacao,
} from "@/lib/export";
import { formatDecimal, formatInt } from "@/lib/format";
import type { FiltrosAnalise } from "@/types/api";

type DimKey = "co_regiao" | "co_uf" | "co_categad";

const DIMENSOES: { key: DimKey; label: string }[] = [
  { key: "co_regiao", label: "Região" },
  { key: "co_uf", label: "UF" },
  { key: "co_categad", label: "Categoria Administrativa" },
];

function construirFiltro(dim: DimKey, value: number | undefined): FiltrosAnalise {
  if (value === undefined) return {};
  if (dim === "co_regiao") return { co_regiao: value };
  if (dim === "co_uf") return { co_uf: value };
  return { co_categad: value };
}

export default function EnadeComparar() {
  const [dim, setDim] = useState<DimKey>("co_regiao");
  const [valueA, setValueA] = useState<number | undefined>(1); // Norte
  const [valueB, setValueB] = useState<number | undefined>(2); // Nordeste

  const chartRef = useRef<HTMLDivElement>(null);

  // dimensões (hooks sempre chamados — regras do React)
  const regioes = useRegioes();
  const ufs = useUFs();
  const categs = useCategoriasAdm();

  const opcoes = useMemo(() => {
    if (dim === "co_regiao")
      return (regioes.data ?? []).map((r) => ({ value: r.co_regiao, label: r.nome }));
    if (dim === "co_uf")
      return (ufs.data ?? []).map((u) => ({ value: u.co_uf, label: `${u.sigla} — ${u.nome}` }));
    return (categs.data ?? []).map((c) => ({ value: c.co_categad, label: c.nome }));
  }, [dim, regioes.data, ufs.data, categs.data]);

  // se os valores atuais não pertencem à dimensão, recai para os 2 primeiros
  useEffect(() => {
    if (opcoes.length < 2) return;
    const vals = opcoes.map((o) => o.value);
    const invalido =
      valueA === undefined ||
      valueB === undefined ||
      !vals.includes(valueA) ||
      !vals.includes(valueB) ||
      valueA === valueB;
    if (invalido) {
      setValueA(opcoes[0].value);
      setValueB(opcoes[1].value);
    }
  }, [opcoes, valueA, valueB]);

  const filtroA = useMemo(() => construirFiltro(dim, valueA), [dim, valueA]);
  const filtroB = useMemo(() => construirFiltro(dim, valueB), [dim, valueB]);

  const qA = useResumoAnual(filtroA);
  const qB = useResumoAnual(filtroB);

  const dimensaoLabel = DIMENSOES.find((d) => d.key === dim)?.label ?? "Grupo";
  const labelA = opcoes.find((o) => o.value === valueA)?.label ?? "Grupo A";
  const labelB = opcoes.find((o) => o.value === valueB)?.label ?? "Grupo B";

  // `?? []` cria um array novo a cada render enquanto a query não resolve;
  // memorizar mantém estáveis as dependências dos useMemo abaixo.
  const serieA = useMemo(() => qA.data ?? [], [qA.data]);
  const serieB = useMemo(() => qB.data ?? [], [qB.data]);

  const anos = useMemo(
    () =>
      Array.from(
        new Set([...serieA.map((p) => p.nu_ano), ...serieB.map((p) => p.nu_ano)]),
      ).sort((a, b) => a - b),
    [serieA, serieB],
  );

  const ocorrencias = useMemo<OcorrenciaAmostra[]>(() => {
    const out: OcorrenciaAmostra[] = [];
    for (const [serie, label] of [
      [serieA, labelA],
      [serieB, labelB],
    ] as const) {
      for (const p of serie) {
        if (p.total_registros < LIMIAR_AMOSTRA) {
          out.push({ grupo: label, nu_ano: p.nu_ano, n: p.total_registros });
        }
      }
    }
    return out;
  }, [serieA, serieB, labelA, labelB]);

  const dados: DadosComparacao = {
    dimensaoLabel,
    metricaLabel: "Média NT GER",
    filtrosResumo: `Dimensão: ${dimensaoLabel}; Grupo A: ${labelA}; Grupo B: ${labelB}`,
    limiarAmostra: LIMIAR_AMOSTRA,
    grupoA: { label: labelA, serie: serieA },
    grupoB: { label: labelB, serie: serieB },
  };

  const carregando = qA.isPending || qB.isPending;
  const erro = qA.isError || qB.isError;
  const semDados = serieA.length === 0 && serieB.length === 0;
  const podeExportar = !carregando && !erro && !semDados;

  const idxA = new Map(serieA.map((p) => [p.nu_ano, p]));
  const idxB = new Map(serieB.map((p) => [p.nu_ano, p]));

  return (
    <div className="space-y-4">
      {/* seletores */}
      <Card>
        <CardHeader
          title="Comparação longitudinal entre dois grupos"
          description="Compara a evolução da Média NT GER (Nota Geral) ao longo das edições do ENADE entre dois grupos. Padrão: Região — Norte × Nordeste."
        />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="text-xs text-academia-700">
            Dimensão
            <select
              className="select mt-1"
              value={dim}
              onChange={(e) => setDim(e.target.value as DimKey)}
            >
              {DIMENSOES.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-academia-700">
            Grupo A
            <select
              className="select mt-1"
              value={valueA ?? ""}
              onChange={(e) => setValueA(Number(e.target.value))}
            >
              {opcoes.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-academia-700">
            Grupo B
            <select
              className="select mt-1"
              value={valueB ?? ""}
              onChange={(e) => setValueB(Number(e.target.value))}
            >
              {opcoes.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {valueA === valueB && (
          <p className="text-xs text-amber-700 mt-2">
            Os dois grupos são iguais — escolha valores diferentes para comparar.
          </p>
        )}

        <div className="flex flex-wrap gap-2 mt-4">
          <button
            type="button"
            className="btn-secondary"
            disabled={!podeExportar}
            onClick={() => exportarSerieCSV(dados)}
          >
            <Download className="h-4 w-4 mr-1.5" aria-hidden />
            Exportar CSV
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!podeExportar}
            onClick={() => {
              const ok = exportarGraficoSVG(chartRef.current);
              if (!ok) alert("Gráfico ainda não disponível para exportação.");
            }}
          >
            <ImageDown className="h-4 w-4 mr-1.5" aria-hidden />
            Exportar SVG
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={!podeExportar}
            onClick={() => exportarRelatorioMarkdown(dados)}
          >
            <FileText className="h-4 w-4 mr-1.5" aria-hidden />
            Exportar relatório (.md)
          </button>
        </div>
      </Card>

      {/* alerta de amostra reduzida */}
      <AlertaAmostra ocorrencias={ocorrencias} />

      {/* gráfico */}
      <Card>
        <CardHeader
          title={`${dimensaoLabel}: ${labelA} × ${labelB}`}
          description="Métrica: Média NT GER (Nota Geral) por ano."
        />
        {erro ? (
          <ErrorState
            message="Falha ao carregar os dados da comparação."
            onRetry={() => {
              qA.refetch();
              qB.refetch();
            }}
          />
        ) : carregando ? (
          <LoadingSpinner label="Carregando comparação…" />
        ) : semDados ? (
          <p className="text-sm text-academia-600 py-6 text-center">
            Sem dados para os grupos selecionados.
          </p>
        ) : (
          <div ref={chartRef}>
            <LineComparativoGrupos
              serieA={serieA}
              serieB={serieB}
              labelA={labelA}
              labelB={labelB}
            />
          </div>
        )}
      </Card>

      {/* tabela ano × grupo */}
      {podeExportar && (
        <Card>
          <CardHeader title="Série por ano e grupo" />
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="text-academia-700">
                <tr className="text-left">
                  <th className="px-2 py-2">Ano</th>
                  <th className="px-2 py-2 text-right">{labelA} — GER</th>
                  <th className="px-2 py-2 text-right">n ({labelA})</th>
                  <th className="px-2 py-2 text-right">{labelB} — GER</th>
                  <th className="px-2 py-2 text-right">n ({labelB})</th>
                  <th className="px-2 py-2 text-right">Δ (A − B)</th>
                </tr>
              </thead>
              <tbody>
                {anos.map((ano) => {
                  const a = idxA.get(ano);
                  const b = idxB.get(ano);
                  const delta =
                    a?.media_geral_ger != null && b?.media_geral_ger != null
                      ? a.media_geral_ger - b.media_geral_ger
                      : null;
                  return (
                    <tr key={ano} className="border-t border-academia-100">
                      <td className="px-2 py-2 font-medium">{ano}</td>
                      <td className="px-2 py-2 text-right">{formatDecimal(a?.media_geral_ger ?? null, 2)}</td>
                      <td className="px-2 py-2 text-right">{a ? formatInt(a.total_registros) : "—"}</td>
                      <td className="px-2 py-2 text-right">{formatDecimal(b?.media_geral_ger ?? null, 2)}</td>
                      <td className="px-2 py-2 text-right">{b ? formatInt(b.total_registros) : "—"}</td>
                      <td className="px-2 py-2 text-right font-medium">{formatDecimal(delta, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
