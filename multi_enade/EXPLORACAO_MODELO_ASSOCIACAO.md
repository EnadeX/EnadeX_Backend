# Exploração e revisão do modelo de associação — multi_enade

Registro do trabalho de revisão sobre `modelo_associacao.py`. O script
exploratório citado aqui (`exploracao_associacao_desempenho.py`) foi removido
do repositório depois de documentado — este arquivo é o registro permanente
das decisões e números que embasam o estado atual de produção.

## 1. Diagnóstico: por que o modelo original era pouco informativo

Produção original usava 3 itens — `QE_I30` ("O curso propiciou experiências
de aprendizagem inovadoras"), `QE_I56` ("Os professores apresentaram
disponibilidade...") e `QE_I57` ("Os professores demonstraram domínio dos
conteúdos...") — **todos do mesmo microtema** (satisfação com
professores/metodologia). Com os limiares de produção (suporte 0,25,
confiança 0,7), o resultado real (confirmado consultando `tbl_multi_enade_
associacao`) eram só 7 regras, todas do tipo "quem concorda totalmente com X
também concorda totalmente com Y" dentro desse mesmo tema — um efeito-halo
raso (gente satisfeita em um aspecto tende a estar satisfeita em todos),
pouco acionável como insight de negócio.

**Restrição conhecida** (mesma do LGPD discutida para o modelo de
regressão): a associação roda a nível de **aluno**, e só dá pra combinar
itens que estão na **mesma linha do mesmo arquivo** — arq4 só tem itens
Likert (QE_I27-I68), nada de renda/cotas/nota (arquivos embaralhados de
forma independente, cada um ordenado por uma variável diferente pra impedir
reidentificação). `CO_CURSO` é a única chave compartilhada entre arquivos.

## 2. Opções testadas

### Opção A — Itens diversos (1 por tema), sem desempenho

Troca os 3 itens do mesmo tema por 6 itens de temas diferentes:
`QE_I57` (professores), `QE_I61` (infraestrutura), `QE_I34` (formação),
`QE_I44` (oportunidades de iniciação científica), `QE_I30` e `QE_I56`
(mantidos do original).

- Resultado: 542 regras (vs. 7 do original) — mas o efeito-halo continua
  sendo a maior parte do sinal, só que agora **mais forte entre temas
  diferentes** (lift 2,6+) do que dentro do mesmo tema (lift 1,5-1,8 do
  original). Mesma natureza de achado (correlação entre percepções), só
  mais robusta.
- **Descartada isoladamente**: mais informativa que a produção original, mas
  ainda não liga nada a desempenho real — só confirma que a satisfação é
  generalizada entre temas.

### Opção B — Itens diversos + banda de desempenho do curso

Anexa a cada aluno a banda de desempenho do seu curso (tercis de `NT_GER`
médio, de arq3, via `CO_CURSO` — válido e compatível com LGPD: é uma
característica do curso, não um vínculo entre alunos de arquivos
diferentes).

- Nos limiares de produção (confiança 0,7): **zero regras** ligadas a
  desempenho — matematicamente impossível, porque nem a banda mais comum
  (`desempenho_alto`, 41,5% dos alunos) chega a 70% de confiança contra
  qualquer item sozinho.
- Com limiares bem mais permissivos (suporte 0,1, confiança 0,1, só para
  explorar): 291 regras ligadas a desempenho apareceram, com destaque pra
  `QE_I44` (oportunidades de iniciação científica, nível 6) → desempenho
  alto, lift até 1,40. Mas confiança de só 0,33-0,58 — **descartada como
  está**: limiar tão baixo não distingue sinal de ruído de busca exaustiva
  (foram testadas centenas de combinações de itens × níveis × limiares até
  achar isso).

### Varredura univariada — existe um item "especial" além de QE_I44?

Testados todos os ~40 itens Likert do arq4 (não só os 6 da opção B),
medindo o lift de cada um (nível 5 ou 6) contra desempenho alto/baixo:

- `QE_I44` (oportunidades de IC) foi de fato o mais forte (lift 1,185), mas
  **não é um caso isolado** — praticamente todos os itens (`QE_I43`
  extensão, `QE_I56`, `QE_I52`, `QE_I60`, `QE_I27`, `QE_I42`... e mais 15)
  mostram o mesmo padrão fraco-mas-consistente (lift 1,08-1,19) na mesma
  direção.
- **Conclusão**: o vínculo percepção→desempenho é real (confirmado de forma
  espalhada e consistente por ~40 itens independentes, não concentrado em
  1 item), mas **fraco** por item isolado. O ganho de lift maior (até 1,40)
  só aparece ao **combinar** 2+ itens — exatamente o que a análise de
  associação existe para achar.

### Busca de limiar ideal (suporte × confiança)

Varredura de suporte ∈ {0,03; 0,05; 0,08; 0,10} × confiança ∈ {0,3; 0,4;
0,5; 0,6; 0,7} nos 6 itens + desempenho:

| Suporte | Confiança | Regras c/ desempenho | Lift médio |
|---|---|---|---|
| 0,03 | 0,3 | 241 | 1,039 |
| 0,03 | 0,4 | 55 | 1,091 |
| **0,03** | **0,5** | **10** | **1,299** |
| 0,05 | 0,5 | 3 | 1,350 |
| qualquer | ≥0,6 | **0** | — |

