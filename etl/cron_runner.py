"""
Cron runner para ETL diario. Entrypoint do servico "etl-cron" no Railway.

Estrategia:
1. Detecta mes atual (UTC-3) e mes anterior (para fechar metricas em D+1)
2. Roda ETL para esses 2 meses, todas as plantas com ISC mapping
3. SKIP automatico para meses ja fechados (kpis_mensal.is_closed=TRUE)
4. Log completo em reports.fetch_log

Variaveis de ambiente esperadas (definir no dashboard Railway):
- SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD
- SUPABASE_REGION (default: us-east-1)
- AEVO_HOST, AEVO_PORT, AEVO_DB, AEVO_USER, AEVO_PASSWORD
- TZ (default: America/Sao_Paulo) — usado para definir "mes atual"
- ETL_MONTHS_BACK (default: 1) — quantos meses para tras tambem processar

Execucao manual local:
    python cron_runner.py
"""
import sys, io, os, time
from datetime import datetime, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

# Stub streamlit
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
        self.session_state = _FakeSession(); self.sidebar = _FakeCtx()
    def cache_data(self, *a, **kw):
        if a and callable(a[0]): return a[0]
        return lambda f: f
    cache_resource = cache_data
    def set_page_config(self, *a, **kw): pass
    def stop(self): raise SystemExit("st.stop()")
    def columns(self, spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return tuple(_FakeCtx() for _ in range(n))
    def tabs(self, names, **kw): return tuple(_FakeCtx() for _ in names)
    def selectbox(self, label, options, *a, **kw):
        try: opts=list(options); return opts[kw.get("index",0)] if opts else None
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

import etl_daily  # noqa: E402


def now_local():
    """Retorna datetime no fuso TZ (ou America/Sao_Paulo por default)."""
    try:
        import pytz
        tz_name = os.environ.get("TZ") or "America/Sao_Paulo"
        return datetime.now(pytz.timezone(tz_name))
    except Exception:
        return datetime.utcnow() - timedelta(hours=3)


def meses_a_processar():
    """Retorna [(ano, mes), ...] do mes corrente + N meses para tras."""
    n_back = int(os.environ.get("ETL_MONTHS_BACK", "1"))
    now = now_local()
    out = [(now.year, now.month)]
    ano, mes = now.year, now.month
    for _ in range(n_back):
        mes -= 1
        if mes == 0: mes = 12; ano -= 1
        out.append((ano, mes))
    return out


def main():
    t0 = time.time()
    print(f"=== CRON RUNNER === {now_local().isoformat()}")
    print(f"Diretorio: {HERE}")
    print(f"Plantas com ISC mapping: {len(etl_daily.app.ISC_MAP)}")

    plantas = etl_daily.listar_plantas_ativas()
    print(f"Plantas ativas no AEVO: {len(plantas)}")

    meses = meses_a_processar()
    print(f"Meses a processar: {meses}")

    conn = etl_daily.sb_connect()
    total_ok = total_skip = total_fail = 0
    for ano, mes in meses:
        print(f"\n--- {ano}-{mes:02d} ---")
        for pid, name in plantas:
            try:
                status, msg, re_, rp, rd = etl_daily.processar_usina(
                    conn, pid, ano, mes, triggered_by="cron", force=False)
            except Exception as e:
                status, msg = "FAIL", str(e)[:200]
            if status == "OK":
                total_ok += 1
                print(f"  [OK] id={pid} {name[:30]:<30} e={re_} p={rp} d={rd}")
            elif status == "SKIP":
                total_skip += 1
            else:
                total_fail += 1
                print(f"  [FAIL] id={pid} {name[:30]:<30} {msg[:60]}")
    conn.close()
    duration = time.time() - t0
    print(f"\n=== FIM === OK={total_ok}  SKIP={total_skip}  FAIL={total_fail}  duracao={duration:.0f}s")


if __name__ == "__main__":
    main()
