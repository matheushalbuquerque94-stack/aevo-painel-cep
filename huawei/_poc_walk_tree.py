"""PoC #3: Descobrir TODAS as plantas/inversores acessiveis na conta.

Estrategia:
  1. Reusa sessao salva (_storage_state.json do PoC #1)
  2. Abre cloud.html (necessario p/ inicializar cookies/CSRF do app)
  3. Usa page.request.get() (heranca de cookies+headers do browser)
     para chamar APIs JSON diretamente
  4. Walk no organization tree:
       /rest/dp/pvms/organization/v1/tree           -> raiz (children diretos)
       /rest/dp/pvms/organization/v1/locate-tree    -> arvore completa contextualizada
  5. Para cada estacao encontrada, lista inversores filhos
  6. Para um inversor, lista signals disponiveis
  7. Para um inversor, baixa 1 dia de device-history-data (5min)
  8. Salva tudo em _walk/<output>.json para inspecao
"""
import os, sys, io, json, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_state.json")
OUT = os.path.join(HERE, "_walk")
os.makedirs(OUT, exist_ok=True)

BASE = "https://la5.fusionsolar.huawei.com"
SEED_URL = f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/history"

# subNodeTypeIds — inclui todos tipos de nos da arvore (estacoes, inversores, etc).
# Veio das chamadas reais capturadas no PoC #2.
SUB_NODE_TYPE_IDS = (
    "20801,20800,20811,20814,20815,20816,20819,20821,20822,20824,20835,20836,"
    "20837,20838,20847,60014,60022,60066,20844,60080,60026,59986,60044,60043,"
    "60001,60002,60003,60010,60015,69999,60092,60067"
)
TYPE_ID_INCLUDE = "23088,23089,23091,23000,23001,23022"

from playwright.sync_api import sync_playwright


def br_midnight_epoch_ms(year, month, day):
    """Retorna epoch_ms da meia-noite (BRT, UTC-3) do dia dado."""
    dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    return int(dt.timestamp() * 1000)


def get_json(req, url, label):
    """Wrapper p/ chamadas GET com log."""
    try:
        r = req.get(url, timeout=20000)
        ct = r.headers.get("content-type", "")
        if r.status != 200:
            print(f"    [{r.status}] {label} :: {url[:120]}")
            return None
        if "json" not in ct.lower():
            print(f"    [no-json] {label}")
            return None
        return r.json()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None


def walk_tree(req, root_node, depth=0, max_depth=6, accum=None):
    """Recursivamente expande hasMoreChild=true via /tree?parentDn=..."""
    if accum is None: accum = []
    accum.append({
        "depth": depth,
        "name": root_node.get("nodeName"),
        "elementDn": root_node.get("elementDn"),
        "elementId": root_node.get("elementId"),
        "parentDn": root_node.get("parentDn"),
        "typeId": root_node.get("typeId"),
        "mocId": root_node.get("mocId"),
        "status": root_node.get("status"),
        "isParent": root_node.get("isParent"),
        "hasMoreChild": root_node.get("hasMoreChild"),
    })
    if depth >= max_depth: return accum

    # Filhos ja embutidos
    for ch in (root_node.get("childList") or []):
        walk_tree(req, ch, depth+1, max_depth, accum)

    # Se ha mais filhos, busca via API
    if root_node.get("hasMoreChild"):
        dn = root_node.get("elementDn") or ""
        # Tentativa via /tree?parentDn=...
        url = f"{BASE}/rest/dp/pvms/organization/v1/tree?parentDn={dn}"
        data = get_json(req, url, f"tree parentDn={dn}")
        if data:
            for ch in (data.get("childList") or []):
                walk_tree(req, ch, depth+1, max_depth, accum)
    return accum


