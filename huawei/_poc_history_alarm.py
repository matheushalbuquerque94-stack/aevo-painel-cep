"""PoC #6: Validar dados historicos por dia + capturar body real do alarm POST.

Estrategia:
  - Testa energy-generate-kpi-list com statTime de DATAS DIFERENTES (dias passados)
    p/ ver se retorna historico ou so o "hoje".
  - Navega na pagina de alarmes p/ capturar o body POST exato.
  - Testa pegar 1 dia inteiro de historico 5min para 1 inversor ativo
    (NE=53128738 retornou 0s; tentar Araguari ou outro com energia).
"""
import os, sys, io, json, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_state.json")
OUT = os.path.join(HERE, "_history_alarm")
os.makedirs(OUT, exist_ok=True)

BASE = "https://la5.fusionsolar.huawei.com"
SEED_URL = f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115"

from playwright.sync_api import sync_playwright


def br_midnight_ms(year, month, day):
    dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    return int(dt.timestamp() * 1000)

def post(req, path, body, roarand, label=""):
    headers = {
        "content-type": "application/json", "accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest", "x-non-renewal-session": "true",
        "x-timezone-offset": "-180", "roarand": roarand, "locale": "pt-BR",
        "referer": SEED_URL,
    }
    try:
        r = req.post(f"{BASE}{path}", headers=headers, data=json.dumps(body), timeout=30000)
        if r.status != 200:
            print(f"    [{r.status}] {label}: {r.text()[:300]}")
            return None
        return r.json()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None

def get_json(req, path, roarand=None, label=""):
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "x-requested-with": "XMLHttpRequest", "x-non-renewal-session": "true",
        "x-timezone-offset": "-180", "referer": SEED_URL,
    }
    if roarand: headers["roarand"] = roarand
    try:
        r = req.get(f"{BASE}{path}", headers=headers, timeout=30000)
        if r.status != 200:
            print(f"    [{r.status}] {label}")
            return None
        return r.json()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None


