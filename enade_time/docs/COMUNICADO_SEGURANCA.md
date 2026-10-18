# Comunicado de segurança — projeto Supabase `EnadeX` (`yghryywuxfwzvfjknpgk`)

**De:** Lucas Eduardo Tavares Costa (ENADE-Time Distribuído)
**Para:** Paulo (líder do ecossistema EnadeX), com cópia aos demais integrantes
**Data:** 2026-09-01
**Urgência:** esta semana, independente do PR do `enade_time/`

Este comunicado tem **dois itens**, ambos verificados diretamente no projeto em
2026-09-01 (via advisors do Supabase e consulta ao catálogo do banco). Não
altero nada fora do meu subprojeto; as ações abaixo são suas ou de quem
administra o projeto.

---

## 1. A RPC `truncar_tabela` pode ser executada por qualquer pessoa com a anon key

**O que existe hoje**

```sql
CREATE OR REPLACE FUNCTION public.truncar_tabela(nome_tabela text)
 RETURNS void LANGUAGE plpgsql SECURITY DEFINER
AS $$ BEGIN
  EXECUTE format('TRUNCATE TABLE public.%I RESTART IDENTITY CASCADE;', nome_tabela);
END; $$;
```

- `SECURITY DEFINER`: roda com os privilégios do dono (superusuário do projeto),
  ignorando RLS e grants de quem chama.
- `EXECUTE` está concedido a `anon` e `authenticated` (default do schema
  `public`), então ela está exposta em `POST /rest/v1/rpc/truncar_tabela`
  **para a anon key** — que é pública por definição (vai para o navegador em
  qualquer frontend).
- `search_path` mutável (o advisor `function_search_path_mutable` aponta isso).
- Os advisors do próprio Supabase marcam os dois problemas como **WARN**:
  `anon_security_definer_function_executable` e
  `authenticated_security_definer_function_executable`.

**Consequência prática:** qualquer pessoa com a anon key consegue esvaziar
**qualquer tabela** do schema `public` — `tbl_arq*_2021`,
`tbl_multi_enade_*`, `enade_time_distribuido`, dims — com um único POST, e o
`CASCADE` leva junto o que depender da tabela.

**Correção (3 comandos, sem impacto no uso atual)** — o `util_db.truncar_tabela_supabase`
continua funcionando, porque quem o chama usa a chave de serviço:

```sql
REVOKE EXECUTE ON FUNCTION public.truncar_tabela(text) FROM anon, authenticated, public;
GRANT  EXECUTE ON FUNCTION public.truncar_tabela(text) TO service_role;
ALTER  FUNCTION public.truncar_tabela(text) SET search_path = public;
```

Depois de aplicar, os dois WARN somem dos advisors.

---

## 2. A `SUPABASE_KEY` compartilhada é uma chave de serviço e foi exposta

**O que aconteceu:** a `SUPABASE_KEY` que circula no `.env` do grupo é uma
chave `sb_secret_…` (formato novo, equivalente ao antigo `service_role`, com
**BYPASSRLS**). Ela foi exposta fora do repositório. A rotação é individual e
já foi/está sendo feita: *Settings → API Keys → New secret key* → distribuir →
**apagar a comprometida**. Não afeta o JWT secret nem as chaves `anon` /
`sb_publishable_`.

**Por que isso importa além do incidente:** o catálogo mostra que **17 das 25
tabelas** do projeto (todas as `tbl_arq*_2021` e as `tbl_multi_enade_*`) têm
RLS ligado **sem nenhuma policy**. Com a anon key elas são invisíveis; elas só
funcionam hoje porque os scripts usam a chave de serviço, que ignora RLS. Ou
seja: **todo o ecossistema está rodando com a chave mais poderosa do projeto
em `.env` de máquinas de alunos e, possivelmente, em deploys (Streamlit).**
Qualquer vazamento dessa chave é acesso total de leitura e escrita a tudo.

**Modelo proposto (mínimo, compatível com o `util_db.py` atual):**

| Uso | Chave | Onde fica |
|---|---|---|
| Leitura pelas APIs / frontends / notebooks | `sb_publishable_…` (ou a `anon` legacy) | pode ir para `.env` de qualquer integrante |
| Escrita por scripts de ETL / treino (`upsert_supabase`, `truncar_tabela_supabase`) | `sb_secret_…` | **só** na máquina de quem roda a carga; nunca em deploy, nunca no `.env` compartilhado |

Para a leitura funcionar com a chave publicável, cada tabela precisa de uma
policy de `SELECT` — o mesmo padrão que já está nas 8 tabelas do ENADE-Time
(`leitura publica`, migração `enable_rls_leitura_publica_enade`):

```sql
CREATE POLICY "leitura publica" ON public.tbl_arq3_2021
  FOR SELECT TO anon, authenticated USING (true);
-- repetir para as demais tbl_arq*_2021 e tbl_multi_enade_*
```

As funções de `util/util_db.py` não mudam: `credenciais_banco()` continua
lendo `SUPABASE_URL`/`SUPABASE_KEY`; o que muda é **qual** chave cada pessoa
coloca no seu `.env`.

---

## Evidências (para conferência)

- Advisors de segurança do projeto em 2026-09-01: 17 × `rls_enabled_no_policy`,
  1 × `function_search_path_mutable`, 1 × `anon_security_definer_function_executable`,
  1 × `authenticated_security_definer_function_executable`.
- `pg_get_functiondef('public.truncar_tabela(text)')` — corpo acima.
- `information_schema.role_table_grants`: `anon` e `authenticated` com
  `DELETE, INSERT, TRUNCATE, UPDATE` em todas as tabelas de `public` (default
  do Supabase; só o RLS impede o uso).

Fico à disposição para aplicar os comandos junto, se preferir fazer em conjunto.