**Confiança ≥0,6 é um teto rígido**: nenhuma regra ligada a desempenho
sobrevive, em nenhum suporte testado. Confiança 0,3 é muito permissiva
(lift médio quase 1,0 — ruído). **Suporte 0,03 / confiança 0,5** foi o
melhor equilíbrio: poucas regras, mas com lift médio mais alto de toda a
varredura.

### Validação por amostras independentes (pedida pelo usuário, essencial)

Antes de aceitar o "sweet spot" (suporte 0,03/confiança 0,5), a base de
alunos foi dividida em duas metades aleatórias independentes (~2328 e ~2329
alunos, `random_state=42`), rodando a mesma configuração em cada uma:

- Metade A encontrou 13 regras ligadas a desempenho, Metade B encontrou 9.
- **Só 6 se repetem nas duas** (46%) — quase metade do que aparece numa
  amostra inteira **não generaliza** pra uma amostra independente, confirmando
  que parte do resultado em 0,03/0,5 é artefato de amostra pequena (suporte
  0,03 ≈ 150-180 alunos por regra), não sinal real.
- As 6 que replicam têm lift consistente nas duas metades (1,23-1,49) e
  **5 das 6 envolvem `oportunidades_ic` nível 6**:
  ```
  oportunidades_ic_6 + professores_dominio_5    -> lift 1,27 / 1,33
  infra_salas_5 + oportunidades_ic_6            -> lift 1,35 / 1,35
  oportunidades_ic_6 + profs_disponibilidade_5  -> lift 1,32 / 1,49
  metodologia_inovadora_4 + oportunidades_ic_6  -> lift 1,38 / 1,43
  formacao_critica_5 + oportunidades_ic_6       -> lift 1,23 / 1,35
  professores_dominio_6 + profs_disponibilidade_5 -> lift 1,28 / 1,35
  ```

### Suporte mínimo de 0,6 — testado a pedido do usuário, estruturalmente impossível

- Mesmo a categoria mais comum da base (`oportunidades_ic_6`, "concordo
  totalmente") só aparece em 50,6% dos alunos — **nenhuma** categoria chega
  a 60% sozinha, então nenhuma regra (que exige suporte conjunto) pode
  existir nesse limiar.
- Testado binarizar os itens (concorda = níveis 4-6, discorda = 1-3): aí sim
  várias combinações passam de 0,6 de suporte, mas **nenhuma envolve
  desempenho** (mesmo binarizado, `desempenho_alto` continua em 41,5% —
  bem abaixo de 0,6) e as regras que sobram têm lift 1,03-1,06 — a
  binarização destruiu a distinção de nível (5 vs. 6) que era onde o sinal
  realmente estava.
- Testado também binarizar a banda de desempenho (`alto` 41,5% vs.
  `não_alto` 58,5%) — nem assim chega a 0,6. **Zero regras ligadas a
  desempenho em suporte 0,6, com qualquer binarização.** Descartada.

## 3. Decisão final e por que venceu

**Configuração adotada**: 6 itens diversos (`QE_I57`, `QE_I61`, `QE_I34`,
`QE_I44`, `QE_I30`, `QE_I56`) + banda de desempenho do curso, `suporte_
minimo=0.03`, `confianca_minima=0.5` — a única configuração que (a) permite
alguma regra ligada a desempenho existir matematicamente, e (b) foi
validada por repetição em duas amostras independentes, não só ajustada até
"parecer boa" numa amostra só.

**Salvaguarda adicionada**: com esses limiares, a base gera milhares de
regras (muitas permutações do mesmo padrão) — inviável publicar direto
(a tabela tinha 7 linhas antes). Adicionado filtro de simplicidade (máx. 3
itens por regra) e limite de publicação (`LIMITE_REGRAS_PUBLICADAS = 50`),
ordenado por lift. Resultado real publicado: 2417 regras totais → 377
simples → **50 publicadas**, das quais 4 envolvem desempenho (ancoradas em
`oportunidades_ic`/`professores_dominio`/`profs_disponibilidade`, nível 5,
com `desempenho_baixo`).

**Bug corrigido no caminho**: `multi_enade_modelo_associacao` tinha um
`try/except` que engolia qualquer exceção só imprimindo, sem propagar — o
mesmo padrão de falha silenciosa já corrigido em `upsert_supabase` (ver
EXPLORACAO_MODELO_REGRESSAO.md). Adicionado `raise e` para falhar de forma
visível.

### Pendências / limitações conhecidas

- A configuração ainda prioriza regras simples entre itens de percepção
  (efeito-halo) sobre as ligadas a desempenho, porque o halo tem lift maior
  — das 50 regras publicadas, só 4 envolvem desempenho. Se o objetivo for
  especificamente regras percepção→desempenho, seria necessário filtrar o
  consequente para só bandas de desempenho (reduz ainda mais a contagem).
- Suporte 0,03 corresponde a ~150-180 alunos por regra — ainda uma amostra
  pequena; nem todas as 50 regras publicadas foram individualmente
  validadas por repetição (só a validação por amostra foi feita para o
  conjunto de 10 regras do "sweet spot" original, não para as 50 atuais).
- `tbl_multi_enade_associacao` não precisou de nenhuma alteração de schema
  (diferente da regressão) — a tabela guarda `antecedents`/`consequents`
  como texto genérico, então o conteúdo pode mudar livremente sem exigir
  `ALTER TABLE`.
