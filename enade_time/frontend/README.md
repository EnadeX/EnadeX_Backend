# ENADE-Time Distribuído — Frontend

Dashboard acadêmico React/Vite para o projeto **ENADE-Time Distribuído —
Sistema Paralelo de Análise Longitudinal dos Microdados do ENADE**.

Consome a API FastAPI read-only descrita em `../api/`.

## Pré-requisitos

- Node.js ≥ 20 LTS
- API rodando em `http://localhost:8000`
  (`python -m uvicorn api.main:app --port 8000 --reload`)

## Configuração

Copie o arquivo de exemplo de variáveis de ambiente:

```powershell
copy .env.example .env.development
```

Variáveis suportadas:
- `VITE_API_BASE_URL` (padrão: `http://localhost:8000`)

## Comandos

```powershell
npm install       # instala dependências
npm run dev       # sobe em http://localhost:5173
npm run build     # build de produção em dist/
npm run preview   # serve dist/ em http://localhost:4173
npm run typecheck # verifica tipos sem emitir
```

## Estrutura

```
src/
├── api/           # axios + funções de fetch
├── hooks/         # TanStack Query hooks
├── types/         # tipagens espelhando os Pydantic schemas
├── lib/           # utilitários (formatação, env, constantes)
├── components/
│   ├── layout/    # Header, Sidebar, Footer, PageContainer
│   ├── ui/        # primitivos (Card, Badge, Skeleton)
│   ├── feedback/  # Loading, Error, Empty, QueryBoundary
│   ├── filters/   # FiltrosAnalise (URL-synced)
│   ├── cards/     # MetricCard, KpiGrid
│   ├── charts/    # gráficos Recharts (9)
│   └── tables/    # tabelas (registros, execuções, etapas, ranking)
└── pages/
    ├── Home.tsx
    ├── enade/     # análises ENADE (5 sub-rotas)
    └── spd/       # benchmark SPD (4 sub-rotas)
```

## Rotas

| Rota | Conteúdo |
|---|---|
| `/` | Visão geral (KPIs ENADE + SPD) |
| `/enade/anual` | Média ENADE por ano |
| `/enade/regional` | Média por região |
| `/enade/uf` | Média por UF |
| `/enade/ies` | Ranking de IES |
| `/enade/registros` | Tabela paginada do fato_enade |
| `/spd/comparativo` | Tempo, speedup, eficiência, throughput |
| `/spd/execucoes` | Tabela de execuções de benchmark |
| `/spd/metricas` | View detalhada de métricas |
| `/spd/etapas/:id` | Drill-down de etapas por ano |
| `/sobre` | Metodologia e contexto |

Filtros de análise são sincronizados com a query string, permitindo
deep-link (ex.: `/enade/anual?nu_ano=2021&co_regiao=2`).

Veja também [`NOTAS_ORGANIZACAO.md`](./NOTAS_ORGANIZACAO.md) para
sugestões de arrumação do projeto após validação final.
