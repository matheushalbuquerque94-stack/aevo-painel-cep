"""ETL focado apenas nas plantas ISC pendentes (sem Huawei lento entre elas).

Diferencas do etl_daily.py main loop:
  - Processa SO plantas no ISC_MAP
  - Adiciona delay configuravel entre plantas (anti rate-limit ISC)
  - Re-login ISC apos cada N plantas (mantem token fresco)
"""
import sys, os, argparse, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# Stub streamlit (mesmo padrao)
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
    ap.add_argument("--only-pending", action="store_true",
                    help="processa so plantas que ainda nao tem dados no mes")
    ap.add_argument("--delay", type=int, default=5,
                    help="segundos entre plantas (default 5)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--triggered-by", default="isc_only")
    args = ap.parse_args()

    if args.current:
        from datetime import datetime
        n = datetime.now()
        args.ano = n.year; args.mes = n.month
    if not args.ano or not args.mes:
        ap.error("--ano e --mes obrigatorios (ou --current)")

    # Plantas ativas no ISC_MAP
    df = etl.app.sql("""
        SELECT id, name FROM public.plant_plant
        WHERE is_active=TRUE AND is_parent=FALSE
        ORDER BY name
    """)
    plantas = [(int(r["id"]), str(r["name"])) for _, r in df.iterrows()
               if int(r["id"]) in etl.app.ISC_MAP]

    # Filtra pendentes (sem dados em maio)
    if args.only_pending:
        conn = etl.sb_connect()
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT plant_id FROM reports.energy_daily
                           WHERE dia >= %s AND dia < %s AND fonte = 'iSolarCloud'""",
                        (f"{args.ano}-{args.mes:02d}-01",
                         f"{args.ano + (1 if args.mes==12 else 0)}-{(args.mes%12+1):02d}-01"))
            done = {r[0] for r in cur.fetchall()}
        conn.close()
        plantas = [(pid, nm) for (pid, nm) in plantas if pid not in done]
        print(f"Pendentes ({len(plantas)}): {[pid for pid, _ in plantas]}")

    if args.limit: plantas = plantas[:args.limit]

    print(f"ETL ISC: {len(plantas)} plantas | {args.ano}-{args.mes:02d} | "
          f"force={args.force} | delay={args.delay}s")

    n_ok = n_fail = n_skip = 0
    t_total = time.time()
    for i, (pid, name) in enumerate(plantas, 1):
        t0 = time.time()
        try: conn = etl.sb_connect()
        except Exception as e:
            print(f"  [{i:>2}/{len(plantas)}] id={pid} FAIL conexao: {e}")
            n_fail += 1; continue
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
              f"{dt:>5.1f}s  e={re_:<4} p={rp:<3} d={rd:<4}  {msg[:60]}")
        sys.stdout.flush()

        # Delay entre plantas (anti rate-limit ISC)
        if i < len(plantas) and args.delay > 0:
            time.sleep(args.delay)

    print(f"\nResumo ISC: OK={n_ok}  SKIP={n_skip}  FAIL={n_fail}  "
          f"total={len(plantas)}  tempo={time.time()-t_total:.1f}s")


if __name__ == "__main__":
    main()
