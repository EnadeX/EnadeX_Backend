export const APP_TITLE = "ENADE-Time Distribuído";
export const APP_SUBTITLE =
  "Sistema Paralelo de Análise Longitudinal dos Microdados do ENADE";

export const CHART_COLORS = {
  seq: "#94a3b8",
  paralelo: "#2563eb",
  paralelo2: "#7c3aed",
  ideal: "#10b981",
  alert: "#ef4444",
  warn: "#f59e0b",
  neutral: "#64748b",
} as const;

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250] as const;

// Limiar de amostra: abaixo deste n por ano/grupo, a estimativa é considerada
// estatisticamente frágil e um alerta é exibido (Módulo 3 — Critério B).
export const LIMIAR_AMOSTRA = 30;
