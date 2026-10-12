# Próximos passos (roadmap pós-entrega)

Lista de melhorias planejadas, **fora do escopo das Fases 1–5**. Cada
item está classificado por esforço (pequeno/médio/grande) e benefício
(operacional, acadêmico ou ambos). Use como base para um próximo
trabalho ou para extensões da pesquisa.

---

## Empacotamento e deploy

### Dockerfile da API
- **Esforço:** pequeno · **Benefício:** operacional.
- Imagem Python slim com `uvicorn` rodando `api.main:app`.
- `EXPOSE 8000`, `HEALTHCHECK` no endpoint `/api/health`.
- Multi-stage build se quiser pré-compilar `psycopg2-binary`.

### Dockerfile do frontend
- **Esforço:** pequeno · **Benefício:** operacional.
- Build com Node 20 → estágio final servindo o `dist/` com Nginx
  alpine.
- Variável de ambiente `VITE_API_BASE_URL` substituída no momento do
  build (não em runtime — limitação de SPA estática).

### docker-compose completo (postgres + api + frontend)
- **Esforço:** médio · **Benefício:** operacional.
- Adicionar serviços `api` e `frontend` ao `docker-compose.yml`.
- Rede interna para isolar Postgres; expor apenas portas 8000 e 3000.
- `depends_on` com `condition: service_healthy` para a API só subir
  após o Postgres estar pronto.

### Deploy online
- **Esforço:** médio · **Benefício:** operacional.
- API + Postgres em um VPS (Hetzner, DigitalOcean) ou em um PaaS
  (Fly.io, Railway).
- Frontend estático em Cloudflare Pages, Vercel ou Netlify.
- Domínio próprio + HTTPS via Let's Encrypt.
- **Atenção:** revisar CORS e ajustar `BENCHMARK_IDS_EXCLUIR` para
  ambiente de produção.

---

## Engenharia de software

### Testes automatizados
- **Esforço:** médio · **Benefício:** operacional.
- Backend: `pytest` cobrindo os routers principais (health, ao menos um
  endpoint de dimensão, um de análise, um de benchmark). Banco de
  teste em container efêmero (`testcontainers-python` ou
  `pytest-postgresql`).
- Frontend: `vitest` + `@testing-library/react` para componentes de
  formatação e para o `QueryBoundary`.
- CI: GitHub Actions ou GitLab CI rodando lint + typecheck + testes
  em todo push.

### Otimização de chunks do frontend
- **Esforço:** pequeno · **Benefício:** operacional.
- Code-splitting por rota via `React.lazy` + `Suspense`.
- Configurar `manualChunks` em `vite.config.ts` para separar
  `recharts` em um chunk dedicado.
- Atualmente o build emite aviso de chunk > 500 kB — informativo,
  não é erro.

### Atualização do Recharts para a v3
- **Esforço:** médio · **Benefício:** operacional + acadêmico.
- A v3 traz API revisada (alguns componentes mudam de assinatura).
- Não fazer durante a janela de entrega — alto risco de regressão
  visual nos 8 gráficos.
- Plano: criar uma branch dedicada, migrar gráfico por gráfico
  validando contra `npm run preview`.

### CI/CD
- **Esforço:** médio · **Benefício:** operacional.
- Pipeline com 3 estágios: lint/typecheck → build (api e frontend) →
  deploy (se branch = main).
- Cache de `node_modules` e `pip` entre runs.
- Publicar imagens Docker no GHCR/GitLab Registry.

---

## Funcionalidades

### Autenticação
- **Esforço:** médio · **Benefício:** operacional.
- API com JWT (FastAPI + `python-jose`). Login simples para a
  apresentação online.
- Frontend com tela de login e armazenamento do token em `httpOnly`
  cookie.
- **Reflexão:** só faz sentido se a API for exposta na internet. No
  ambiente acadêmico local, é overhead.

### Exportação de gráficos
- **Esforço:** pequeno · **Benefício:** acadêmico.
- Botão "Exportar PNG" em cada gráfico, usando
  `recharts` + `dom-to-image-more` ou `html2canvas`.
- Botão "Exportar CSV" usando o próprio endpoint da API + `Blob`.
- Útil para alunos que quiserem inserir os gráficos em artigos.

