# Guia de execução — ENADE-Time Distribuído

Passo a passo completo para rodar o projeto do zero. Os comandos assumem
**PowerShell** no Windows e o diretório `C:\Projetos\ENADE`.

## Pré-requisitos

- **Docker Desktop** rodando (para o PostgreSQL)
- **Python 3.13** (já existe `.venv\` no projeto)
- **Node.js ≥ 20** (testado com Node 24)
- **Portas livres:** 5432 (Postgres), 8000 (API), 5173 (frontend dev), 3000 (frontend preview)

---

## 1. Subir o PostgreSQL

```powershell
cd C:\Projetos\ENADE
docker compose up -d postgres
docker compose ps
```

Esperado em `docker compose ps`:
- Container `enade_postgres` no estado `Up` e `(healthy)`.
- Porta `5432->5432` mapeada.

> Variáveis de ambiente padrão (em `.env.example` / `docker-compose.yml`):
> `POSTGRES_DB=enade_db`, `POSTGRES_USER=enade_user`,
> `POSTGRES_PASSWORD=enade_password`.

---

## 2. Validar o banco

Ative o ambiente virtual e rode o validador:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\07_validar_banco.py
```

Esperado: o script reporta **24.967 linhas** em `fato_enade` e confirma
presença das dimensões e tabelas de benchmark.

### Primeira execução (banco vazio)

Se for a primeira subida do container (volume novo), criar schema + carga:

```powershell
python scripts\05_criar_schema_postgres.py
python scripts\06_carregar_dados_postgres.py
python scripts\07_validar_banco.py
```

> Os scripts 01–04 reprocessam os microdados brutos. Não é necessário
> rodá-los novamente — os CSVs já estão consolidados em
> `dados_processados\`.

### Schema v2 do benchmark (aditivo — obrigatório antes de medir)

```powershell
python scripts\14_migrar_schema_v2.py --status   # mostra o que existe
python scripts\14_migrar_schema_v2.py            # aplica (idempotente; nada é apagado)
```

> **Nunca** use `05_criar_schema_postgres.py --reset` em um banco com dados:
> ele dropa `benchmark_execucao`/`benchmark_etapa` (incidente D9). O 14 só
> adiciona colunas e substitui views. Instalações novas já nascem com a v2
> (o 05 importa o 14).

### Benchmark — campanha oficial (Fase 6 / v2)

```powershell
# smoke (1 suíte: sequencial + 2 workers LPT), ~3 min, não oficial
python scripts\10_rodar_suite_benchmark.py --workers 2 --ordens lpt --reps 1 --sem-aquecer --obs smoke

# campanha oficial: aquecimento + 5 suítes × (1 seq + {2,3,4,6} × {crescente,lpt}) = 45 execuções, ~45 min
python scripts\10_rodar_suite_benchmark.py --oficial --obs "descreva a máquina e o que está rodando"

# checagem cruzada Python × views × API
python scripts\13_validar_metricas.py --api http://localhost:8000
```

Condições para uma campanha válida: projeto **fora do OneDrive**; Docker só
com o Postgres (pare `enade_api` se estiver de pé); sem API, frontend ou
build rodando; nada pesado em segundo plano. O script mede a CPU ociosa por
10 s antes de começar e grava o valor em todas as execuções — se estiver alta,
investigue antes de medir. Cada execução individual também aceita
`--campanha/--suite/--oficial` (scripts 08 e 09) e o 09 aceita
`--ordem crescente|lpt` e `--tempos-de <id_sequencial>`.

> O `/api/benchmark/comparativo` mostra por padrão a **campanha oficial mais
> recente** (agregada em `resumo[]`); `?apenas_validas=false` devolve o
> histórico inteiro e `?campanha_id=…`/`?suite_id=…` fazem o drill-down.
> `BENCHMARK_IDS_EXCLUIR` (JSON) continua disponível para ocultar ids
> específicos — ex.: `$env:BENCHMARK_IDS_EXCLUIR='[1,2,3]'`.

Resultados e leitura: [`RESULTADOS_BENCHMARK.md`](RESULTADOS_BENCHMARK.md)
(gerado do banco por `docs/geradores/gerar_resultados_md.py`).

---

## 3. Subir a API (FastAPI)

### Opção A — no host, com hot reload (recomendada para desenvolver)

```powershell
# da raiz do EnadeX, venv já ativo
$env:PYTHONPATH='.'
pip install -r enade_time\requirements.txt   # primeira vez apenas
python enade_time\enade_time_rotas.py        # API standalone em http://localhost:8002
```

> As URLs desta seção que citam a porta 8000 e o prefixo `/api/` são da API
> legada (`enade_time.api.main`, usada pela SPA Vite e pelos testes). No
> ecossistema a API é a de cima: porta **8002**, prefixo **`/api/enade-time`**
> (ex.: `http://localhost:8002/api/enade-time/health`).

### Opção B — em container (Fase 5)

```powershell
cd C:\Projetos\ENADE
docker compose --profile api up -d --build
docker compose ps
```

Sobe `enade_postgres` **e** `enade_api` na mesma porta 8000. O serviço `api`
fica atrás de um profile, então `docker compose up -d postgres` continua
subindo só o banco. Sem hot reload — rebuild após alterar o código:
`docker compose --profile api up -d --build`.

Testar:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/benchmark/comparativo
```

URLs úteis:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

---

## 4. Subir o frontend (em outro terminal)

### Dashboard canônico: módulo `/enade-time` do `EnadeX_Frontend`

```powershell
cd C:\Projetos\EnadeX_Frontend
pnpm install --frozen-lockfile           # primeira vez apenas (pnpm 12.3.4)
pnpm dev -p 3000                         # http://localhost:3000/enade-time
```

Use sempre a porta 3000: é a única origem liberada no CORS da API. Detalhes,
variável de ambiente e verificação em `docs/FRONTEND_ECOSSISTEMA.md`.

### SPA original (Vite) — artefato do TCC

```powershell
cd C:\Projetos\ENADE\frontend
npm install                              # primeira vez apenas
npm run dev                              # http://localhost:5173
```

### Build de produção servido localmente

```powershell
npm run build
npm run preview -- --host 0.0.0.0 --port 3000
```

Após `npm run build`, o conteúdo estático fica em `frontend\dist\`.

URLs:
- Dev (HMR): http://localhost:5173
- Preview (build): http://localhost:3000

---

## 5. Testes, validação e geradores

```powershell
# venv ativo; Postgres no ar (os testes de banco são PULADOS sem ele)
pip install -r api\requirements.txt pytest httpx      # primeira vez
pytest -q                                              # filtros, repositórios, views, rotas

# documento (.docx), apresentação (.pptx) e RESULTADOS_BENCHMARK.md — tudo lido das views
python docs\geradores\analise_escalonamento.py --json docs\geradores\out\escalonamento.json --md
python docs\geradores\gerar_resultados_md.py
python docs\geradores\gerar_apresentacao.py
python docs\geradores\gerar_documento.py

# confere que nenhum número do .pptx/.docx está fora das views (lista negra da rodada perdida inclusa)
python docs\geradores\verificar_numeros.py --pptx docs\geradores\out\apresentacao.pptx `
    --docx docs\geradores\out\ENADE_Time_Distribuido_Documento_Academico.docx `
    --escalonamento docs\geradores\out\escalonamento.json
```

As capturas de tela e os diagramas usados pelos geradores ficam fora do git
(`apresentacao/documento_final/` neste repositório); aponte outra pasta com
`--screenshots`/`--ativos` ou `GERADORES_SCREENSHOTS`/`GERADORES_ATIVOS`.

---

## 6. Ordem completa (resumo)

```powershell
# Terminal 1 — banco
cd C:\Projetos\ENADE
docker compose up -d postgres
docker compose ps
.\.venv\Scripts\Activate.ps1
python scripts\07_validar_banco.py

# Terminal 1 (continua) — API
pip install -r api\requirements.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd C:\Projetos\ENADE\frontend
npm install
npm run dev
```

---

## Troubleshooting

### Docker não está rodando

**Sintoma:** `docker compose up` falha com `Cannot connect to the Docker daemon`.

**Solução:**
1. Abrir o Docker Desktop e aguardar o tray icon ficar verde.
2. Rodar `docker version` para confirmar.
3. Em alguns hosts: reiniciar o serviço `com.docker.service` ou logout/login.

### Postgres `unhealthy` ou não aceita conexão

```powershell
docker compose logs postgres --tail 50
docker exec enade_postgres pg_isready -U enade_user -d enade_db
```

Se o container não inicializou o banco corretamente, **com cuidado**:
remover o volume e subir de novo (perde dados — só faça se for a
primeira subida e ainda não houver dados úteis).

### API offline no frontend (badge vermelho no header)

1. Confirmar que `uvicorn` está rodando: visitar http://localhost:8000/docs.
2. Confirmar que `frontend\.env.development` aponta para
   `VITE_API_BASE_URL=http://localhost:8000`.
3. Confirmar que não há outra aplicação ocupando a porta 8000:
   `Get-NetTCPConnection -LocalPort 8000`.
4. Reiniciar o dev server do frontend após mudar `.env`:
   `Ctrl+C` e `npm run dev` novamente.

### CORS bloqueado (Network tab mostra erro CORS no preview)

A API libera CORS apenas para `http://localhost:5173` (dev) e
`http://localhost:3000` (preview). Se você rodar o preview em outra
porta, há duas saídas:

- **Recomendada:** rodar `npm run preview -- --host 0.0.0.0 --port 3000`
  (mantém origin já permitida).
- **Alternativa:** ajustar `CORS_ORIGINS` no `.env` da API (variável de
  ambiente lida em `api/settings.py`) e reiniciar o uvicorn.

> Não comitar credenciais ou origens de produção no repositório.

### Porta 5173 ou 3000 já está ocupada

```powershell
# Descobrir o processo
Get-NetTCPConnection -LocalPort 5173 | Select-Object OwningProcess
Get-Process -Id <PID>
```

- Encerrar o processo conflitante, ou
- Rodar em outra porta: `npm run dev -- --port 5174`. Se mudar a porta
  do frontend, ajustar `CORS_ORIGINS` na API conforme acima.

### API rodando, mas o frontend exibe gráficos vazios

1. Abrir o DevTools (F12) → Network → recarregar a página.
2. Ver se as chamadas `/api/...` retornam 200. Se retornarem CORS error,
   ver seção CORS acima.
3. Se retornarem 404 em `/api/...`: confirmar prefixo `/api` no router
   da FastAPI (deve estar; é o caso atual).
4. Conferir `/api/health` direto no navegador. Se OK, é problema do
   frontend → reiniciar `npm run dev`.

### `npm run build` com aviso "chunk size > 500 kB"

Aviso esperado por causa do Recharts e do dataset de leitura. **Não é
um erro** — o build passa normalmente. Ações possíveis (não obrigatórias
para a entrega):

- Configurar `build.chunkSizeWarningLimit` em `vite.config.ts`.
- Code-splitting por rota com `React.lazy` + `Suspense`.

Ver [`PROXIMOS_PASSOS.md`](PROXIMOS_PASSOS.md).

### `npm audit` reportando vulnerabilidades

Mensagens de auditoria são informativas e geralmente referem-se a
dependências transitivas de ferramentas de build (Vite, etc.) em modo
de desenvolvimento, **sem exposição em produção** deste projeto local.

**Não rodar `npm audit fix --force`** — pode quebrar versões fixadas em
`package.json`.

### Recharts deprecated warning

Recharts 2.x emite avisos de deprecação para componentes que terão API
revista na v3. O dashboard funciona normalmente em v2.13. Atualização
para v3 está em [`PROXIMOS_PASSOS.md`](PROXIMOS_PASSOS.md) e **não deve
ser feita durante a janela da entrega**.

### `python scripts\07_validar_banco.py` falha com `ModuleNotFoundError`

```powershell
.\.venv\Scripts\Activate.ps1
pip install psycopg2-binary pandas psutil
```

Confirmar que o prompt mostra `(.venv)` antes de rodar Python.

### Frontend não encontra `lucide-react`/`react-router-dom` no editor

Diagnósticos do tipo `Cannot find module 'X'` no VS Code antes de
`npm install` são esperados — desaparecem após a instalação das
dependências.
