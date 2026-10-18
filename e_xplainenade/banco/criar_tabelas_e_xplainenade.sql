-- Tabelas próprias do E-XplainENADE (gerado por e_xplainenade/banco/carregar_tabelas.py).
-- Rodar no SQL Editor do Supabase Studio. Colunas em text (mesma convenção das
-- tbl_arqN_2021 — modules/supabase_client.py normaliza tudo para string na leitura).
-- RLS ligado e sem política: a chave pública não lê nem escreve; o backend usa a
-- chave secreta, que ignora RLS (mesma configuração das tbl_educluster_*).

create table if not exists public.tbl_e_xplainenade_arq1_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "CO_GRUPO" text,
    "CO_REGIAO_CURSO" text,
    "CO_CATEGAD" text
);
alter table public.tbl_e_xplainenade_arq1_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq2_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "CO_TURNO_GRADUACAO" text
);
alter table public.tbl_e_xplainenade_arq2_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq3_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "NT_GER" text,
    "NT_FG" text,
    "NT_CE" text,
    "TP_PRES" text
);
alter table public.tbl_e_xplainenade_arq3_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq5_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "TP_SEXO" text
);
alter table public.tbl_e_xplainenade_arq5_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq6_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "NU_IDADE" text
);
alter table public.tbl_e_xplainenade_arq6_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq10_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I04" text
);
alter table public.tbl_e_xplainenade_arq10_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq11_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I05" text
);
alter table public.tbl_e_xplainenade_arq11_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq14_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I08" text
);
alter table public.tbl_e_xplainenade_arq14_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq16_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I10" text
);
alter table public.tbl_e_xplainenade_arq16_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq21_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I15" text
);
alter table public.tbl_e_xplainenade_arq21_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq23_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I17" text
);
alter table public.tbl_e_xplainenade_arq23_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq27_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I21" text
);
alter table public.tbl_e_xplainenade_arq27_2021 enable row level security;

create table if not exists public.tbl_e_xplainenade_arq29_2021 (
    "id" bigint primary key,
    "CO_CURSO" text not null,
    "QE_I23" text
);
alter table public.tbl_e_xplainenade_arq29_2021 enable row level security;