with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print(f"ERRO: rode _poc_login.py primeiro para criar {STORAGE}")
        sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()

    # Necessario p/ que o app reinicialize cookies de sessao
    print(f"[1] Seed: navegando p/ cloud.html...")
    page.goto(SEED_URL, wait_until="networkidle", timeout=30000)
    time.sleep(5)
    print(f"    URL: {page.url}")
    req = ctx.request   # request context herda cookies

    # ── 2. Raiz da arvore ────────────────────────────────────────────────
    print("\n[2] Raiz /organization/v1/tree (sem parametros)...")
    root = get_json(req, f"{BASE}/rest/dp/pvms/organization/v1/tree", "tree-root")
    with open(os.path.join(OUT, "tree_root.json"), "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
    if root:
        print(f"    raiz tem {len(root.get('childList', []))} filhos diretos, hasMoreChild={root.get('hasMoreChild')}")

    # ── 3. Locate-tree do NE=53128738 (deve dar contexto completo) ───────
    print("\n[3] /organization/v1/locate-tree (NE=53128738 como contexto)...")
    url = (f"{BASE}/rest/dp/pvms/organization/v1/locate-tree"
           f"?targetDn=NE=53128738&subNodeTypeIds={SUB_NODE_TYPE_IDS}"
           f"&date={int(time.time()*1000)}&typeIdInclude={TYPE_ID_INCLUDE}")
    locate = get_json(req, url, "locate-tree")
    with open(os.path.join(OUT, "locate_tree.json"), "w", encoding="utf-8") as f:
        json.dump(locate, f, ensure_ascii=False, indent=2)
    if locate:
        n_top = len(locate.get("childList", []))
        print(f"    locate-tree retornou {n_top} nodes top-level")

    # ── 4. Walk completo a partir da raiz ─────────────────────────────────
    print("\n[4] Walk completo a partir do raiz da organizacao...")
    nodes = []
    if root and root.get("childList"):
        for ch in root.get("childList"):
            walk_tree(req, ch, depth=0, max_depth=6, accum=nodes)
    print(f"    {len(nodes)} nodes coletados (apenas a partir do /tree raiz)")

    # ── 4b. Tentar tambem walk a partir do locate-tree ────────────────────
    print("\n[4b] Walk a partir do locate-tree (mais abrangente)...")
    nodes_locate = []
    if locate and locate.get("childList"):
        for ch in locate.get("childList"):
            walk_tree(req, ch, depth=0, max_depth=6, accum=nodes_locate)
    print(f"    {len(nodes_locate)} nodes coletados via locate-tree")

    # Deduplica por elementDn
    seen, all_nodes = set(), []
    for n in nodes + nodes_locate:
        dn = n.get("elementDn")
        if dn and dn in seen: continue
        seen.add(dn); all_nodes.append(n)
    print(f"    Total deduplicado: {len(all_nodes)} nodes unicos")

    # Categoriza por mocId
    by_moc = {}
    for n in all_nodes:
        by_moc.setdefault(n.get("mocId"), []).append(n)
    print("    Distribuicao por mocId:")
    for moc, ns in sorted(by_moc.items(), key=lambda x: -len(x[1])):
        # 20800=Company, 20801=Station, 20822=Inverter, 20821=SmartLogger, 20819=Dongle
        name = {20800:"Company", 20801:"Station", 20822:"Inverter",
                20821:"SmartLogger", 20819:"Dongle", 20814:"Optimizer",
                20844:"Meter", 23000:"CompanyType", 23022:"InverterType"}.get(moc, "?")
        print(f"      mocId={moc} ({name}): {len(ns)}")

    # Lista estacoes e inversores
    stations = [n for n in all_nodes if n.get("mocId") == 20801]
    inverters = [n for n in all_nodes if n.get("mocId") == 20822]
    print(f"\n    ESTACOES ({len(stations)}):")
    for s in stations[:50]:
        print(f"      - {s.get('elementDn'):<22} {s.get('name')}")
    print(f"\n    INVERSORES ({len(inverters)}) (primeiros 20):")
    for i in inverters[:20]:
        print(f"      - {i.get('elementDn'):<22} {i.get('name')} (parent={i.get('parentDn')})")

    with open(os.path.join(OUT, "all_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(all_nodes, f, ensure_ascii=False, indent=2)

    # ── 5. Para cada estacao, expande p/ pegar inversores  ────────────────
    print("\n[5] Expandindo cada estacao p/ achar inversores...")
    station_inverters = {}  # station_dn -> [inverter_dn,...]
    for s in stations[:10]:  # limita a 10 p/ POC
        s_dn = s.get("elementDn")
        # /tree?parentDn=<station>
        url = f"{BASE}/rest/dp/pvms/organization/v1/tree?parentDn={s_dn}"
        data = get_json(req, url, f"children of {s.get('name')}")
        kids = []
        if data and data.get("childList"):
            # walk em profundidade buscando mocId=20822 (inverter)
            stack = list(data.get("childList"))
            while stack:
                node = stack.pop()
                if node.get("mocId") == 20822:
                    kids.append({"dn": node.get("elementDn"), "name": node.get("nodeName"),
                                 "status": node.get("status")})
                for ch in (node.get("childList") or []):
                    stack.append(ch)
                # Se hasMoreChild, busca recursivamente
                if node.get("hasMoreChild"):
                    child_dn = node.get("elementDn")
                    child_url = f"{BASE}/rest/dp/pvms/organization/v1/tree?parentDn={child_dn}"
                    cd = get_json(req, child_url, f"sub-tree {child_dn}")
                    if cd and cd.get("childList"):
                        for ch in cd.get("childList"): stack.append(ch)
        station_inverters[s_dn] = {"name": s.get("name"), "inverters": kids}
        print(f"    {s.get('name')[:30]:<30} ({s_dn}): {len(kids)} inversores")

    with open(os.path.join(OUT, "station_inverters.json"), "w", encoding="utf-8") as f:
        json.dump(station_inverters, f, ensure_ascii=False, indent=2)

    # ── 6. Lista signals do inversor 53128738 ────────────────────────────
    print("\n[6] /device-statistics-signal NE=53128738...")
    url = f"{BASE}/rest/pvms/web/device/v1/device-statistics-signal?deviceDn=NE=53128738"
    sigs = get_json(req, url, "statistics-signal")
    with open(os.path.join(OUT, "signals_53128738.json"), "w", encoding="utf-8") as f:
        json.dump(sigs, f, ensure_ascii=False, indent=2)
    if sigs and sigs.get("data"):
        sig_list = sigs["data"].get("signalList", [])
        default_list = sigs["data"].get("defaultList", [])
        print(f"    {len(sig_list)} signals, defaultList={default_list}")
        # Procura energia (kWh)
        for s in sig_list:
            name = s.get("name", "").lower()
            unit = (s.get("unit", {}) or {}).get("unit", "")
            if "energia" in name or "kwh" in unit.lower() or s.get("id") in default_list:
                print(f"      id={s.get('id')} name='{s.get('name')}' unit={unit} period={s.get('period')}")

    # ── 7. Baixa 1 dia de historico do NE=53128738 ───────────────────────
    print("\n[7] device-history-data: 1 dia (ontem) NE=53128738...")
    # Ontem BRT
    yesterday = datetime.now() - timedelta(days=1)
    date_ms = br_midnight_epoch_ms(yesterday.year, yesterday.month, yesterday.day)
    url = (f"{BASE}/rest/pvms/web/device/v1/device-history-data"
           f"?showDst=true&signalIds=30014&signalIds=30017"
           f"&deviceDn=NE=53128738&date={date_ms}")
    hist = get_json(req, url, "history yesterday")
    with open(os.path.join(OUT, "history_yesterday.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    if hist and hist.get("data"):
        for sid, payload in hist["data"].items():
            pm = payload.get("pmDataList", [])
            valid = [p for p in pm if p.get("counterValue") not in (None,) and p.get("counterValue") < 1e30]
            print(f"    sig {sid}: {len(pm)} pontos ({len(valid)} validos)")
            if valid:
                first, last = valid[0], valid[-1]
                print(f"      primeiro: t={first.get('startTime')} v={first.get('counterValue')}")
                print(f"      ultimo:   t={last.get('startTime')} v={last.get('counterValue')}")

    # ── 8. KPI mensal/diario via energy-generate-kpi-list ────────────────
    print("\n[8] energy-generate-kpi-list: ultimo dia disponivel...")
    # Esta API parece aceitar POST com filtros. Vamos olhar a captura.
    # No PoC #2 a chamada veio sem body visivel (GET? POST?)
    # Tenta GET:
    url = f"{BASE}/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list"
    kpi = get_json(req, url, "energy-kpi (GET)")
    with open(os.path.join(OUT, "energy_kpi.json"), "w", encoding="utf-8") as f:
        json.dump(kpi, f, ensure_ascii=False, indent=2)
    if kpi: print(f"    {str(kpi)[:200]}")

    browser.close()

print(f"\nResultados em: {OUT}")
print("Proximos passos:")
print("  - Inspecionar all_nodes.json p/ confirmar lista completa de estacoes")
print("  - Validar mapping signal_id -> grandeza fisica em signals_53128738.json")
print("  - Construir extrator de energia diaria a partir do counterId correto")
