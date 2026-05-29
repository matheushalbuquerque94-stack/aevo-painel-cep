"""PoC #5: Chamar as APIs POST direto (sem renderizar pagina).

Pipeline completo:
  1. Login (reusa storage_state)
  2. Seed cloud.html (necessario p/ inicializar sessao)
  3. Captura roarand (token CSRF) via /keep-alive
  4. POST station-list -> lista TODAS as plantas (com KPIs)
  5. POST tree -> lista inversores de uma planta
  6. POST energy-generate-kpi-list -> energia diaria/mensal por inversor
  7. GET device-history-data -> historico 5min por inversor
  8. POST fm/v1/query -> alarmes
"""
import os, sys, io, json, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_state.json")
OUT = os.path.join(HERE, "_direct")
os.makedirs(OUT, exist_ok=True)

BASE = "https://la5.fusionsolar.huawei.com"
SEED_URL = f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115"

from playwright.sync_api import sync_playwright


def br_midnight_ms(year, month, day):
    dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    return int(dt.timestamp() * 1000)


def post(req, path, body, roarand, label=""):
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest",
        "x-non-renewal-session": "true",
        "x-timezone-offset": "-180",
        "roarand": roarand,
        "locale": "pt-BR",
        "referer": SEED_URL,
    }
    url = f"{BASE}{path}"
    try:
        r = req.post(url, headers=headers, data=json.dumps(body), timeout=30000)
        ct = r.headers.get("content-type", "")
        if r.status != 200:
            print(f"    [{r.status}] {label}")
            return None
        if "json" not in ct.lower():
            print(f"    [no-json] {label}: ct={ct}")
            return None
        return r.json()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None


def get(req, path, roarand=None, label=""):
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "x-requested-with": "XMLHttpRequest",
        "x-non-renewal-session": "true",
        "x-timezone-offset": "-180",
        "referer": SEED_URL,
    }
    if roarand: headers["roarand"] = roarand
    url = f"{BASE}{path}"
    try:
        r = req.get(url, headers=headers, timeout=30000)
        if r.status != 200:
            print(f"    [{r.status}] {label}")
            return None
        return r.json() if "json" in r.headers.get("content-type", "").lower() else r.text()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None


