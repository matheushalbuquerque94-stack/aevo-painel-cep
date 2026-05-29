"""ETL focado apenas nas plantas Huawei (HUAWEI_MAP).

Uso:
  python etl/etl_huawei_only.py --ano 2026 --mes 5 [--force]
  python etl/etl_huawei_only.py --current
"""
import sys, os, argparse, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# Stub streamlit (mesmo padrao do etl_daily.py)
class _FakeCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **kw): return self
    def __getattr__(self, n): return self
    def __iter__(self): return iter([_FakeCtx() for _ in range(20)])
class _FakeSess(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v
class _FakeSt:
    def __init__(self):
        self.session_state = _FakeSess()
        self.session_state["auth_user"] = {"username": "etl", "role": "admin"}
        self.sidebar = _FakeCtx()
    def cache_data(self, *a, **kw):
        if a and callable(a[0]): return a[0]
        return lambda f: f
    cache_resource = cache_data
    def set_page_config(self, *a, **kw): pass
    def stop(self): pass
    def columns(self, s, **kw):
        n = s if isinstance(s, int) else len(s); return tuple(_FakeCtx() for _ in range(n))
    def tabs(self, n, **kw): return tuple(_FakeCtx() for _ in n)
    def selectbox(self, *a, **kw):
        try: opts = list(a[1] if len(a)>1 else kw.get("options", [])); return opts[0] if opts else None
        except: return None
    def __getattr__(self, n):
        return lambda *a, **kw: _FakeCtx()
sys.modules["streamlit"] = _FakeSt()

# Importa funcoes do etl_daily como modulo (sem CLI)
import importlib.util
spec = importlib.util.spec_from_file_location("etl_daily", os.path.join(HERE, "etl_daily.py"))
etl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int)
    ap.add_argument("--mes", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--triggered-by", default="huawei_only")
    args = ap.parse_args()

    if args.current:
        from datetime import datetime
        n = datetime.now()
        args.ano = n.year; args.mes = n.month
    if not args.ano or not args.mes:
        ap.error("--ano e --mes obrigatorios (ou --current)")

    if not etl._HUAWEI_OK:
        print("Huawei nao carregado — verifique imports")
        sys.exit(1)

    # Plantas ativas no AEVO QUE estao no HUAWEI_MAP
    df = etl.app.sql("""
        SELECT id, name FROM public.plant_plant
        WHERE is_active=TRUE AND is_parent=FALSE
        ORDER BY name
    """)
    plantas = [(int(r["id"]), str(r["name"])) for _, r in df.iterrows()
               if int(r["id"]) in etl.HUAWEI_MAP]
    if args.limit: plantas = plantas[:args.limit]

    print(f"ETL Huawei: {len(plantas)} plantas | {args.ano}-{args.mes:02d} | force={args.force}")

    n_ok = n_fail = n_skip = 0
    t_total = time.time()
    for i, (pid, name) in enumerate(plantas, 1):
        t0 = time.time()
        # Conn fresca por planta (Playwright pode demorar +30s, pooler Supabase mata idle)
        try: conn = etl.sb_connect()
        except Exception as e:
            print(f"  [{i:>2}/{len(plantas)}] id={pid} FAIL conexao Supabase: {e}")
            n_fail += 1; continue
        # Conecta Huawei storage_backup ao Supabase
        try: etl._huawei_set_conn(conn)
        except: pass
        try:
            status, msg, re_, rp, rd = etl.processar_usina(
                conn, pid, args.ano, args.mes, args.triggered_by, args.force)
        except Exception as e:
            status, msg, re_, rp, rd = "FAIL", str(e), 0, 0, 0
        try: conn.close()
        except: pass
        dt = time.time() - t0
        if status == "OK": n_ok += 1
        elif status == "SKIP": n_skip += 1
        else: n_fail += 1
        print(f"  [{i:>2}/{len(plantas)}] id={pid:<5} {name[:28]:<28} {status:<5} "
              f"{dt:>5.1f}s  e={re_:<4} p={rp:<3} d={rd:<4}  {msg[:50]}")
        sys.stdout.flush()
    try: etl._huawei_close()
    except: pass
    print(f"\nResumo Huawei: OK={n_ok}  SKIP={n_skip}  FAIL={n_fail}  "
          f"total={len(plantas)}  tempo={time.time()-t_total:.1f}s")


if __name__ == "__main__":
    main()
