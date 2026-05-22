-- ════════════════════════════════════════════════════════════════════════════
-- Migration 001: Schema "reports" para painel AEVO
-- ════════════════════════════════════════════════════════════════════════════
-- Objetivo: persistir dados que hoje sao recarregados da API ISC a cada uso.
-- Estrategia: schema separado ("reports") para nao misturar com tabelas
-- do sistema principal (public.*). Idempotente via UPSERT em (plant_id, periodo).
-- Aplicacao: rodar UMA vez no Postgres Railway antes de subir o ETL.
-- ════════════════════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS reports;

-- ──────────────────────────────────────────────────────────────────────────
-- 1) Energia diaria por inversor (granularidade fina)
-- ──────────────────────────────────────────────────────────────────────────
-- Origem: isc_energia_mensal (p2 fim do dia, delta vs dia anterior)
-- Volume estimado: 140 usinas × 30 dias × ~15 inversores = ~63k linhas/mes
-- Crescimento: ~750k linhas/ano. Cabe sem problema.
CREATE TABLE IF NOT EXISTS reports.energy_daily (
    plant_id        BIGINT       NOT NULL,
    dia             DATE         NOT NULL,
    inversor        VARCHAR(64)  NOT NULL,
    modelo          VARCHAR(32),
    energia_kwh     NUMERIC(12,2) NOT NULL DEFAULT 0,
    fonte           VARCHAR(32)  NOT NULL,  -- 'iSolarCloud' | 'Banco AEVO'
    fetched_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plant_id, dia, inversor)
);
-- Indice (plant_id, dia) ja eh suficiente para queries por usina e por mes
-- (range scan em (plant_id, dia BETWEEN ...) eh otimo)
CREATE INDEX IF NOT EXISTS idx_energy_daily_plant_dia
    ON reports.energy_daily (plant_id, dia);
CREATE INDEX IF NOT EXISTS idx_energy_daily_dia
    ON reports.energy_daily (dia);

-- ──────────────────────────────────────────────────────────────────────────
-- 2) Paradas detectadas (parciais ou via 5-estados)
-- ──────────────────────────────────────────────────────────────────────────
-- Origem: isc_5estados_mensal (Tier 1) ou load_disp_operacao (Tier 2)
-- Volume estimado: variavel; ~50-300 por usina/mes. ~600k/ano para 140 usinas.
CREATE TABLE IF NOT EXISTS reports.paradas (
    id              BIGSERIAL    PRIMARY KEY,
    plant_id        BIGINT       NOT NULL,
    ano             SMALLINT     NOT NULL,
    mes             SMALLINT     NOT NULL,
    inversor        VARCHAR(64)  NOT NULL,
    inicio          TIMESTAMP    NOT NULL,
    fim             TIMESTAMP,
    duracao_h       NUMERIC(8,4) NOT NULL,
    tipo            VARCHAR(32)  NOT NULL,   -- 'Parada Parcial (sensor)' | 'Parada'
    causa           VARCHAR(64),             -- 'Sobretensao CA', etc. NULL em Tier 2
    responsavel     VARCHAR(32),             -- 'Concessionaria' | 'Equipamento / O&M' | NULL
    fetched_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paradas_plant_periodo
    ON reports.paradas (plant_id, ano, mes);
CREATE INDEX IF NOT EXISTS idx_paradas_inversor
    ON reports.paradas (plant_id, inversor);
-- Sem PK natural (uma parada pode reiniciar com dados levemente diferentes).
-- O ETL faz DELETE+INSERT por (plant_id, ano, mes) ao popular — comportamento
-- idempotente garantido sem precisar de chave composta complexa.

-- ──────────────────────────────────────────────────────────────────────────
-- 3) KPIs mensais (snapshot pronto para o painel)
-- ──────────────────────────────────────────────────────────────────────────
-- Origem: calc_kpis + kpis_5est. UM registro por (plant_id, ano, mes).
-- Esta eh a tabela MAIS consultada pelo painel.
CREATE TABLE IF NOT EXISTS reports.kpis_mensal (
    plant_id        BIGINT       NOT NULL,
    ano             SMALLINT     NOT NULL,
    mes             SMALLINT     NOT NULL,
    energia_real_kwh    NUMERIC(14,2),
    energia_esperada_kwh NUMERIC(14,2),  -- e_grid PVsyst
    atingimento_pct     NUMERIC(6,2),
    pr_real             NUMERIC(6,4),
    pr_esperado         NUMERIC(6,4),
    poa_kwh_m2          NUMERIC(8,2),
    poa_fonte           VARCHAR(32),     -- 'Manual' | 'Banco' | 'PVsyst' | 'GHI×fator'
    disp_geracao_pct    NUMERIC(6,2),
    disp_operacao_pct   NUMERIC(6,2),
    cobertura_dias      NUMERIC(6,2),
    dias_com_dado       SMALLINT,
    tier                SMALLINT,         -- 1 ou 2
    pct_ger_pure        NUMERIC(6,2),     -- so Tier 1
    pct_irr             NUMERIC(6,2),
    pct_conc            NUMERIC(6,2),
    pct_om              NUMERIC(6,2),
    total_eventos       INT,
    total_horas_off     NUMERIC(10,2),
    em_aberto           INT,
    receita_estimada_brl NUMERIC(14,2),   -- se tarifa cadastrada
    is_closed           BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = mes fechado, dado imutavel
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plant_id, ano, mes)
);
CREATE INDEX IF NOT EXISTS idx_kpis_periodo ON reports.kpis_mensal (ano, mes);

