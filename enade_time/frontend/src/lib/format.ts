const numberFmt = new Intl.NumberFormat("pt-BR");
const decimal2Fmt = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const decimal4Fmt = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});
const percentFmt = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return numberFmt.format(value);
}

export function formatDecimal(
  value: number | null | undefined,
  digits: 2 | 4 = 2,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return digits === 4 ? decimal4Fmt.format(value) : decimal2Fmt.format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return percentFmt.format(value);
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${decimal2Fmt.format(value)} s`;
}

export function formatThroughput(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${decimal2Fmt.format(value)} linhas/s`;
}

export function formatSpeedup(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${decimal4Fmt.format(value)}×`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR");
}
