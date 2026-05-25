"""
ETL diario: extrai dados (AEVO+ISC) e persiste em Supabase reports.*
Uso:
  python etl_daily.py --plant <id|all> --ano YYYY --mes MM [--force] [--limit N]
  python etl_daily.py --backfill --ano-ini 2024 --mes-ini 1 --ano-fim 2026 --mes-fim 4 [--plant <id>]
  python etl_daily.py --current   (sinonimo: --ano <ano-atual> --mes <mes-atual> --all)
"""
import sys, io, os, argparse, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# ── Stub Streamlit (necessario p/ importar app.py) ────────────────────────
class _FakeCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **kw): return self
    def __getattr__(self, name): return self
    def __iter__(self): return iter([_FakeCtx() for _ in range(20)])

class _FakeSession(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v

class _FakeSt:
    def __init__(self):
        self.session_state = _FakeSession()
        self.sidebar = _FakeCtx()
    def cache_data(self, *a, **kw):
        if a and callable(a[0]): return a[0]
        return lambda f: f
    cache_resource = cache_data
    def set_page_config(self, *a, **kw): pass
    def stop(self): pass  # nao parar (auth.ensure_login chama isso no import)
    def columns(self, spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return tuple(_FakeCtx() for _ in range(n))
    def tabs(self, names, **kw): return tuple(_FakeCtx() for _ in names)
    def selectbox(self, label, options, *a, **kw):
        try:
            opts = list(options); return opts[kw.get("index", 0)] if opts else None
        except: return None
    def multiselect(self, *a, **kw): return []
    def number_input(self, *a, **kw): return kw.get("value", 0.0)
    def text_input(self, *a, **kw): return kw.get("value", "")
    def text_area(self, *a, **kw): return kw.get("value", "")
    def checkbox(self, *a, **kw): return False
    def button(self, *a, **kw): return False
    def data_editor(self, df, **kw): return df
    def expander(self, *a, **kw): return _FakeCtx()
    def progress(self, *a, **kw): return _FakeCtx()
    def __getattr__(self, name):
        def f(*a, **kw): return _FakeCtx()
        return f

sys.modules["streamlit"] = _FakeSt()

import app   # noqa: E402
import psycopg2  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402
import pandas as pd  # noqa: E402
import calendar  # noqa: E402

# ── Carrega .env ─────────────────────────────────────────────────────────
def load_env(path):
    """Carrega vars de .env e tambem expoe via os.environ (fallback).
    Prioridade: os.environ > .env"""
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    # Sobrescreve/adiciona com os.environ (Github Actions, Railway, etc)
    for k in ("SUPABASE_HOST","SUPABASE_PORT","SUPABASE_DB","SUPABASE_USER",
              "SUPABASE_PASSWORD","SUPABASE_REGION",
              "AEVO_HOST","AEVO_PORT","AEVO_DB","AEVO_USER","AEVO_PASSWORD",
              "ISC_USER","ISC_PASS","ISC_APPKEY","ISC_SECRET"):
        if os.environ.get(k): env[k] = os.environ[k]
    return env

ENV = load_env(os.path.join(ROOT, ".env"))
if "SUPABASE_HOST" not in ENV:
    print("ERRO: SUPABASE_HOST nao definido (nem em .env nem em os.environ)")
    sys.exit(2)
REGION = ENV.get("SUPABASE_REGION", "us-east-1")
PROJECT_REF = ENV["SUPABASE_HOST"].split(".")[1]
SB_CONN = dict(
    host=f"aws-1-{REGION}.pooler.supabase.com",
    port=5432,
    dbname=ENV.get("SUPABASE_DB", "postgres"),
    user=f"postgres.{PROJECT_REF}",
    password=ENV["SUPABASE_PASSWORD"],
    sslmode="require",
)

def sb_connect():
    return psycopg2.connect(**SB_CONN, connect_timeout=15)


# ── Persistencia ──────────────────────────────────────────────────────────
def upsert_energy_daily(conn, pid, df_daily, fonte):
    if df_daily.empty: return 0
    rows = []
    for _, r in df_daily.iterrows():
        dia = r["dia"]
        if hasattr(dia, "strftime"): dia_str = dia.strftime("%Y-%m-%d")
        else:
            s = str(dia)
            dia_str = s if "-" in s else f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        rows.append((pid, dia_str, str(r["inversor"]), str(r.get("modelo","") or "")[:32],
                     float(r["energia_kwh"]), fonte))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO reports.energy_daily (plant_id, dia, inversor, modelo, energia_kwh, fonte)
            VALUES %s
            ON CONFLICT (plant_id, dia, inversor) DO UPDATE SET
                modelo=EXCLUDED.modelo,
                energia_kwh=EXCLUDED.energia_kwh,
                fonte=EXCLUDED.fonte,
                fetched_at=NOW()
        """, rows)
    return len(rows)


def replace_paradas(conn, pid, ano, mes, df_paradas):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM reports.paradas WHERE plant_id=%s AND ano=%s AND mes=%s",
                    (pid, ano, mes))
    if df_paradas.empty: return 0
    rows = []
    for _, r in df_paradas.iterrows():
        # inicio/fim sao strings "DD/MM/YYYY HH:MM" -> converter
        def parse_dt(s):
            if not s: return None
            s = str(s)
            try:
                from datetime import datetime
                return datetime.strptime(s[:16], "%d/%m/%Y %H:%M")
            except: return None
        ini = parse_dt(r.get("inicio"))
        fim = parse_dt(r.get("fim"))
        rows.append((pid, ano, mes, str(r["inversor"]), ini, fim,
                     float(r["duracao_h"]), str(r.get("tipo","Parada"))[:32],
                     (str(r.get("causa")) if r.get("causa") is not None else None),
                     (str(r.get("responsavel")) if r.get("responsavel") is not None else None)))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO reports.paradas
                (plant_id, ano, mes, inversor, inicio, fim, duracao_h, tipo, causa, responsavel)
            VALUES %s
        """, rows)
    return len(rows)


def upsert_disp(conn, pid, ano, mes, disp_dia_inv):
    if not disp_dia_inv: return 0
    rows = []
    for dia, dia_dict in disp_dia_inv.items():
        for inv, pct in dia_dict.items():
            rows.append((pid, ano, mes, int(dia), str(inv), float(pct)))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO reports.disp_dia_inversor
                (plant_id, ano, mes, dia, inversor, disp_pct)
            VALUES %s
            ON CONFLICT (plant_id, ano, mes, dia, inversor) DO UPDATE SET
                disp_pct=EXCLUDED.disp_pct,
                fetched_at=NOW()
        """, rows)
    return len(rows)


def upsert_kpis(conn, pid, ano, mes, data, total_eventos, total_horas_off, em_aberto, is_closed):
    kpis = data.get("kpis", {})
    pvsyst = data.get("pvsyst", {})
    kpis5 = data.get("kpis_5est") or {}
    er = kpis.get("energia_real", 0)
    ee = kpis.get("ee", 0)
    poa = data.get("poa", 0)
    row = (
        pid, ano, mes,
        float(er) if er else None,
        float(ee) if ee else None,
        float(kpis.get("at", 0)) if ee else None,
        float(kpis.get("pr_real", 0) or 0) or None,
        float(kpis.get("pr_e", 0) or 0) or None,
        float(poa) if poa else None,
        str(data.get("fonte_poa") or ""),
        float(kpis5.get("pct_geracao") or 0) or None,
        float(data.get("disp_op_media") or 0) or None,
        float(kpis.get("cob_pct") or 0) or None,
        int(kpis.get("dias_com_dado", 0) or 0),
        int(kpis5.get("tier") or 2),
        float(kpis5.get("pct_ger_pure") or 0) or None,
        float(kpis5.get("pct_irr") or 0) or None,
        float(kpis5.get("pct_conc") or 0) or None,
        float(kpis5.get("pct_om") or 0) or None,
        int(total_eventos or 0),
        float(total_horas_off or 0),
        int(em_aberto or 0),
        None,  # receita: calcular depois com tarifa do plant_config_mensal
        bool(is_closed),
    )
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO reports.kpis_mensal
              (plant_id, ano, mes, energia_real_kwh, energia_esperada_kwh, atingimento_pct,
               pr_real, pr_esperado, poa_kwh_m2, poa_fonte,
               disp_geracao_pct, disp_operacao_pct, cobertura_dias, dias_com_dado, tier,
               pct_ger_pure, pct_irr, pct_conc, pct_om,
               total_eventos, total_horas_off, em_aberto, receita_estimada_brl, is_closed)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (plant_id, ano, mes) DO UPDATE SET
              energia_real_kwh=EXCLUDED.energia_real_kwh,
              energia_esperada_kwh=EXCLUDED.energia_esperada_kwh,
              atingimento_pct=EXCLUDED.atingimento_pct,
              pr_real=EXCLUDED.pr_real, pr_esperado=EXCLUDED.pr_esperado,
              poa_kwh_m2=EXCLUDED.poa_kwh_m2, poa_fonte=EXCLUDED.poa_fonte,
              disp_geracao_pct=EXCLUDED.disp_geracao_pct,
              disp_operacao_pct=EXCLUDED.disp_operacao_pct,
              cobertura_dias=EXCLUDED.cobertura_dias,
              dias_com_dado=EXCLUDED.dias_com_dado,
              tier=EXCLUDED.tier,
              pct_ger_pure=EXCLUDED.pct_ger_pure, pct_irr=EXCLUDED.pct_irr,
              pct_conc=EXCLUDED.pct_conc, pct_om=EXCLUDED.pct_om,
              total_eventos=EXCLUDED.total_eventos,
              total_horas_off=EXCLUDED.total_horas_off,
              em_aberto=EXCLUDED.em_aberto,
              is_closed=EXCLUDED.is_closed,
              fetched_at=NOW()
        """, row)


