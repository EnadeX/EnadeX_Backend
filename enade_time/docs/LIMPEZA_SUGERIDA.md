# Limpeza sugerida (pós-entrega)

Documento consolidado de sugestões de organização e arquivamento.
**Nada deve ser apagado antes da apresentação final.** Este arquivo
serve como referência para uma limpeza opcional **depois** da
validação pela banca.

Também consolida o conteúdo de
[`frontend/NOTAS_ORGANIZACAO.md`](../frontend/NOTAS_ORGANIZACAO.md), que
permanece válido — este aqui é o documento canônico do projeto.

---

## Atenção: pasta oficial do projeto

> A pasta oficial é **`C:\Projetos\ENADE`**.
>
> **Não usar** a cópia antiga que existia dentro do OneDrive: o
> sincronizador interfere em medições de I/O e gera falsos
> resultados de benchmark (foi exatamente o que aconteceu nas
> execuções inválidas #1, #2 e #3).
>
> Se a cópia em OneDrive ainda existir na sua máquina, considere
> renomear a pasta para algo como `ENADE_OneDrive_OBSOLETO\` para
> evitar abrir por engano. **Não apagar** sem antes confirmar que tudo
> que estava lá já está em `C:\Projetos\ENADE\`.

---

## 1. Manter obrigatoriamente (não remover)

Itens essenciais para reprodutibilidade e para a entrega:

- `README.md` (raiz)
- `docs/` (todos os arquivos da Fase 5)
- `docker-compose.yml`
- `.env.example`
- `scripts/01_..` até `scripts/10_..` (todos)
- `etl/` (módulo compartilhado dos scripts 08, 09, 10)
- `api/` (FastAPI completa)
- `frontend/` (código-fonte + `package.json`)
- `dados_processados/` (CSVs filtrados/consolidados — entrada do COPY)
- Microdados brutos das **6 edições usadas**:
  - `microdados_enade_2005_LGPD/`
  - `microdados_enade_2008_LGPD/`
  - `microdados_enade_2011/`
  - `microdados_enade_2014_LGPD/`
  - `microdados_enade_2017_LGPD/`
  - `microdados_enade_2021/`

## 2. Pode arquivar depois (sem perda funcional)

Pastas de microdados que estão no diretório, mas **não fazem parte do
recorte trienal de Computação** do estudo. Podem ser movidas para
mídia externa (HD/cloud) ou para uma pasta `microdados_enade_brutos_arquivados/`
após a entrega:

| Pasta | Motivo |
|---|---|
| `microdados_enade_2010/` | 2010 não é ano de ciclo para Computação |
| `microdados_enade_2012_LGPD/` | Fora do ciclo trienal (2011 → 2014) |
| `microdados_enade_2013_LGPD/` | Fora do ciclo |
| `microdados_enade_2015_LGPD/` | Fora do ciclo (2014 → 2017) |
| `microdados_enade_2016_LGPD/` | Fora do ciclo |
| `microdados_enade_2018_LGPD/` | Fora do ciclo (2017 → 2021) |
| `microdados_enade_2019_LGPD/` | Fora do ciclo |
| `microdados_enade_2022_LGPD/` | Fora do recorte do experimento |
| `microdados_enade_2023/` | Fora do recorte do experimento |

> Se o recorte for **ampliado** futuramente (ex.: incluir 2023), essas
> pastas voltam a ser necessárias — daí o arquivamento, e não a
> remoção definitiva.

Outros itens arquiváveis após a entrega:

- `scripts/__pycache__/` — caches do Python, regeráveis automaticamente.
- `frontend/node_modules/` — regerável com `npm install`. Já está em
  `.gitignore`.
- `frontend/dist/` — gerado por `npm run build`. Regerável.
- `.venv/` — ambiente virtual local, regerável com
  `python -m venv .venv && pip install`.

## 3. Não remover antes da apresentação

Mesmo que pareçam "intermediários", estes itens são consultados
durante a defesa e devem permanecer intactos:

- Execuções **inválidas** #1, #2, #3 em `tbl_enade_time_benchmark_execucao` — provam
  a importância de rodar fora do OneDrive (lição aprendida do
  projeto).
- `frontend/NOTAS_ORGANIZACAO.md` — referência histórica desta
  decisão.
- `.env.example` — sem ele, fica menos óbvio reproduzir o ambiente.
- Resultados do `npm run build` em `dist/` (se a apresentação envolver
  rodar `npm run preview`).

## 4. Atenção com OneDrive

Regras práticas para evitar repetir o problema de I/O:

- **Não mover** `C:\Projetos\ENADE` para dentro de pastas
  sincronizadas (`OneDrive`, `Dropbox`, `Google Drive`).
- Se precisar de **backup**, copiar para `.zip` periodicamente em
  outro local — **não** sincronizar a pasta de trabalho.
- Antes de rodar qualquer benchmark, conferir que o caminho do
  projeto **não** começa com `C:\Users\<usuário>\OneDrive\…`.

---

## Checklist final (pós-apresentação)

Marcar quando cada item for executado:

- [ ] Confirmar com a banca que a defesa foi aceita.
- [ ] Mover as pastas `microdados_enade_*` da seção 2 para
      `microdados_enade_brutos_arquivados/` ou mídia externa.
- [ ] Apagar caches: `scripts/__pycache__/`, `frontend/dist/`,
      `frontend/node_modules/` (regeráveis).
- [ ] Verificar se `.venv/` precisa permanecer (depende do uso futuro).
- [ ] Renomear ou remover qualquer cópia residual do projeto que
      esteja em OneDrive.
- [ ] Atualizar `README.md` e este documento se algo mudar de status.

> Reforço: **nenhum desses passos é obrigatório**. O projeto está
> entregável como está em `C:\Projetos\ENADE`.
