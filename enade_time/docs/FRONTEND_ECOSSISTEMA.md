# Dashboard do ENADE-Time no frontend do ecossistema

O dashboard do ENADE-Time agora vive no repositório de frontend do grupo
(`Cintriano/EnadeX_Frontend`), como o módulo **`/enade-time`**. A SPA original
(React + Vite) continua em `enade_time/frontend/` como artefato do TCC; a fonte
da verdade do dashboard é a do `EnadeX_Frontend`.

## Onde está

| O quê | Onde |
|---|---|
| Rotas e componentes | `EnadeX_Frontend/app/enade-time/` |
| Cliente HTTP, tipos, hooks, utilitários | `EnadeX_Frontend/lib/enade-time/` |
| Código compartilhado alterado | `app/page.tsx` (`href` e período `2005–2021` do card), `package.json` e `pnpm-lock.yaml` (+ `@tanstack/react-query`) |
| Publicação | `master`, commits `b04118e` … `3ebeff7` (12/10/2026), todos com prefixo `enade-time:` |

Nada fora dessas pastas foi tocado: nem `app/layout.tsx`, nem `globals.css`, nem
`components/`, nem os módulos dos colegas.

## Como rodar

```powershell
# 1) API do ENADE-Time (da raiz do EnadeX, porta 8002)
$env:PYTHONPATH='.'
python enade_time\enade_time_rotas.py

# 2) Frontend do grupo (outro terminal)
cd C:\Projetos\EnadeX_Frontend
pnpm install --frozen-lockfile        # pnpm 12.3.4, a versão do packageManager
pnpm dev -p 3000                      # http://localhost:3000/enade-time
```

- **Use sempre a porta 3000 e `localhost`** (não `127.0.0.1`): é a única origem
  liberada no CORS da API.
- **Variável:** `NEXT_PUBLIC_ENADE_TIME_API_URL` (padrão `http://localhost:8002`).
  Com o router no `api_main.py` central, use `http://localhost:8000`. A variável é
  embutida no build: mudar o valor exige novo build.
- **Dados:** a API lê do Postgres local (`scripts/05` e `06`, mais o experimento) ou,
  com `--fonte supabase`, do Supabase do grupo, onde a base e o benchmark estão
  publicados (`scripts/12`). O pill do módulo mostra qual fonte está em uso. Sem banco
  acessível, o módulo mostra "Banco indisponível", sem derrubar nada.
- `next dev` gera `AGENTS.md` e `CLAUDE.md` na raiz do frontend: são artefatos da
  ferramenta, não devem ser commitados.

## Contrato com a API

O módulo consome 19 das 20 rotas GET de `/api/enade-time` (`/benchmark/campanhas`
existe e não é usada). Só o prefixo e a URL base mudaram em relação à SPA original;
tipos e parâmetros são os mesmos de `api/schemas/`.

| Situação | O que a API devolve | O que o dashboard mostra |
|---|---|---|
| Normal | 200 | dados |
| Banco fora | 503 (`Banco do ENADE-Time indisponível`, com CORS) | pill "Banco indisponível" |
| API fora | sem resposta | pill "API offline" e como subir |
| Outro erro | 4xx/5xx | pill "Erro na API" e a mensagem |

Para o router poder entrar no `api_main.py` sem lifespan, o pool de conexões é
preguiçoso (`api/database.py`). Depois de uma falha, as requisições seguintes
recebem 503 imediato por 5 s (cooldown) em vez de esperar o timeout de conexão, e
o pool é descartado e recriado quando o banco volta.

## Como o módulo se adapta ao projeto em grupo

- **Casca visual** copiada dos demais subprojetos (header de 70 px, cards
  `rounded-2xl`, hex do grupo), com **acento âmbar**, a cor do card na home.
- **Camada de dados:** TanStack Query (cache de 24 h para dimensões, 5 min para
  análises), a única dependência nova. Os demais subprojetos usam `fetch` direto.