with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print("ERRO: rode _poc_login.py primeiro"); sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()
    page.goto(SEED_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    req = ctx.request

    ka = get_json(req, "/rest/dpcloud/auth/v1/keep-alive", label="keep-alive")
    roarand = ka["payload"]
    print(f"roarand={roarand[:30]}...")

    # ── 1. Variar statTimeDim e statTime ─────────────────────────────────
    target_st = "NE=38413012"  # Araguari (sabidamente ativa, 13676.5 kWh hoje)
    test_dates = [
        (2026, 5, 27, "ontem 27/05/2026"),
        (2026, 5, 20, "20/05/2026"),
        (2026, 5, 15, "15/05/2026"),
        (2026, 4, 15, "15/04/2026"),
        (2026, 1, 15, "15/01/2026"),
    ]
    print(f"\n[1] Testando statTimeDim x statTime para {target_st} (Araguari)")
    for (y,m,d, tag) in test_dates:
        for dim in ["2", "3"]:  # 2=daily?, 3=monthly?
            stat_ms = br_midnight_ms(y, m, d)
            body = {
                "moList": [{"moType": 20801, "moString": target_st}],
                "stationDn": target_st,
                "orderBy": "productPower", "page": 1, "pageSize": 100,
                "sort": "desc", "statTime": stat_ms, "statTimeDim": dim,
                "timeZone": -3, "mocId": 20822,
            }
            kpi = post(req, "/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list",
                       body, roarand, f"kpi {tag} dim={dim}")
            if kpi and kpi.get("data") and kpi["data"].get("list"):
                lst = kpi["data"]["list"]
                total_prod = sum(it.get("productPower") or 0 for it in lst)
                total_month = sum(it.get("directMonthProductPower") or 0 for it in lst)
                total_year = sum(it.get("directYearProductPower") or 0 for it in lst)
                first = lst[0]
                print(f"    {tag:<25} dim={dim}: n_inv={len(lst):<2} "
                      f"prod={total_prod:>8.1f}  month={total_month:>10.1f}  year={total_year:>10.1f}  "
                      f"collectTime={first.get('collectTime')}")

    # Salva detalhe de 1 chamada
    body = {
        "moList": [{"moType": 20801, "moString": target_st}],
        "stationDn": target_st,
        "orderBy": "productPower", "page": 1, "pageSize": 100,
        "sort": "desc", "statTime": br_midnight_ms(2026,5,20), "statTimeDim": "2",
        "timeZone": -3, "mocId": 20822,
    }
    sample = post(req, "/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list",
                  body, roarand, "sample")
    with open(os.path.join(OUT, "kpi_sample_araguari_20mai.json"), "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    # ── 2. Capturar body real do alarm POST ───────────────────────────────
    print("\n[2] Navegando em /alarm/realtime p/ capturar POST exato...")
    capt = []
    page.on("request", lambda r: (capt.append({
        "url": r.url, "method": r.method, "post_data": r.post_data,
    }) if "fm/v1" in r.url and r.method == "POST" else None))

    # Pagina de alarmes ativos
    page.goto(f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/maintenance/alarm/realtime",
              wait_until="networkidle", timeout=30000)
    time.sleep(6)
    print(f"    {len(capt)} POSTs fm/v1 capturados")
    for c in capt[:5]:
        u = c["url"].split("?")[0]
        print(f"    POST {u}")
        if c["post_data"]:
            try: body = json.loads(c["post_data"])
            except: body = c["post_data"]
            print(f"        body: {json.dumps(body)[:400]}")
    with open(os.path.join(OUT, "alarm_post_capture.json"), "w", encoding="utf-8") as f:
        json.dump(capt, f, ensure_ascii=False, indent=2)

    # Tentar o POST com body capturado
    alarm_posts = [c for c in capt if "/fm/v1/query" in c["url"] and not c["url"].endswith("alarm-total") and c["post_data"]]
    if alarm_posts:
        real_body = json.loads(alarm_posts[0]["post_data"])
        print(f"\n[3] Tentando POST real fm/v1/query com body capturado...")
        # Customiza p/ pegar alarmes historicos do Araguari
        if "moList" in real_body or "moDns" in real_body:
            print(f"    keys: {list(real_body.keys())}")
        result = post(req, "/rest/pvms/fm/v1/query", real_body, roarand, "alarm real body")
        if result and result.get("data"):
            print(f"    total={result['data'].get('totalCount')} hits={len(result['data'].get('hits',[]))}")
            with open(os.path.join(OUT, "alarms_real.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

    # ── 4. Testa device-history-data inversor ATIVO (Araguari ou similar)
    # Primeiro pega a lista de inversores do Araguari
    print("\n[4] Buscando inversores Araguari para teste de history...")
    body_kpi = {
        "moList": [{"moType": 20801, "moString": target_st}],
        "stationDn": target_st,
        "orderBy": "productPower", "page": 1, "pageSize": 100,
        "sort": "desc", "statTime": int(time.time()*1000), "statTimeDim": "2",
        "timeZone": -3, "mocId": 20822,
    }
    k = post(req, "/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list",
             body_kpi, roarand, "araguari kpi")
    invs_araguari = [it.get("dn") for it in (k.get("data",{}).get("list",[]) if k else [])]
    print(f"    Araguari tem {len(invs_araguari)} inversores: {invs_araguari[:3]}...")

    if invs_araguari:
        inv = invs_araguari[0]
        yesterday = datetime.now() - timedelta(days=1)
        date_ms = br_midnight_ms(yesterday.year, yesterday.month, yesterday.day)
        # signal 30016 = capacidade de geracao do dia (acumulador diario kWh)
        path = (f"/rest/pvms/web/device/v1/device-history-data"
                f"?showDst=true&signalIds=30016&signalIds=30014"
                f"&deviceDn={inv}&date={date_ms}")
        h = get_json(req, path, roarand=roarand, label=f"history {inv}")
        with open(os.path.join(OUT, f"history_araguari_{inv}.json"), "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
        if h and h.get("data"):
            for sid, payload in h["data"].items():
                pm = payload.get("pmDataList", [])
                valid = [p for p in pm if p.get("counterValue") is not None and p.get("counterValue") < 1e30]
                if valid:
                    vmax = max(p["counterValue"] for p in valid)
                    vmin = min(p["counterValue"] for p in valid)
                    print(f"    {inv} sig {sid}: {len(pm)} pts, {len(valid)} validos, "
                          f"min={vmin} max={vmax}")

    browser.close()

print(f"\nResultados em: {OUT}")
