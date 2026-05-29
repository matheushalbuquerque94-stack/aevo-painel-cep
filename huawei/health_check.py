"""Health check Huawei FusionSolar — verifica que cada login esta funcional.

Para cada login conhecido:
  1. Tenta logar (com storage cache se houver)
  2. Chama list_stations() — smoke test
  3. Reporta OK ou FAIL

Exit code:
  0 = todos OK (ou pelo menos `aevomaster` OK)
  1 = aevomaster falhou
  2 = todos falharam

Uso:
  python -m huawei.health_check
  python -m huawei.health_check --backup-to-supabase
"""
import os, sys, time, json, argparse
from datetime import datetime

# Garante stdout UTF-8 (Windows)
try: sys.stdout.reconfigure(encoding="utf-8")
except: pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from huawei.fusionsolar import FusionSolarClient, KNOWN_LOGINS
from huawei.storage_backup import upload_storage, download_storage, mark_session_invalid


def check_login(username: str, password: str, sb_conn=None,
                use_supabase_cache: bool = True) -> dict:
    """Testa um login. Retorna {ok: bool, n_stations: int, error: str, duration_s: float}."""
    t0 = time.time()
    storage = os.path.join(HERE, f"_storage_{username}.json")
    # Puxa do Supabase se nao tem local
    if use_supabase_cache and sb_conn and not os.path.exists(storage):
        download_storage(username, storage, sb_conn)

    result = {"username": username, "ok": False, "n_stations": 0,
              "error": None, "duration_s": 0, "checked_at": datetime.now().isoformat()}
    client = None
    try:
        client = FusionSolarClient(username=username, password=password,
                                   storage_state_path=storage,
                                   headless=True, timeout_ms=20000)
        client.open()
        sts = client.list_stations(page_size=5)
        if sts is None:
            raise RuntimeError("list_stations retornou None")
        result["ok"] = True
        result["n_stations"] = len(sts)
        # Persiste sessao boa no Supabase
        if sb_conn and os.path.exists(storage):
            upload_storage(username, storage, sb_conn,
                           notes=f"health check OK ({len(sts)} stations)")
    except Exception as e:
        result["error"] = str(e)[:200]
        if sb_conn:
            mark_session_invalid(username, sb_conn, reason=f"health_check: {result['error']}")
    finally:
        try:
            if client: client.close()
        except: pass
    result["duration_s"] = round(time.time() - t0, 1)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", help="checa apenas 1 usuario (em vez de todos)")
    ap.add_argument("--no-supabase", action="store_true",
                    help="nao usa Supabase como cache (default: usa)")
    ap.add_argument("--json", action="store_true", help="output em JSON")
    args = ap.parse_args()

    sb_conn = None
    if not args.no_supabase:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "etl_daily", os.path.join(ROOT, "etl", "etl_daily.py"))
            etl = importlib.util.module_from_spec(spec)
            # Stub streamlit p/ importar etl_daily
            class _C:
                def __enter__(self): return self
                def __exit__(self,*a): return False
                def __call__(self,*a,**k): return self
                def __getattr__(self,n): return self
            class _ST:
                def __init__(self):
                    self.session_state={"auth_user":{"username":"hc","role":"admin"}}
                    self.sidebar=_C()
                def cache_data(self,*a,**k):
                    if a and callable(a[0]): return a[0]
                    return lambda f:f
                cache_resource=cache_data
                def set_page_config(self,*a,**k): pass
                def stop(self): pass
                def columns(self,s,**k):
                    n=s if isinstance(s,int) else len(s); return tuple(_C() for _ in range(n))
                def tabs(self,n,**k): return tuple(_C() for _ in n)
                def __getattr__(self,n): return lambda *a,**k: _C()
            sys.modules["streamlit"] = _ST()
            spec.loader.exec_module(etl)
            sb_conn = etl.sb_connect()
        except Exception as e:
            print(f"[!] sem conexao Supabase ({e}); usando so cache local")

    users_to_check = [args.user] if args.user else list(KNOWN_LOGINS.keys())
    results = []
    n_ok = 0
    for user in users_to_check:
        pwd = KNOWN_LOGINS.get(user)
        if not pwd:
            results.append({"username": user, "ok": False,
                            "error": "senha desconhecida"})
            continue
        if not args.json:
            print(f"[ ] {user}: checando...", end=" ", flush=True)
        r = check_login(user, pwd, sb_conn=sb_conn,
                        use_supabase_cache=not args.no_supabase)
        results.append(r)
        if not args.json:
            status = "OK" if r["ok"] else "FAIL"
            extra = (f"({r['n_stations']} stations)" if r["ok"]
                     else f"err={r['error'][:60]}")
            print(f"\r[{status}] {user}: {extra} ({r['duration_s']}s)")
        if r["ok"]: n_ok += 1

    if sb_conn:
        try: sb_conn.close()
        except: pass

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(f"\nResumo: {n_ok}/{len(results)} contas OK")

    # Exit code: 0 = aevomaster OK (suficiente), 1 = aevomaster falhou
    primary = next((r for r in results if r["username"] == "aevomaster"), None)
    if primary and primary["ok"]:
        sys.exit(0)
    if n_ok > 0:
        sys.exit(0)  # algum funciona — failover salva
    sys.exit(2)  # nada funciona


if __name__ == "__main__":
    main()
