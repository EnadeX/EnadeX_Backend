# Propostas para os arquivos compartilhados do EnadeX

**De:** Lucas (ENADE-Time) · **Para:** líder do ecossistema · **Data:** 12/10/2026

O ENADE-Time só alterou arquivos dentro de `enade_time/` (e, no frontend, `app/enade-time`,
`lib/enade-time`, uma linha de `href` no card da home, o período do card e a dependência
`@tanstack/react-query`). Tudo abaixo está **fora** do que alterei: são observações feitas
ao integrar, com o fato verificado no `main` de 12/10/2026 e uma sugestão. Nenhuma foi
aplicada; a decisão é do líder.

| # | Fato verificado no `main` | Sugestão | Custo |
|---|---|---|---|
| 1 | `.gitignore` não ignora `__pycache__`; há 25 `.pyc` versionados (inclusive `util/__pycache__/util_db.cpython-314.pyc`, que entrou no último merge) | Acrescentar `__pycache__/` e `*.pyc` e rodar `git rm -r --cached` neles; evita conflito de merge a cada `import` | 5 min |
| 2 | `requirements.txt` está em **UTF-16** e faltam `uvicorn` (usado pelo `api_main.py`), `psycopg2-binary` e `pydantic-settings` (necessários para importar o `enade_time`) | Regravar em UTF-8 e acrescentar os pacotes; `pip` em alguns ambientes não lê UTF-16 | 10 min |
| 3 | `api_main.py` inclui só o `multi_enade`; as linhas dos demais estão comentadas **sem o import**, então descomentar uma sozinha dá `NameError` e derruba a API central | Ver [`propostas/api_main_referencia.py`](propostas/api_main_referencia.py): 2 linhas para o ENADE-Time, sem lifespan. O router devolve 503 com CORS se o banco dele estiver fora | 5 min |
| 4 | CORS central com `allow_methods=["GET","POST"]` e só `localhost:3000`; o frontend e o ENADE-Time usam exatamente essa origem | Nada a mudar; só registrar que `localhost:3000` (não `127.0.0.1`, não 3001) é a única origem liberada | — |
| 5 | `educluster_endpoints.py` cria o próprio `FastAPI()` (porta 8001) em vez de um `APIRouter`; por isso não dá para incluí-lo no `api_main` | Converter em `APIRouter(prefix="/api/educluster")`, como os outros | 30 min |
| 6 | `multi_enade_endpoints.py` devolve HTTP 200 com `{"erro": ...}` quando falha; o documento do líder chama o arquivo de `multi_enade_rotas.py` | Responder 4xx/5xx de verdade (o frontend já trata erro HTTP) e, se quiser, renomear para `multi_enade_rotas.py` | 20 min |
| 7 | `util/` não tem `__init__.py` (funciona como pacote de namespace) e o `.env_example` está em `util/`, não na raiz como pede o documento | Criar `util/__init__.py` vazio e mover o `.env_example` para a raiz | 5 min |
| 8 | Cada subprojeto tem porta e variável de ambiente próprias no frontend (`NEXT_PUBLIC_API_URL` :8000, `NEXT_PUBLIC_EXPLAIN_API_URL` :8003, `NEXT_PUBLIC_ENADE_TIME_API_URL` :8002) | Quando todos os routers estiverem no `api_main`, padronizar em uma variável; o ENADE-Time passa a apontar para :8000 só trocando o valor, sem mudar código | — |
| 9 | O projeto Supabase é do plano gratuito: pausa após 7 dias sem uso | Acordar o projeto um dia antes de qualquer demonstração (Dashboard → Restore) | 2 min |

## Frontend (EnadeX_Frontend)

| # | Fato verificado | Sugestão |
|---|---|---|
| F1 | `public/` não existe: os 4 ícones do `app/layout.tsx` dão 404 | Criar `public/` com os ícones (ou tirar as referências) |
| F2 | `next.config.mjs` tem `typescript.ignoreBuildErrors: true`; o `next build` não checa tipos (o `tsc` do projeto está limpo hoje) | Remover a opção, ou acrescentar um script `typecheck` (`tsc --noEmit`) |
| F3 | Três cores do projeto reprovam o WCAG AA sobre fundo claro: `#8aa0c1` e `#91a4c3` (2,5:1) e `#009b67` (3,4:1) | Adotar `#5f7393` e `#047857` (4,5:1 ou mais), como no módulo ENADE-Time |
| F4 | `.gitignore` tem `.env*`, o que também ignora um `.env.example` | Acrescentar `!.env.example` |
| F5 | `package.json` tem `"name": "my-project"`; não há scripts de lint nem de typecheck | Renomear e acrescentar scripts |
| F6 | O card da home do ENADE-Time dizia `2017–2021` (a base vai de 2005 a 2021) e o KPI "05 · 2017 até 2021" continua; EduCluster segue sem `href` | O card já foi corrigido; o KPI e o `href` do EduCluster ficam com o líder |

## O que não é proposta, mas o líder precisa saber

A função `public.truncar_tabela` do Supabase continua executável pela chave pública e esvazia
qualquer tabela do projeto (`docs/COMUNICADO_SEGURANCA.md`). A checagem `13_validar_metricas.py
--cruzado` avisa isso a cada execução. As tabelas do ENADE-Time são republicáveis a qualquer
momento (`12_publicar_supabase.py`, idempotente), mas as dos outros subprojetos não têm essa rede.
