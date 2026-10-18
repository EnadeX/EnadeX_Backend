# EduCluster

Modulo do ecossistema EnadeX. Descoberta de perfis academicos latentes nos microdados do ENADE 2021.

Projeto irmao de `multi_enade/`, com pipeline e dependencias proprias. Nao modifica nenhum arquivo fora desta pasta.

## Estrutura

```
educluster/
  educluster_config.py       constantes, dimensoes do arq4, features, reprodutibilidade
  educluster_dados.py        carga plugavel: Supabase (padrao) ou microdados locais
  educluster_preparo.py      limpeza da escala, derivacao de area, agregacao por curso
  educluster_endpoints.py    rotas (APIRouter) e app standalone com CORS
  educluster_interpretacao.py  descricao automatica dos perfis via Gemini, com cache
  modelos/
    mdl_curso_percepcao/       A6 e A7, mais estabilidade por reamostragem
    mdl_perfil_desempenho/     A1: perfis de desempenho no nivel do estudante
    mdl_calibracao_prova/      A3: percepcao da prova versus desempenho
    mdl_situacao_discursiva/   A4: desistencia versus erro conceitual
    mdl_dimensao_desempenho/   A8: qual dimensao percebida se associa ao desempenho
    mdl_comparacao_tradicional/ Fase 6: artefato versus ranking por nota media
  banco/
    criar_tabelas_educluster.sql   cria as tabelas do EduCluster no Supabase
    carga_supabase.py              sobe a base nacional do zip do INEP para o Supabase
    verificar_ponta_a_ponta.py     confere banco, analises e modelos contra os resultados aprovados
```

## Analises implementadas

**A6, perfis de curso (analise central).** Cruza arq3 e arq4 agregados por `CO_CURSO`, unico join permitido pela versao LGPD dos microdados. Features: `NT_FG`, `NT_CE`, taxa de presenca, e as tres dimensoes percebidas do arq4 (ODP, OPORT, INFRA). Base de 3.832 cursos com no minimo 20 respondentes em cada arquivo, representando 316.232 estudantes em 30 areas.

**A1, perfis de desempenho.** Nivel do estudante, apenas arq3. Espaco padrao `objetivo_discursivo` (`NT_OBJ_FG`, `NT_DIS_FG`, `NT_OBJ_CE`, `NT_DIS_CE`), que substitui o trio colinear usado no TCC 1. Os espacos `trio` e `par` seguem disponiveis para comparacao: so o `objetivo_discursivo` tem modelo treinado e versionado, e os outros dois sao reagrupados em memoria na primeira chamada (k por silhouette, `random_state=42`), sem gravar joblib.

## Decisoes de tratamento

- **Escala do arq4**: os codigos 7 (nao sei responder) e 8 (nao se aplica) viram nulo. O codigo 6 e resposta valida (concordo totalmente) e e preservado
- **Area do curso**: derivada de `DS_VT_GAB_OCE_FIN`, que tem 30 valores e mapeia 1 para 1 com o curso e com o `CO_GRUPO` do arq1
- **Reprodutibilidade**: `random_state=42` e `n_init=10` em todo K-Means, `sample_size` explicito no silhouette do nivel estudante

## Como rodar

Executar da raiz do repositorio (`EnadeX/`), com o `.env` (SUPABASE_URL e SUPABASE_KEY) na raiz:

```
pip install -r educluster/requirements.txt
PYTHONPATH=. python -m educluster.educluster_endpoints
```

A documentacao interativa fica em `http://localhost:8001/docs`. A primeira chamada baixa o arq3 e o arq4 do Supabase (cerca de 60 s); as seguintes usam o cache em memoria.

O frontend do ecossistema (`EnadeX_Frontend`, Next.js em `http://localhost:3000`) chama esta API direto do navegador, por isso a app standalone tem CORS. As origens liberadas vem de `EDUCLUSTER_CORS_ORIGENS` (lista separada por virgula, padrao `http://localhost:3000`).

Para entrar no `api_main.py` do grupo, basta incluir o router: `from educluster.educluster_endpoints import router as edu_cluster_router` e `app.include_router(edu_cluster_router)`. O CORS fica a cargo do `api_main.py`, que ja libera `http://localhost:3000`.

Verificar se banco, analises e modelos continuam batendo com os resultados aprovados:

```
PYTHONPATH=. python -m educluster.banco.verificar_ponta_a_ponta
```

## Fonte de dados

O padrao e o Supabase, nas tabelas proprias do EduCluster:

| Tabela | Conteudo | Linhas |
|---|---|---|
| `tbl_educluster_arq3_2021` | notas, presenca, gabarito do CE, percepcao da prova, situacao das discursivas | 489.866 |
| `tbl_educluster_arq4_2021` | as 42 assertivas QE_I27 a QE_I68 | 489.866 |
| `tbl_educluster_cursos_2021` | atributos do curso vindos do arq1 (IES, categoria, organizacao, grupo, modalidade, municipio, UF, regiao) | 7.997 |

Sao a base nacional completa do ENADE 2021. As tabelas `tbl_arqN_2021` do grupo nao servem ao EduCluster: guardam so o recorte do MultiENADE (CC e SI do Norte e Nordeste) e sao esvaziadas e recarregadas pelos scripts de refino dele.

Para recriar: rodar `banco/criar_tabelas_educluster.sql` no SQL Editor do Supabase e depois `PYTHONPATH=. python -m educluster.banco.carga_supabase` (le direto do zip do INEP em `~/Downloads/microdados_enade_2021.zip` ou do caminho em `EDUCLUSTER_ZIP_MICRODADOS`; `--substituir` recarrega tabelas ja preenchidas).

A leitura busca faixas de 1.000 ids em paralelo, com novas tentativas automaticas, e confere se recebeu todas as linhas. Cada tabela e baixada uma unica vez por processo, mesmo com chamadas simultaneas.

A origem pode ser trocada pela variavel de ambiente `EDUCLUSTER_ORIGEM` (`supabase` ou `local`) ou pelo parametro `origem` de cada rota. `local` le os `.txt` de `../microdados/microdados_Enade_2021_LGPD/2.DADOS/`.

## Rotas

Prefixo `/api/educluster`. Organizadas por recurso e granularidade, nao por analise.

| Rota | Analise | Retorno |
|---|---|---|
| `GET /cursos` | A6 | Colecao com cluster e PCA. Filtros `area` e `cluster` |
| `GET /cursos/clusters` | A6 | Perfil de cada cluster e metricas |
| `GET /cursos/discrepantes` | A7 | Cursos que destoam dos pares da area |
| `GET /cursos/{co_curso}` | A6 | Detalhe de um curso |
| `GET /estudantes/clusters` | A1 | Perfil de cada cluster de desempenho |
| `GET /estudantes/amostra` | A1 | Amostra reprodutivel para plotagem |
| `GET /areas` | catalogo | As 30 areas com agregados |
| `GET /dimensoes` | catalogo | ODP, OPORT e INFRA com seus itens |
| `GET /espacos-desempenho` | catalogo | Espacos de variaveis da A1 |
| `GET /health` | catalogo | Saude da API, versao, origem e se a base de cursos ja esta em memoria |

Parametros gerais: `origem` (`supabase`, padrao, ou `local`), `n_minimo`, `k` (reclusteriza em memoria).

A A1 nao expoe colecao completa: seriam 51,2 MB para 354.899 estudantes. Expoe resumo e amostra.

Status: 200 valido, 404 curso ausente, 422 parametro fora da faixa, 503 fonte indisponivel.
