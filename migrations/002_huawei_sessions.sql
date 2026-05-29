-- 002: Tabela para persistir storage_state das sessoes FusionSolar.
-- Necessario para reuso entre runs do GitHub Actions (sem filesystem persistente).
-- Storage_state contem cookies + localStorage da sessao Playwright.

CREATE TABLE IF NOT EXISTS reports.huawei_sessions (
    username       TEXT PRIMARY KEY,
    storage_state  JSONB NOT NULL,
    last_login_at  TIMESTAMPTZ DEFAULT NOW(),
    last_used_at   TIMESTAMPTZ DEFAULT NOW(),
    -- Marca se a sessao está válida (usado pelo health check)
    is_valid       BOOLEAN DEFAULT TRUE,
    failure_count  INTEGER DEFAULT 0,
    notes          TEXT
);

COMMENT ON TABLE reports.huawei_sessions IS
'Backup das sessoes FusionSolar (cookies + localStorage) para reuso entre runs do ETL.';
