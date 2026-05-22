"""Conecta no Supabase, verifica schema 'reports', aplica migration se faltar."""
import sys, io, os, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Le credenciais do .env (sem dependencia de python-dotenv)
def load_env(path):
    env = {}
    if not os.path.exists(path): return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = load_env(os.path.join(HERE, "..", ".env"))
SQL_FILE = os.path.join(HERE, "001_create_reports_schema.sql")

# Project ref extraido do host: db.{REF}.supabase.co
PROJECT_REF = ENV["SUPABASE_HOST"].split(".")[1]

REGION = ENV.get("SUPABASE_REGION", "us-east-1")
ATTEMPTS = [
    ("direct (5432)",             ENV["SUPABASE_HOST"], 5432, ENV["SUPABASE_USER"]),
    (f"pooler {REGION} session",  f"aws-0-{REGION}.pooler.supabase.com", 5432, f"postgres.{PROJECT_REF}"),
    (f"pooler {REGION} trans",    f"aws-0-{REGION}.pooler.supabase.com", 6543, f"postgres.{PROJECT_REF}"),
    (f"pooler {REGION} v1 sess",  f"aws-1-{REGION}.pooler.supabase.com", 5432, f"postgres.{PROJECT_REF}"),
]

conn = None
for label, host, port, user in ATTEMPTS:
    print(f"Tentando {label}: {host}:{port} user={user}")
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=ENV["SUPABASE_DB"],
                                user=user, password=ENV["SUPABASE_PASSWORD"],
                                sslmode="require", connect_timeout=15)
        print(f"  [OK] Conectado via {label}")
        # Salva config bem-sucedida para reuso
        SUCCESS = (host, port, user)
        break
    except Exception as e:
        print(f"  [falhou] {type(e).__name__}: {e}")
if conn is None:
    print("\n[ERRO] Nenhum endpoint funcionou. Confira senha e regiao do projeto.")
    sys.exit(2)

# Verifica schema/tabelas existentes
with conn.cursor() as cur:
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='reports' ORDER BY table_name
    """)
    existing = [r[0] for r in cur.fetchall()]

print(f"\nTabelas em 'reports.*': {len(existing)} encontradas")
for t in existing: print(f"  reports.{t}")

EXPECTED = ["disp_dia_inversor","energy_daily","fetch_log","kpis_mensal",
            "paradas","plant_config_mensal","users"]

missing = [t for t in EXPECTED if t not in existing]
if not missing:
    print("\n[OK] Schema 'reports' ja esta completo. Nada a fazer.")
    conn.close()
    sys.exit(0)

print(f"\nFaltam {len(missing)} tabela(s): {missing}")
print(f"Aplicando migration {os.path.basename(SQL_FILE)}...")
with open(SQL_FILE, "r", encoding="utf-8") as f:
    sql_text = f.read()

# Fecha conn anterior e abre uma fresca para aplicar DDL
conn.close()
host, port, user = SUCCESS
conn = psycopg2.connect(host=host, port=port, dbname=ENV["SUPABASE_DB"],
                        user=user, password=ENV["SUPABASE_PASSWORD"],
                        sslmode="require", connect_timeout=15)
conn.autocommit = False
try:
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()
    print("[OK] Migration aplicada.")
except Exception as e:
    conn.rollback()
    print(f"[ERRO] {type(e).__name__}: {e}")
    conn.close()
    sys.exit(1)

# Verifica novamente
with conn.cursor() as cur:
    cur.execute("""
        SELECT table_name,
               (SELECT COUNT(*) FROM information_schema.columns c
                WHERE c.table_schema='reports' AND c.table_name=t.table_name) AS cols
        FROM information_schema.tables t
        WHERE table_schema='reports' ORDER BY table_name
    """)
    rows = cur.fetchall()

print(f"\nVerificacao final: {len(rows)} tabelas em 'reports.*'")
for name, cols in rows:
    print(f"  reports.{name:<25} {cols} colunas")
conn.close()