def log_fetch(conn, pid, ano, mes, source, status, rows_e, rows_p, rows_d,
              duration, err, triggered_by):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO reports.fetch_log
              (plant_id, ano, mes, source, status, rows_energy, rows_paradas, rows_disp,
               duration_sec, error_msg, triggered_by, finished_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
        """, (pid, ano, mes, source, status, rows_e, rows_p, rows_d,
              duration, err, triggered_by))


# ── Orquestracao ──────────────────────────────────────────────────────────
def is_month_closed(ano, mes):
    from datetime import datetime
    n = datetime.now()
    return (ano, mes) < (n.year, n.month)


def already_done(conn, pid, ano, mes):
    """Retorna True se ja existe kpis_mensal com is_closed=TRUE."""
    with conn.cursor() as cur:
        cur.execute("SELECT is_closed FROM reports.kpis_mensal WHERE plant_id=%s AND ano=%s AND mes=%s",
                    (pid, ano, mes))
        row = cur.fetchone()
        return bool(row and row[0])


def processar_usina(conn, pid, ano, mes, triggered_by="manual", force=False):
    t0 = time.time()
    if not force and already_done(conn, pid, ano, mes):
        return ("SKIP", "ja persistido (is_closed=TRUE)", 0, 0, 0)
    # Pula plantas sem mapping ISC (sem fonte de dados acessivel hoje)
    if pid not in app.ISC_MAP:
        log_fetch(conn, pid, ano, mes, "n/a", "SKIP", 0, 0, 0,
                  time.time()-t0, "sem ISC mapping", triggered_by)
        conn.commit()
        return ("SKIP", "sem ISC mapping", 0, 0, 0)
    # Timeout por planta para evitar travamento em chamadas ISC lentas
    import threading
    result_box = {"data": None, "error": None}
    def _coletar():
        try: result_box["data"] = app.coletar_dados_usina(pid, ano, mes)
        except Exception as e: result_box["error"] = e
    th = threading.Thread(target=_coletar, daemon=True)
    th.start()
    th.join(timeout=300)  # 5 min por planta (api ISC pode demorar muito)
    if th.is_alive():
        duration = time.time() - t0
        log_fetch(conn, pid, ano, mes, "n/a", "FAIL", 0, 0, 0, duration,
                  "timeout 120s na coleta", triggered_by)
        conn.commit()
        return ("FAIL", "timeout 120s", 0, 0, 0)
    if result_box["error"]:
        duration = time.time() - t0
        log_fetch(conn, pid, ano, mes, "n/a", "FAIL", 0, 0, 0, duration,
                  str(result_box["error"])[:200], triggered_by)
        conn.commit()
        return ("FAIL", str(result_box["error"])[:200], 0, 0, 0)
    try:
        data = result_box["data"]
        if "error" in data:
            duration = time.time() - t0
            log_fetch(conn, pid, ano, mes, "n/a", "FAIL", 0, 0, 0, duration, data["error"], triggered_by)
            conn.commit()
            return ("FAIL", data["error"], 0, 0, 0)

        fonte = data.get("fonte_energia") or "Banco AEVO"
        rows_e = upsert_energy_daily(conn, pid, data["df_daily"], fonte)
        rows_p = replace_paradas(conn, pid, ano, mes, data["df_paradas"])
        rows_d = upsert_disp(conn, pid, ano, mes, data.get("disp_dia_inv"))

        # KPIs agregados
        total_h = float(data["df_paradas"]["duracao_h"].sum()) if not data["df_paradas"].empty else 0.0
        n_ev = len(data["df_paradas"]) + len(data["df_al"])
        em_aberto = 0
        if not data["df_al"].empty and "status" in data["df_al"].columns:
            em_aberto = int((data["df_al"]["status"]=="Aberto").sum())
        is_closed = is_month_closed(ano, mes)
        upsert_kpis(conn, pid, ano, mes, data, n_ev, total_h, em_aberto, is_closed)

        duration = time.time() - t0
        log_fetch(conn, pid, ano, mes, fonte, "OK", rows_e, rows_p, rows_d, duration, None, triggered_by)
        conn.commit()
        return ("OK", f"fonte={fonte}", rows_e, rows_p, rows_d)
    except Exception as e:
        duration = time.time() - t0
        try:
            conn.rollback()
            log_fetch(conn, pid, ano, mes, "n/a", "FAIL", 0, 0, 0, duration, str(e), triggered_by)
            conn.commit()
        except: pass
        return ("FAIL", str(e)[:200], 0, 0, 0)


def listar_plantas_ativas():
    df = app.sql("""
        SELECT id, name FROM public.plant_plant
        WHERE is_active=TRUE AND is_parent=FALSE
        ORDER BY name
    """)
    return [(int(r["id"]), str(r["name"])) for _, r in df.iterrows()]


# ── CLI ───────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plant", type=str, default="all")
    p.add_argument("--ano", type=int)
    p.add_argument("--mes", type=int)
    p.add_argument("--force", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--triggered-by", default="manual")
    p.add_argument("--current", action="store_true",
                   help="usa ano/mes atual com --plant all")
    args = p.parse_args()

    from datetime import datetime
    if args.current:
        n = datetime.now()
        args.ano = n.year; args.mes = n.month; args.plant = "all"

    if not args.ano or not args.mes:
        p.error("--ano e --mes obrigatorios (a menos que --current)")

    if args.plant == "all":
        plantas = listar_plantas_ativas()
    else:
        plantas = [(int(args.plant), "—")]
    if args.limit: plantas = plantas[:args.limit]

    print(f"ETL: {len(plantas)} plantas | {args.ano}-{args.mes:02d} | force={args.force}")
    print(f"Supabase: {SB_CONN['host']}:{SB_CONN['port']}/{SB_CONN['dbname']}")
    conn = sb_connect()

    n_ok = n_fail = n_skip = 0
    t_total = time.time()
    for i, (pid, name) in enumerate(plantas, 1):
        t0 = time.time()
        try:
            status, msg, re_, rp, rd = processar_usina(
                conn, pid, args.ano, args.mes, args.triggered_by, args.force)
        except Exception as e:
            status = "FAIL"; msg = str(e); re_=rp=rd=0
        dt = time.time() - t0
        if status=="OK": n_ok += 1
        elif status=="SKIP": n_skip += 1
        else: n_fail += 1
        print(f"  [{i:>3}/{len(plantas)}] id={pid:<5} {name[:25]:<25} {status:<6} {dt:>5.1f}s  e={re_:<5} p={rp:<4} d={rd:<5}  {msg[:60]}")

    conn.close()
    print(f"\nResumo: OK={n_ok}  SKIP={n_skip}  FAIL={n_fail}  total={len(plantas)}  tempo={time.time()-t_total:.1f}s")


if __name__ == "__main__":
    main()
