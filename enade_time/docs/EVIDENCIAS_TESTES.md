# Evidências de testes — checklist de entrega

Documento para anexar as capturas de tela (prints) que comprovam o
funcionamento de cada camada do projeto. Os espaços abaixo estão
**vazios propositadamente** — adicione cada imagem antes da entrega
final.

## Convenções

- Salvar as imagens em `docs\evidencias\` (pode criar a pasta no
  momento da entrega).
- Nomear sequencialmente: `01_docker_ps.png`, `02_validar_banco.png`,
  etc.
- Capturar a janela inteira com a barra de título visível para
  comprovar o contexto (terminal/navegador, hora, host).
- Preferir prints com **resolução nativa** (não capturar com zoom).

---

## 1. Infraestrutura

### 1.1 Docker / PostgreSQL healthy

**Comando:**
```powershell
docker compose ps
```

**Esperado:** linha do container `enade_postgres` com `STATUS = Up X minutes (healthy)` e porta `5432->5432`.

> _Adicionar print aqui — `docs/evidencias/01_docker_ps.png`._

---

### 1.2 Validação do banco — 24.967 linhas em `fato_enade`

**Comando:**
```powershell
.\.venv\Scripts\Activate.ps1
python scripts\07_validar_banco.py
```

**Esperado:** saída do script mostrando contagem `24967` em `fato_enade`, presença das dimensões e tabelas de benchmark.

> _Adicionar print aqui — `docs/evidencias/02_validar_banco.png`._

---

## 2. Benchmark v2 — schema, campanha e checagem cruzada

> Os valores esperados desta seção **não são digitados aqui**: são os de
> [`RESULTADOS_BENCHMARK.md`](RESULTADOS_BENCHMARK.md), gerado das views.
> Um print vale como evidência se os números batem com a tabela de lá.

### 2.1 Migração aditiva do schema

**Comando:**
```powershell
python scripts\14_migrar_schema_v2.py --status
```

**Esperado:** as 11 colunas da v2 marcadas `[x]`, `views: v_benchmark_metricas, v_benchmark_resumo`, `tbl_enade_time_publicacao: existe`, contagem de execuções com campanha e oficiais.

> _Adicionar print aqui — `docs/evidencias/03_schema_v2.png`._

---

### 2.2 Campanha oficial

**Comando:**
```powershell
python scripts\10_rodar_suite_benchmark.py --oficial --obs "..."
```

**Esperado:** cabeçalho com `4 físicos / 8 lógicos`, CPU ociosa medida, containers ativos; banner de aquecimento; as suítes (9 execuções cada, quando completas); ao final a tabela `RESUMO DA CAMPANHA (v_benchmark_resumo)` com o `n` de cada configuração e o caminho do manifesto em `backups/campanhas/`. Em cada paralela, a linha `Submissão: [...]` mostra a ordem usada e `Teto: makespan guloso … → speedup máx. …`.

> _Adicionar print aqui — `docs/evidencias/04_campanha.png`._

---

### 2.3 Checagem cruzada das métricas

**Comando:**
```powershell
python scripts\13_validar_metricas.py --api http://localhost:8000
```

**Esperado:** seções A (view × Python), B (resumo × numpy) e C (API) todas `OK`, terminando em `MÉTRICAS VALIDADAS: Python, views e API concordam.`

> _Adicionar print aqui — `docs/evidencias/05_validar_metricas.png`._

---

### 2.4 Testes automatizados

**Comando:**
```powershell
pytest -q
```

**Esperado:** suíte verde (filtros, repositórios, views de benchmark — inclusive o pareamento por suíte e a estrutura 5 × 9 da campanha oficial — e rotas).

> _Adicionar print aqui — `docs/evidencias/05b_pytest.png`._

---

## 3. Fase 3 — API FastAPI

### 3.1 Swagger UI

**URL:** http://localhost:8000/docs

**Esperado:** página Swagger com 4 grupos de endpoints (`health`, `dimensoes`, `analises`, `benchmark`) e ~15 rotas listadas.

> _Adicionar print aqui — `docs/evidencias/06_swagger.png`._

---

### 3.2 `/api/health`

**URL:** http://localhost:8000/api/health

**Esperado:** resposta JSON `{ "status": "ok", "database": "ok", "version": "0.2.0" }` (0.2.0 = schema v2 do benchmark + campanhas).

> _Adicionar print aqui — `docs/evidencias/07_health.png`._

---

### 3.3 `/api/benchmark/comparativo`

**URL:** http://localhost:8000/api/benchmark/comparativo

**Esperado:** JSON com `campanha_id` da campanha oficial, `maquina` (4 físicos / 8 lógicos, `cache_quente: true`), `resumo[]` com 9 configurações (com o `n` da campanha) e `itens[]` com as execuções oficiais, cada uma com `speedup`/`eficiencia` vindos da view e `pareamento: "suite"`. `baseline_sequencial_id` é `null` (o baseline de uma campanha é a mediana dos sequenciais).

> _Adicionar print aqui — `docs/evidencias/08_comparativo.png`._

---

## 4. Fase 4 — frontend

> As evidências desta seção e da 5 são da SPA original (Vite, `frontend/`). O
> mesmo dashboard, portado para o `EnadeX_Frontend`, foi verificado com
> checagens automatizadas no navegador — ver `docs/FRONTEND_ECOSSISTEMA.md` e
> `tools/e2e_frontend/`.

### 4.1 Visão geral

**URL:** http://localhost:5173

**Esperado:** badge "API online" no header; KPIs de cobertura (24.967 inscrições / 582 cursos-ano, 6 anos, 2 regiões, 16 UFs); KPIs de SPD com o baseline como **mediana da campanha** (dica "mediana de n suítes") e o melhor speedup/eficiência/throughput com a dica `N workers · ordem · mediana de n suítes`; card "Melhor configuração da campanha oficial: N workers · ordem" — os valores têm de bater com `RESULTADOS_BENCHMARK.md`.

> _Adicionar print aqui — `docs/evidencias/09_home.png`._

---

### 4.2 ENADE — por ano

**URL:** http://localhost:5173/enade/anual

**Esperado:** gráfico de linha com 6 pontos (2005, 2008, 2011, 2014, 2017, 2021) e cards de KPI calculados.

> _Adicionar print aqui — `docs/evidencias/10_enade_anual.png`._

---

### 4.3 SPD — comparativo (a tela-vitrine)

**URL:** http://localhost:5173/spd/comparativo

**Esperado:**
- Card verde com "Melhor configuração: N workers · LPT/crescente" e o speedup **mediano** com mín–máx e o nº de suítes.
- Card "Condições de medição": modelo da CPU, **4 núcleos físicos / 8 lógicos**, cache quente, id da campanha e nº de suítes.
- 4 gráficos: tempo e speedup com barra de erro mín–máx (mediana), eficiência com **uma linha por ordem de submissão**, throughput.
- "Interpretação desta campanha" gerada dos dados: melhor configuração, saturação/hyperthreads, as duas ordens e a estimativa de Karp–Flatt por configuração (com a ressalva do que ela embute).

> _Adicionar print aqui — `docs/evidencias/11_spd_comparativo.png`._

---

### 4.4 Drill-down de etapas

**URL:** http://localhost:5173/spd/etapas/<id de uma paralela LPT da campanha>

**Esperado:** gráfico de barras com tempo por ano e tabela das 6 etapas com `worker_pid` e timestamps — os anos maiores (2021, 2017, 2014) aparecem nos primeiros pids e os menores fecham o pool: é a ordem de submissão LPT em ação.

> _Adicionar print aqui — `docs/evidencias/12_etapas.png`._

---

## 5. Build do frontend

### 5.1 `npm run build` passando

**Comando:**
```powershell
cd C:\Projetos\ENADE\frontend
npm run build
```

**Esperado:** `vite v5.x building for production...`, lista de chunks em `dist/`, mensagem `built in X.XXs`. Pode haver aviso "chunks larger than 500 kB" — é informativo, não é erro.

> _Adicionar print aqui — `docs/evidencias/13_build.png`._

---

### 5.2 `npm run preview` rodando em :3000

**Comando:**
```powershell
npm run preview -- --host 0.0.0.0 --port 3000
```

**Esperado:** Vite servindo `dist/` em http://localhost:3000 e dashboard funcional com API conectada (CORS já configurado para essa porta).

> _Adicionar print aqui — `docs/evidencias/14_preview.png`._

---

## Resumo da bateria

| # | Item | Status |
|--:|------|:------:|
| 1.1 | Docker healthy | ⬜ |
| 1.2 | Banco com 24.967 linhas | ⬜ |
| 2.1 | Schema v2 (`14 --status`) | ⬜ |
| 2.2 | Campanha oficial (`10 --oficial`) | ⬜ |
| 2.3 | `13_validar_metricas --api` | ⬜ |
| 2.4 | `pytest -q` | ⬜ |
| 3.1 | Swagger UI | ⬜ |
| 3.2 | `/api/health` | ⬜ |
| 3.3 | `/api/benchmark/comparativo` | ⬜ |
| 4.1 | Frontend — Visão geral | ⬜ |
| 4.2 | Frontend — ENADE anual | ⬜ |
| 4.3 | Frontend — SPD comparativo | ⬜ |
| 4.4 | Frontend — etapas | ⬜ |
| 5.1 | `npm run build` | ⬜ |
| 5.2 | `npm run preview` em :3000 | ⬜ |

Marcar com `✅` cada item conforme o print correspondente for anexado.
