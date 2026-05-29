"""Cria mapping HUAWEI: AEVO plant_id -> FusionSolar station DN.

Estrategia:
  1. Lista estacoes FusionSolar (43 plantas via aevomaster) e dos outros logins
  2. Lista plantas ativas no AEVO sem cobertura ISC
  3. Match fuzzy por nome
  4. Imprime sugestao de dict pronta p/ colar em app.py
"""
import os, sys, io, re, json
from difflib import SequenceMatcher

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # importar app.py

# Stub Streamlit p/ importar app.py (mesma estrategia do etl_daily.py)
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
        # Marca auth como ja resolvida p/ pular auth.ensure_login
        self.session_state["auth_user"] = {"username": "etl_local", "role": "admin"}
        self.sidebar = _FakeCtx()
    def cache_data(self, *a, **kw):
        if a and callable(a[0]): return a[0]
        return lambda f: f
    cache_resource = cache_data
    def set_page_config(self, *a, **kw): pass
    def stop(self): pass
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
import app  # noqa

from huawei.fusionsolar import FusionSolarClient, KNOWN_LOGINS


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(ufv|usina|fotovoltaica|fv|brasil)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


# ── 1. Lista FusionSolar ────────────────────────────────────────────────
fs_stations = []
for user, pwd in KNOWN_LOGINS.items():
    storage = os.path.join(HERE, f"_storage_{user}.json")
    print(f"\n[{user}] coletando estacoes...")
    try:
        with FusionSolarClient(username=user, password=pwd,
                               storage_state_path=storage) as fs:
            stations = fs.list_stations()
            for st in stations:
                st["login"] = user
                fs_stations.append(st)
            print(f"    {len(stations)} estacoes em {user}")
    except Exception as e:
        print(f"    ERRO em {user}: {e}")

# Deduplica por DN (usuarios podem ter acesso aos mesmos)
seen = set(); unique_fs = []
for s in fs_stations:
    if s["dn"] in seen: continue
    seen.add(s["dn"]); unique_fs.append(s)
print(f"\nTotal FusionSolar unico: {len(unique_fs)} estacoes")

# ── 2. Lista AEVO ────────────────────────────────────────────────────────
print("\n[AEVO] listando plantas ativas...")
df = app.sql("""
    SELECT id, name FROM public.plant_plant
    WHERE is_active=TRUE AND is_parent=FALSE
    ORDER BY name
""")
aevo_plants = [(int(r["id"]), str(r["name"])) for _, r in df.iterrows()]
print(f"    {len(aevo_plants)} plantas no AEVO")

aevo_no_isc = [(pid, name) for pid, name in aevo_plants if pid not in app.ISC_MAP]
print(f"    {len(aevo_no_isc)} sem cobertura ISC (candidatos a Huawei)")

# ── 3. Match fuzzy ───────────────────────────────────────────────────────
print("\n[MATCH] aproximando AEVO x FusionSolar...")
mapping = {}
matches = []
unmatched_aevo = []
for pid, aname in aevo_no_isc:
    an = norm(aname)
    best = None
    for st in unique_fs:
        fn = norm(st["name"])
        score = similar(an, fn)
        if best is None or score > best["score"]:
            best = {"score": score, "fs": st}
    if best and best["score"] >= 0.55:
        matches.append((pid, aname, best["fs"], best["score"]))
        mapping[pid] = best["fs"]["dn"]
    else:
        unmatched_aevo.append((pid, aname, best))

# Ordena matches por score
matches.sort(key=lambda x: -x[3])
print(f"\n=== {len(matches)} MATCHES (score >= 0.55) ===")
for pid, aname, fs, sc in matches:
    flag = "✓" if sc >= 0.8 else "?" if sc >= 0.65 else "!"
    print(f"  {flag} {sc:.2f}  [{pid:>5}] {aname[:35]:<35} ↔ {fs['dn']:<22} {fs['name']} ({fs['login']})")

print(f"\n=== {len(unmatched_aevo)} SEM MATCH NO AEVO ===")
for pid, aname, best in unmatched_aevo:
    suggestion = ""
    if best:
        suggestion = f"  (mais proximo: {best['fs']['name']} score={best['score']:.2f})"
    print(f"  [{pid:>5}] {aname[:50]}{suggestion}")

# Estacoes FusionSolar sem AEVO
used_dns = set(mapping.values())
unused_fs = [s for s in unique_fs if s["dn"] not in used_dns]
print(f"\n=== {len(unused_fs)} ESTACOES FusionSolar SEM AEVO ===")
for s in unused_fs:
    print(f"  {s['dn']:<22} {s['name']} ({s['login']})")

# ── 4. Output ────────────────────────────────────────────────────────────
out = {
    "matches": [{"plant_id": pid, "aevo_name": an, "fs_dn": fs["dn"],
                 "fs_name": fs["name"], "login": fs["login"], "score": round(sc, 2)}
                for pid, an, fs, sc in matches],
    "unmatched_aevo": [{"plant_id": pid, "name": an} for pid, an, _ in unmatched_aevo],
    "unmatched_fs": [{"dn": s["dn"], "name": s["name"], "login": s["login"]} for s in unused_fs],
}
out_path = os.path.join(HERE, "_mapping_proposta.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\nSalvo: {out_path}")

# Imprime dict Python pronto para colar
print("\n# ============ COLAR EM app.py ============")
print("HUAWEI_MAP = {")
for pid, an, fs, sc in matches:
    if sc >= 0.65:
        print(f'    {pid}: "{fs["dn"]}",  # {an[:30]} ↔ {fs["name"][:30]} (score={sc:.2f})')
print("}")