with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print(f"ERRO: rode _poc_login.py primeiro")
        sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()

    print("[1] Seed: cloud.html p/ inicializar cookies de sessao...")
    page.goto(SEED_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    req = ctx.request

    # ── 2. Obter roarand ─────────────────────────────────────────────────
    print("\n[2] Obtendo roarand via /keep-alive...")
    ka = get(req, "/rest/dpcloud/auth/v1/keep-alive", label="keep-alive")
    if not ka or not ka.get("payload"):
        print(f"    Falhou: {ka}")
        sys.exit(2)
    roarand = ka["payload"]
    print(f"    roarand={roarand[:30]}...")

    # ── 3. POST station-list -> todas as plantas ─────────────────────────
    print("\n[3] POST station-list (todas as plantas)...")
    body = {
        "curPage": 1, "pageSize": 200,
        "gridConnectedTime": "",
        "queryTime": int(time.time()*1000),
        "timeZone": -3,
        "sortId": "createTime", "sortDir": "DESC",
        "locale": "pt_BR",
    }
    sl = post(req, "/rest/pvms/web/station/v1/station/station-list", body, roarand, "station-list")
    with open(os.path.join(OUT, "station_list.json"), "w", encoding="utf-8") as f:
        json.dump(sl, f, ensure_ascii=False, indent=2)
    stations = []
    if sl and sl.get("data") and sl["data"].get("list"):
        for s in sl["data"]["list"]:
            stations.append({
                "name": s.get("name"),
                "dn": s.get("dn"),
                "status": s.get("plantStatus"),
                "lat": s.get("latitude"), "lon": s.get("longitude"),
                "tz": s.get("timeZone"),
                "gridConnTime": s.get("gridConnectedTime"),
                "installedPower_MW": s.get("inverterPower") or s.get("onlyInverterPower"),
                "dailyEnergy_kWh": s.get("dailyEnergy"),
                "monthEnergy_kWh": s.get("monthEnergy"),
                "yearEnergy_kWh": s.get("yearEnergy"),
            })
        print(f"    {len(stations)} estacoes:")
        for st in stations[:50]:
            print(f"      {st['dn']:<22} {st['name'][:30]:<30} status={st['status']} "
                  f"daily={st['dailyEnergy_kWh']} kWh  month={st['monthEnergy_kWh']} kWh")

    # ── 4. POST /organization/v1/tree -> inversores de uma planta ────────
    target_st = "NE=53128732"  # Andradas 01
    print(f"\n[4] POST /organization/v1/tree p/ {target_st} (inversores)...")
    body = {
        "parentDn": target_st,
        "treeDepth": "device",
        "pageParam": {"pageId": 1, "pageSize": 100, "needPage": True},
        "filterCond": {"nameType": "device", "mocIdInclude": [20822]},
        "displayCond": {"self": True, "status": False},
    }
    tree = post(req, "/rest/dp/pvms/organization/v1/tree", body, roarand, f"tree {target_st}")
    with open(os.path.join(OUT, f"tree_{target_st}.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
    inverters = []

    def collect_invs(node):
        if node.get("mocId") == 20822:
            inverters.append({"dn": node.get("elementDn"), "name": node.get("nodeName"),
                              "status": node.get("status"), "parentDn": node.get("parentDn")})
        for ch in (node.get("childList") or []):
            collect_invs(ch)

    if tree and tree.get("childList"):
        for n in tree["childList"]: collect_invs(n)
    print(f"    {len(inverters)} inversores em {target_st}:")
    for inv in inverters:
        print(f"      {inv['dn']:<22} {inv['name']} (status={inv['status']})")

    # ── 5. POST energy-generate-kpi-list -> energia mensal por inversor ──
    print(f"\n[5] POST energy-generate-kpi-list (mensal) p/ {target_st}...")
    body = {
        "moList": [{"moType": 20801, "moString": target_st}],
        "stationDn": target_st,
        "orderBy": "productPower",
        "page": 1, "pageSize": 100,
        "sort": "desc",
        "statTime": int(time.time()*1000),
        "statTimeDim": "2",  # 2=mes? testar
        "timeZone": -3,
        "mocId": 20822,
    }
    kpi = post(req, "/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list", body, roarand, "kpi-list mes")
    with open(os.path.join(OUT, f"kpi_month_{target_st}.json"), "w", encoding="utf-8") as f:
        json.dump(kpi, f, ensure_ascii=False, indent=2)
    if kpi and kpi.get("success") and kpi.get("data"):
        lst = kpi["data"].get("list", [])
        print(f"    {len(lst)} inversores retornados (statTimeDim=2):")
        for it in lst:
            print(f"      {it.get('dn'):<22} {it.get('deviceName')[:25]:<25} "
                  f"month={it.get('directMonthProductPower')} kWh  "
                  f"year={it.get('directYearProductPower')} kWh  "
                  f"total={it.get('totalPower')} kWh")

    # Testa statTimeDim=1 (diario?)
    print(f"\n[5b] statTimeDim=1 (diario?)...")
    body["statTimeDim"] = "1"
    kpi_d = post(req, "/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list", body, roarand, "kpi-list diario")
    with open(os.path.join(OUT, f"kpi_day_{target_st}.json"), "w", encoding="utf-8") as f:
        json.dump(kpi_d, f, ensure_ascii=False, indent=2)
    if kpi_d and kpi_d.get("data"):
        lst = kpi_d["data"].get("list", [])
        print(f"    {len(lst)} pontos (statTimeDim=1)")
        for it in lst[:5]:
            print(f"      {it.get('deviceDn')} prod={it.get('productPower')} t={it.get('collectTime')}")

    # ── 6. Historico 5min de 1 dia para 1 inversor ───────────────────────
    if inverters:
        inv_dn = inverters[0]["dn"]
        yesterday = datetime.now() - timedelta(days=1)
        date_ms = br_midnight_ms(yesterday.year, yesterday.month, yesterday.day)
        # signal 30016 = capacidade de geracao do dia (kWh - acumulador diario)
        # signal 30014 = potencia ativa AC (kW)
        print(f"\n[6] device-history-data {inv_dn} (ontem {yesterday.date()}, sig=30016+30014)...")
        path = (f"/rest/pvms/web/device/v1/device-history-data"
                f"?showDst=true&signalIds=30014&signalIds=30016"
                f"&deviceDn={inv_dn}&date={date_ms}")
        hist = get(req, path, roarand=roarand, label=f"history {inv_dn}")
        with open(os.path.join(OUT, f"history_{inv_dn}.json"), "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
        if hist and hist.get("data"):
            for sid, payload in hist["data"].items():
                pm = payload.get("pmDataList", [])
                valid = [p for p in pm if p.get("counterValue") is not None and p.get("counterValue") < 1e30]
                if valid:
                    vmax = max(p["counterValue"] for p in valid)
                    vsum = sum(p["counterValue"] for p in valid)
                    print(f"    sig {sid}: {len(pm)} pontos, {len(valid)} validos, max={vmax} sum={vsum:.2f}")
                else:
                    print(f"    sig {sid}: {len(pm)} pontos, 0 validos (todos NaN)")

    # ── 7. Alarmes ───────────────────────────────────────────────────────
    print(f"\n[7] POST fm/v1/query (alarmes ativos)...")
    # Sem filtros = retorna todos abertos do escopo do usuario
    now_ms = int(time.time()*1000)
    body = {
        "moList": [{"moType": 20801, "moString": target_st}],
        "alarmType": "ALL",
        "severity": [], "alarmName": [],
        "beginTime": now_ms - 30*24*3600*1000,
        "endTime": now_ms,
        "alarmStatus": "ACTIVE",
        "offset": 0, "limit": 50,
        "sortField": "occurTime", "sortOrder": "desc",
        "timeZone": -3,
    }
    al = post(req, "/rest/pvms/fm/v1/query", body, roarand, "alarmes ativos")
    with open(os.path.join(OUT, "alarms_active.json"), "w", encoding="utf-8") as f:
        json.dump(al, f, ensure_ascii=False, indent=2)
    if al and al.get("data"):
        hits = al["data"].get("hits", [])
        print(f"    {al['data'].get('totalCount', 0)} alarmes ativos, {len(hits)} retornados")
        for h in hits[:5]:
            print(f"      {h}")

    browser.close()

print(f"\nResultados em: {OUT}")
