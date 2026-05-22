# Painel AEVO19 — Relatorios e Portfolio O&M

Sistema interno da AEVO Solar para geracao de relatorios mensais e painel de portfolio das usinas fotovoltaicas.

## Arquitetura

```
+-----------------+       +------------------+       +------------------+
|  Postgres AEVO  |  READ |   ETL diario     | WRITE |   Supabase       |
|  (railway)      | <---- |  cron 02:00 BRT  | ----> |  reports.*       |
+-----------------+       +------------------+       +------------------+
                                                              |
                                                              | READ
                                                              v
                                                     +------------------+
                                                     |  Streamlit App   |
                                                     |  (Railway)       |
                                                     +------------------+
                                                              ^
                                                              | login bcrypt
                                                              |
                                                     [equipe AEVO]
```

## Componentes

- `app.py` — Streamlit (gerador de relatorios + painel)
- `auth.py` — Login (bcrypt, tabela reports.users)
- `etl/etl_daily.py` — Pipeline AEVO→Supabase
- `etl/cron_runner.py` — Entrypoint do servico cron
- `migrations/001_create_reports_schema.sql` — Schema do Supabase

## Setup local

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `playwright install chromium`
4. Copie `.env.example` como `.env` e preencha credenciais
5. `streamlit run app.py`

## Deploy

Ver `DEPLOY.md`.

## Gerenciar usuarios

```
python auth.py create <username> <email> "<Nome Completo>" [admin|user|viewer]
python auth.py list
python auth.py setpw <username>
python auth.py disable <username>
```

## ETL manual

```
python etl/etl_daily.py --plant all --ano 2026 --mes 4
python etl/etl_daily.py --plant 479 --ano 2026 --mes 3 --force
```
