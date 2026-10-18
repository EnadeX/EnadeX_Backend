# Notas de organização do projeto

Documento criado na Fase 4 (frontend) para registrar pastas e arquivos que
**possivelmente** podem ser arquivados ou removidos no futuro, **sem** apagar
nada agora. A remoção só deve acontecer após a validação final do projeto
(defesa/entrega) e com aprovação explícita.

## Escopo válido do projeto (referência)

- **Edições do ENADE consideradas:** 2005, 2008, 2011, 2014, 2017, 2021
  (ciclos trienais de Computação; 2021 é a reaplicação pós-pandemia).
- **Regiões:** Norte e Nordeste.
- **Cursos:** Ciência da Computação (CO_GRUPO=40) e Sistemas de
  Informação (CO_GRUPO=4004).
- **Total processado:** 24.967 registros em `fato_enade`.

## Diretórios `microdados_enade_*` não utilizados pelo recorte

As pastas abaixo foram baixadas, mas não fazem parte do recorte trienal
de Computação. Podem ser arquivadas em mídia externa **sem perda** para o
projeto atual.

| Pasta | Motivo de não ser usada |
|---|---|
| `microdados_enade_2010` | 2010 não é ano de aplicação do ENADE para Computação (ciclo é trienal: 2008 → 2011) |
| `microdados_enade_2012_LGPD` | 2012 não é ano de ciclo para Computação |
| `microdados_enade_2013_LGPD` | 2013 não é ano de ciclo |
| `microdados_enade_2015_LGPD` | 2015 não é ano de ciclo (entre 2014 e 2017) |
| `microdados_enade_2016_LGPD` | 2016 não é ano de ciclo |
| `microdados_enade_2018_LGPD` | 2018 não é ano de ciclo (entre 2017 e 2021) |
| `microdados_enade_2019_LGPD` | 2019 não é ano de ciclo |
| `microdados_enade_2022_LGPD` | 2022 fora do recorte definido para o experimento |
| `microdados_enade_2023` | 2023 fora do recorte definido |

**Ação sugerida (futura):** mover essas pastas para `microdados_enade_brutos_arquivados/`
ou para mídia externa (HD/cloud) antes da entrega final, mantendo só as
6 edições efetivamente usadas.

**Atenção:** se algum dia o recorte for expandido (ex.: incluir 2018 ou
2023), essas pastas voltam a ser necessárias.

## Diretórios usados (NÃO remover)

- `microdados_enade_2005_LGPD/`
- `microdados_enade_2008_LGPD/`
- `microdados_enade_2011/`
- `microdados_enade_2014_LGPD/`
- `microdados_enade_2017_LGPD/`
- `microdados_enade_2021/`

## Outras observações de organização

- **`dados_processados/`**: contém os CSVs filtrados/consolidados gerados
  pelos scripts 02 e 03. **Não remover** — são entrada para o COPY do
  PostgreSQL (script 06) e referência de validação.
- **`.venv/`**: ambiente virtual local Python. Pode ser recriado a
  qualquer momento via `python -m venv .venv` + `pip install`. Pode ser
  excluído antes de empacotar o projeto (já está no `.gitignore` típico).
- **`scripts/`**: contém os 10 scripts numerados (01 a 10). **Manter
  todos** — fazem parte da reprodutibilidade do experimento, mesmo os
  que rodam só uma vez (ex.: criação de schema).
- **`etl/`**: módulo Python reutilizado pelos scripts de benchmark.
  **Manter**.
- **`api/`**: backend FastAPI (Fase 3). **Manter**.
- **`frontend/`**: dashboard React (Fase 4). **Manter**.
- **`docker-compose.yml`**: só sobe o Postgres por ora. Na Fase 5
  receberá serviços de API e frontend.
- **`.env.example`**: template para variáveis do Postgres. **Manter**.

## Checklist antes da entrega final

- [ ] Confirmar que `npm run build` do frontend gera `dist/` sem erros.
- [ ] Confirmar que `pip install -r api/requirements.txt` instala em
      ambiente limpo.
- [ ] Confirmar que `docker compose up -d` sobe o Postgres e que os
      scripts 05 e 06 reidratam o banco do zero a partir do CSV
      consolidado em `dados_processados/`.
- [ ] Decidir se as pastas `microdados_enade_*` fora do recorte vão para
      arquivo morto antes da entrega.
- [ ] Atualizar este arquivo se algum item desta lista mudar de status.
