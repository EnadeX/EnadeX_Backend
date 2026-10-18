import { formatDecimal, formatInt } from "@/lib/format";
import type { ResumoIES } from "@/types/api";

export function RankingIES({ items }: { items: ResumoIES[] }) {
  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm">
        <thead className="bg-academia-100 text-academia-700">
          <tr>
            <th className="px-3 py-2 text-left font-medium">#</th>
            <th className="px-3 py-2 text-right font-medium">Cód. IES</th>
            <th className="px-3 py-2 text-right font-medium">Cat. Adm.</th>
            <th className="px-3 py-2 text-right font-medium">Org. Acad.</th>
            <th className="px-3 py-2 text-right font-medium">UF (cód.)</th>
            <th className="px-3 py-2 text-right font-medium">Registros</th>
            <th className="px-3 py-2 text-right font-medium">Média FG</th>
            <th className="px-3 py-2 text-right font-medium">Média CE</th>
            <th className="px-3 py-2 text-right font-medium">Média GER</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r, i) => (
            <tr
              key={r.co_ies}
              className="odd:bg-white even:bg-academia-50/40 border-t border-academia-100"
            >
              <td className="px-3 py-2 font-medium">{i + 1}</td>
              <td className="px-3 py-2 text-right">{r.co_ies}</td>
              <td className="px-3 py-2 text-right">{r.co_categad}</td>
              <td className="px-3 py-2 text-right">{r.co_orgacad}</td>
              <td className="px-3 py-2 text-right">{r.co_uf_curso}</td>
              <td className="px-3 py-2 text-right">{formatInt(r.total_registros)}</td>
              <td className="px-3 py-2 text-right">
                {formatDecimal(r.media_geral, 2)}
              </td>
              <td className="px-3 py-2 text-right">
                {formatDecimal(r.media_geral_ce, 2)}
              </td>
              <td className="px-3 py-2 text-right font-semibold">
                {formatDecimal(r.media_geral_ger, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