-- ──────────────────────────────────────────────────────────────────────────
-- 4) Disponibilidade dia × inversor (para heatmap e analises operacionais)
-- ──────────────────────────────────────────────────────────────────────────
-- Origem: disp_dia_inv do isc_5estados_mensal (so Tier 1)
-- Volume estimado: 140 × 30 × 15 = ~63k linhas/mes
CREATE TABLE IF NOT EXISTS reports.disp_dia_inversor (
    plant_id        BIGINT       NOT NULL,
    ano             SMALLINT     NOT NULL,
    mes             SMALLINT     NOT NULL,
    dia             SMALLINT     NOT NULL,
    inversor        VARCHAR(64)  NOT NULL,
    disp_pct        NUMERIC(5,1) NOT NULL,
    fetched_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plant_id, ano, mes, dia, inversor)
);
CREATE INDEX IF NOT EXISTS idx_disp_periodo
    ON reports.disp_dia_inversor (plant_id, ano, mes);

-- ──────────────────────────────────────────────────────────────────────────
-- 5) Log de execucoes do ETL (auditoria + diagnostico)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports.fetch_log (
    id              BIGSERIAL    PRIMARY KEY,
    plant_id        BIGINT       NOT NULL,
    ano             SMALLINT     NOT NULL,
    mes             SMALLINT     NOT NULL,
    source          VARCHAR(32)  NOT NULL,   -- 'iSolarCloud' | 'Banco AEVO' | 'mixed'
    status          VARCHAR(16)  NOT NULL,   -- 'OK' | 'PARTIAL' | 'FAIL' | 'SKIP'
    rows_energy     INT,
    rows_paradas    INT,
    rows_disp       INT,
    duration_sec    NUMERIC(8,2),
    error_msg       TEXT,
    triggered_by    VARCHAR(32),             -- 'cron' | 'manual' | 'backfill'
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fetchlog_plant_periodo
    ON reports.fetch_log (plant_id, ano, mes, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_fetchlog_status
    ON reports.fetch_log (status, started_at DESC) WHERE status <> 'OK';

-- ──────────────────────────────────────────────────────────────────────────
-- 6) Usuarios do app (auth interna AEVO)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports.users (
    username        VARCHAR(64)  PRIMARY KEY,
    nome            VARCHAR(128) NOT NULL,
    email           VARCHAR(128) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,    -- bcrypt
    role            VARCHAR(16)  NOT NULL DEFAULT 'user',  -- 'admin' | 'user' | 'viewer'
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

-- ──────────────────────────────────────────────────────────────────────────
-- 7) Cache de tarifa / observacoes por usina×mes (substitui o input manual)
-- ──────────────────────────────────────────────────────────────────────────
-- Hoje a tarifa e obs sao digitadas no Streamlit a cada geracao.
-- Persistir aqui permite que o painel use o valor mais recente.
CREATE TABLE IF NOT EXISTS reports.plant_config_mensal (
    plant_id        BIGINT       NOT NULL,
    ano             SMALLINT     NOT NULL,
    mes             SMALLINT     NOT NULL,
    tarifa_brl_kwh  NUMERIC(8,4),
    poa_manual      NUMERIC(8,2),
    observacoes     TEXT,
    updated_by      VARCHAR(64),  -- username de quem editou
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plant_id, ano, mes)
);

-- ════════════════════════════════════════════════════════════════════════════
-- Politicas de uso (referencia):
--
-- IDEMPOTENCIA do ETL:
-- - energy_daily, kpis_mensal, disp_dia_inversor: UPSERT por PK natural
-- - paradas: DELETE WHERE plant_id=X AND ano=Y AND mes=Z; INSERT em massa
--
-- MES FECHADO vs ABERTO:
-- - kpis_mensal.is_closed = TRUE quando o mes ja passou
-- - ETL pula recompute de meses fechados (a menos que --force)
-- - Reduz drasticamente o tempo do cron diario
--
-- BACKFILL:
-- - Rodar ETL com --backfill iterando (ano, mes) historico
-- - Aproveita cache em disco existente onde possivel
--
-- USUARIOS:
-- - Inicialmente popula manualmente via INSERT
-- - Streamlit-authenticator le desta tabela
-- - Admin pode adicionar usuario via UI (Fase futura)
-- ════════════════════════════════════════════════════════════════════════════

-- Permissoes (descomentar quando rodar como superuser):
-- GRANT USAGE ON SCHEMA reports TO powerbi_readonly_user;
-- GRANT SELECT ON ALL TABLES IN SCHEMA reports TO powerbi_readonly_user;
-- GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA reports TO <etl_user>;