- **Filtros na URL** (`nu_ano`, `co_regiao`, `co_uf`, `co_ies`, `co_grupo`,
  `co_modalidade`, `co_categad`, `co_orgacad`): deep link, sem rolar a página, e
  preservados ao trocar de aba. O `<Suspense>` que o `useSearchParams` exige fica
  no grupo de rotas `enade/(analises)`, sem alterar as URLs, para os redirects
  de `/enade-time/enade` e `/enade-time/spd` responderem 307.
- **Recharts 3 e Tailwind 4:** formatters de tooltip tipados, grade de gráfico com
  dois eixos corrigida, classes do módulo em `lib/enade-time/ui.ts` (o `index.css`
  da SPA não foi portado, para não criar CSS global).

## Contraste (acessibilidade)

Três cores do projeto em grupo reprovam o WCAG AA sobre fundo claro:
`#8aa0c1` e `#91a4c3` (texto "fraco", 2,5:1) e `#009b67` (verde de "Conectado",
3,4:1). No módulo foram trocadas por `#5f7393` (4,5:1 ou mais em todos os fundos
usados) e `#047857`. Fica a sugestão ao líder de adotar o mesmo ajuste nos demais
subprojetos.

## Verificação (12/10/2026)

Rodada sobre o build de produção, com a campanha oficial `899faa82` no banco.

| Verificação | Resultado |
|---|---|
| `tsc --noEmit` no projeto inteiro | 0 erros (o `next build` do grupo não checa tipos) |
| `next build` | passa, com todas as rotas `/enade-time/*` e sem erro de Suspense |
| Códigos HTTP | 200 nas 13 páginas; 307 em `/enade-time/enade` e `/spd`; 404 do módulo em URL desconhecida e em id inválido |
| Funcional no Chrome (`funcional.mjs`) | 59/59: dados, deep link, filtros sem rolar, abas, exportações CSV/SVG/Markdown, alerta de amostra, paginação, benchmark, 404, responsivo em 375/768/1280/1920 px sem rolagem horizontal, console sem erros |
| Degradação (`degradacao.mjs`) | 10/10: API parada, banco parado (503) e recuperação sem reiniciar, benchmark vazio |
| Acessibilidade (`acessibilidade.mjs`) | axe-core (WCAG 2.0/2.1 A e AA e boas práticas): 0 violações em 13 páginas; 24 paradas de foco por teclado, todas com indicador visível |
| Modo central simulado | mesma bateria (então com 55 verificações, antes da página de custo de publicação) com o router incluído num `FastAPI()` sem lifespan, CORS idêntico ao do `api_main.py`, na porta 8000 |
| Clone limpo | `pnpm install --frozen-lockfile` e `pnpm build` a partir dos commits |
| Backend | 120 testes, 1 pulado sem a chave pública do Supabase (`tests/test_router_ecossistema.py` cobre as 20 rotas, o 503 com CORS, a conexão morta e a recuperação) |

Ruído esperado no console, vindo do layout raiz do grupo e não do módulo: os
ícones `/icon*.png` e `/icon.svg` (a pasta `public/` não existe) e o script
`/_vercel/insights` fora da Vercel.

Para reproduzir (com a API e o `pnpm start -p 3000` no ar):

```powershell
cd enade_time\tools\e2e_frontend
npm install
npm run funcional
npm run acessibilidade
npm run degradacao      # derruba e religa a API e o container do Postgres
```

Os valores esperados do `funcional.mjs` (24.967 inscrições; melhor configuração
`6 workers · crescente`, 2,70×) são os da campanha oficial `899faa82`.

## Limitações conhecidas

- O `AlertaAmostra` ainda conta inscrições (`total_registros`) e não cursos-ano; a
  correção depende do campo `total_cursos` nos endpoints `resumo-*` (DESIGN_LOG D16).
- Os dados de SPD só existem no Postgres local; para outras máquinas dependem da
  publicação no Supabase (fase 4 do plano de migração).
- O KPI "05 · 2017 até 2021" da home do grupo não foi alterado: é decisão do líder.
