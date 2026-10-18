# Descrição sugerida para o PR `enade-time/migracao` → `main`

> Texto para colar no PR (a abertura do PR é do Lucas: esta máquina não tem login no `gh`).

## ENADE-Time Distribuído na pasta `enade_time/`

Traz o Projeto 4 para o EnadeX: a base longitudinal do ENADE 2005–2021 (Computação, Norte/Nordeste),
o experimento de processamento paralelo (SPD) e a API que alimenta o módulo `/enade-time` do
`EnadeX_Frontend`. **Nada fora de `enade_time/` foi alterado**; o que seria útil fora dela está só
como proposta em `enade_time/docs/PROPOSTAS_COMPARTILHADAS.md`.

### O que muda para o resto do grupo
- Nenhum arquivo de outro subprojeto, nem `api_main.py`, `util/` ou `requirements.txt`.
- Para ligar a API ao `api_main.py` central bastam 2 linhas (import + `include_router`); o router
  é autocontido, não precisa de lifespan e responde 503 com CORS se o Postgres do subprojeto
  estiver fora. Detalhes em `enade_time/docs/COMUNICADO_GRUPO.md`.

### Conteúdo
- ETL 2005–2021 (24.967 inscrições = 582 cursos-ano, a unidade analítica) e dicionário de variáveis.
- Benchmark v2: campanha oficial, speedup/eficiência definidos em views SQL (a API só lê), duas
  ordens de submissão, máquina declarada.
- Eixo de carga (D17): custo de **publicar** a base, local × nuvem (COPY local, COPY pelo pooler e
  upsert pelo PostgREST), com controles que isolam índices e chaves estrangeiras. Medição situada,
  não speedup. Achado: o `util_db` e o `%.4f` do ETL arredondam empates de modo diferente.
- Publicação no Supabase com a convenção do grupo (`tbl_enade_time_*`, `v_enade_time_*`), RLS,
  leitura pública só de `SELECT`, md5 linha a linha, e `v_enade_time_curso_ano` (582 linhas) como
  ponto de troca com o E-XplainENADE.
- 20 rotas GET read-only em `/api/enade-time/*`; a API lê do Postgres local ou do Supabase
  (`--fonte supabase`, papel somente leitura).

### Como verificar
```powershell
$env:PYTHONPATH='.'
pip install -r enade_time\requirements.txt
python -m pytest enade_time\tests -q          # 122 passam (a leitura real do Supabase é pulada sem a chave pública)
python enade_time\scripts\13_validar_metricas.py            # métricas: Python, views e API concordam
python enade_time\enade_time_rotas.py                       # API na porta 8002
```
Verificação do dashboard (Chrome headless): `enade_time/tools/e2e_frontend` (funcional 59/59,
degradação 10/10, acessibilidade axe-core 0 violações em 13 páginas).

### Limites declarados
- O upsert pelo PostgREST foi medido como `anon` com política temporária numa tabela de teste, não
  com a chave de serviço (que ignora a RLS).
- As medições de rede descrevem uma máquina, uma rede e um horário (n = 10).
- Pendências de segurança do Supabase do projeto estão em `enade_time/docs/COMUNICADO_SEGURANCA.md`
  e dependem do líder.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
