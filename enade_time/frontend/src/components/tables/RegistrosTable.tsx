import { formatDecimal } from "@/lib/format";
import type { Registro } from "@/types/api";

export function RegistrosTable({ items }: { items: Registro[] }) {
  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm">
        <thead className="bg-academia-100 text-academia-700">
          <tr>
            <th className="px-3 py-2 text-left font-medium">ID</th>
            <th className="px-3 py-2 text-left font-medium">Ano</th>
            <th className="px-3 py-2 text-right font-medium">IES</th>
            <th className="px-3 py-2 text-right font-medium">Curso</th>
            <th className="px-3 py-2 text-right font-medium">Categ.</th>
            <th className="px-3 py-2 text-right font-medium">Org.</th>
            <th className="px-3 py-2 text-right font-medium">Grupo</th>
            <th className="px-3 py-2 text-right font-medium">Modal.</th>
            <th className="px-3 py-2 text-right font-medium">UF</th>
            <th className="px-3 py-2 text-right font-medium">Região</th>
            <th className="px-3 py-2 text-right font-medium">Média NT FG</th>
            <th className="px-3 py-2 text-right font-medium">Média NT CE</th>
            <th className="px-3 py-2 text-right font-medium">Média NT GER</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id} className="odd:bg-white even:bg-academia-50/40 border-t border-academia-100">
              <td className="px-3 py-1.5 text-left">{r.id}</td>
              <td className="px-3 py-1.5">{r.nu_ano}</td>
              <td className="px-3 py-1.5 text-right">{r.co_ies}</td>
              <td className="px-3 py-1.5 text-right">{r.co_curso}</td>
              <td className="px-3 py-1.5 text-right">{r.co_categad}</td>
              <td className="px-3 py-1.5 text-right">{r.co_orgacad}</td>
              <td className="px-3 py-1.5 text-right">{r.co_grupo}</td>
              <td className="px-3 py-1.5 text-right">{r.co_modalidade ?? "—"}</td>
              <td className="px-3 py-1.5 text-right">{r.co_uf_curso}</td>
              <td className="px-3 py-1.5 text-right">{r.co_regiao_curso}</td>
              <td className="px-3 py-1.5 text-right font-medium">
                {formatDecimal(r.media_nt_fg, 2)}
              </td>
              <td className="px-3 py-1.5 text-right">
                {formatDecimal(r.media_nt_ce, 2)}
              </td>
              <td className="px-3 py-1.5 text-right">
                {formatDecimal(r.media_nt_ger, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