### Tema escuro
- **Esforço:** pequeno · **Benefício:** estético.
- Tailwind já suporta `dark:` modificador.
- Adicionar `<button>` no header com `useTheme()` armazenado em
  `localStorage`.

### i18n
- **Esforço:** médio · **Benefício:** acadêmico.
- Adicionar `react-i18next` para suportar inglês — útil em
  publicações internacionais.

---

## Pesquisa / experimentos adicionais

### ~~Mais pontos na curva de speedup~~ — feito na campanha oficial (v2)
- Campanha com {2, 3, 4, 6} workers × {crescente, LPT} × 5 suítes,
  aquecimento descartado e instrumentação de CPU/disco
  (`RESULTADOS_BENCHMARK.md`). p = 8 ficou de fora por construção
  (6 unidades de trabalho → dois workers ociosos).

### Granularidade menor que o ano
- **Esforço:** médio · **Benefício:** acadêmico (é o que sobe o teto).
- O teto de speedup atual é de **escalonamento/granularidade** (6 unidades
  de tamanhos diferentes), não de Amdahl. Particionar cada ano em blocos
  (por UF ou por faixas de linhas) eleva o teto e permite testar p > 6 de
  verdade. Exige manter `processar_ano` puro (blocos como novas unidades).

### Repetir a campanha em outra máquina / SO
- **Esforço:** pequeno · **Benefício:** acadêmico.
- Máquina com mais núcleos físicos e Linux (`fork` em vez de `spawn`):
  separa o custo do spawn do Windows do resto do overhead e testa se o
  ponto ótimo desloca como previsto. O script 10 já grava máquina e
  condições; basta rodar e comparar campanhas pelo `campanha_id`.

### Intervalo de confiança formal
- **Esforço:** pequeno · **Benefício:** acadêmico.
- Com 5 suítes reportamos mediana, mín–máx e IQR. Com ~15–20 suítes cabe um
  IC por bootstrap do speedup mediano — `v_enade_time_benchmark_resumo` já agrega por
  campanha; só o `--reps` muda.

### Profiling por etapa
- **Esforço:** médio · **Benefício:** acadêmico.
- Usar `py-spy` no worker para separar, dentro de cada ano, leitura/decodificação
  de parsing pandas. A campanha já mostrou que o disco quase não é lido em
  regime quente; o profiling diria onde a CPU vai.

### Eixo de carga local × nuvem (Fase 7 do plano de migração)
- **Esforço:** médio · **Benefício:** acadêmico + ecossistema.
- `COPY` local × `COPY` via Session Pooler × `upsert` PostgREST em lotes,
  n = 10, sempre em tabela vazia, RTT medido no canal testado — custo de
  publicar no Supabase, nunca "speedup".

### Comparar com Dask/Spark
- **Esforço:** grande · **Benefício:** acadêmico.
- Reescrever o ETL em Dask (ou PySpark local) e medir overhead vs.
  ganho.
- Hipótese: para 24k linhas, o overhead supera o ganho. Vale o
  experimento.

### Particionar o banco
- **Esforço:** médio · **Benefício:** acadêmico.
- Particionar `tbl_enade_time_fato` por `nu_ano` no Postgres e medir impacto
  no `COPY` paralelo.

---

## Documentação

### Vídeo de demo
- **Esforço:** pequeno · **Benefício:** divulgação.
- Gravar 3–5 minutos navegando pelo dashboard e mostrando o
  comparativo. Útil para portfolio.

### Artigo técnico
- **Esforço:** grande · **Benefício:** acadêmico.
- Estruturar como paper curto (4–6 páginas) descrevendo o
  experimento, a metodologia e os resultados — bom material para
  iniciar uma publicação em workshop de SPD.

---

## O que **não** virá agora (intencionalmente)

- Reescrever a API em async puro (sem ganho real com Postgres
  síncrono).
- Trocar Recharts por D3 puro (mais flexível, mas custo de
  desenvolvimento maior que o ganho).
- Mover para microsserviços (escopo errado para o tamanho do
  projeto).
- Adicionar Redis ou cache externo (a API já está rápida o suficiente
  com o pool de conexões).
