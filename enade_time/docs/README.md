# Documentação — ENADE-Time Distribuído

Índice da documentação acadêmica do projeto. Os arquivos abaixo formam
o pacote de entrega da **Fase 5** (empacotamento e documentação final).

> Para o overview do projeto, ver o
> [`README.md` da raiz](../README.md).

## Índice

| Documento | Para quem | Conteúdo |
|---|---|---|
| [GUIA_EXECUCAO.md](GUIA_EXECUCAO.md) | Quem vai **rodar** | Passo a passo do zero (Docker → banco → API → frontend) + troubleshooting completo |
| [ARQUITETURA.md](ARQUITETURA.md) | Quem vai **entender** | Camadas, fluxo de dados, modelo de tabelas, decisões técnicas justificadas |
| [DICIONARIO_VARIAVEIS.md](DICIONARIO_VARIAVEIS.md) | Quem vai **entender os dados** | Variável a variável: nome original por ano → forma harmonizada → mudanças entre ciclos |
| [LOG_EXECUCAO_ETL.md](LOG_EXECUCAO_ETL.md) | Quem vai **auditar** | Registro das execuções do ETL e das alterações controladas na base consolidada |
| [DESIGN_LOG.md](DESIGN_LOG.md) | Quem vai **entender as escolhas** | Decisões de projeto e alternativas descartadas, com justificativa (D1–D17) |
| [RELATORIO_VERIFICACAO.md](RELATORIO_VERIFICACAO.md) | Quem vai **auditar a migração** | Estado real do projeto, do repositório EnadeX e do Supabase em 2026-09-01; bug do baseline; ordem de despacho; máquina |
| [COMUNICADO_SEGURANCA.md](COMUNICADO_SEGURANCA.md) | Líder do EnadeX | RPC `truncar_tabela` exposta e modelo de chaves do grupo |
| [INTEGRACAO_ECOSSISTEMA.md](INTEGRACAO_ECOSSISTEMA.md) | Quem vai **integrar** | Como este módulo conversa com os demais módulos do projeto |
| [RESULTADOS_BENCHMARK.md](RESULTADOS_BENCHMARK.md) | Quem vai **avaliar** | Números oficiais da Fase 2 (execuções #4, #5, #6), conclusão e explicação da Lei de Amdahl |
| [EVIDENCIAS_TESTES.md](EVIDENCIAS_TESTES.md) | Quem vai **entregar** | Checklist com 14 prints a anexar, com comando e resultado esperado de cada um |
| [GUIA_APRESENTACAO.md](GUIA_APRESENTACAO.md) | Quem vai **apresentar** | Roteiro oral de 8–12 min, falas-modelo, FAQ da banca |
| [LIMPEZA_SUGERIDA.md](LIMPEZA_SUGERIDA.md) | Pós-entrega | O que pode ser arquivado depois (sem apagar nada agora) |
| [PROXIMOS_PASSOS.md](PROXIMOS_PASSOS.md) | Quem vai **continuar** | Roadmap de Dockerfile, deploy, testes, CI/CD, melhorias acadêmicas |

## Convenções

- Linguagem: **português (pt-BR)**.
- Caminhos: **Windows / PowerShell**, com diretório base
  `C:\Projetos\ENADE`.
- Os documentos referenciam-se entre si por links relativos
  (`./XXX.md`); funcionam no GitHub, VS Code e qualquer leitor
  Markdown padrão.

## Como ler primeiro

- **Começando do zero**: leia `../README.md` → siga `GUIA_EXECUCAO.md`.
- **Avaliando o projeto**: leia `ARQUITETURA.md` →
  `RESULTADOS_BENCHMARK.md` → `EVIDENCIAS_TESTES.md`.
- **Preparando defesa**: leia `GUIA_APRESENTACAO.md` →
  `RESULTADOS_BENCHMARK.md` (números exatos).
- **Continuando o projeto**: leia `PROXIMOS_PASSOS.md`.

## Documentos auxiliares fora desta pasta

- [`../README.md`](../README.md) — overview do projeto.
- [`../frontend/README.md`](../frontend/README.md) — comandos
  específicos do frontend.
- [`../frontend/NOTAS_ORGANIZACAO.md`](../frontend/NOTAS_ORGANIZACAO.md)
  — notas históricas de organização (consolidadas em
  `LIMPEZA_SUGERIDA.md`).
- [`../api/`](../api/) — código-fonte da API (Swagger em runtime).
- [`../scripts/`](../scripts/) — scripts 01 a 11 da pipeline (11 = carga do
  consolidado no Supabase, opcional).
