"""PoC #7: Capturar POST body real do fm/v1/query em URLs com alarmes reais.

Estrategia: navegar em multiplas paginas/estacoes e ver onde o SPA dispara
o POST de query de alarmes. Salva todos request bodies + responses.
"""
import os, sys, io, json, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_aevomaster.json")
OUT = os.path.join(HERE, "_alarm_capture")
os.makedirs(OUT, exist_ok=True)

BASE = "https://la5.fusionsolar.huawei.com"
ZONE = "a85e6744-6630-4ce9-bdc9-cb4892621115"

# Tentar varias paginas de alarme (active/history/realtime)
URLS = {
    # Por device (inversor especifico)
    "device_jaiba_alarm": f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id={ZONE}#/view/device/NE=46380856/inverter/alarm",
    # Pagina global de alarmes
    "global_alarm_active":  f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id={ZONE}#/run/alarm/realtime/list",
    "global_alarm_history": f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id={ZONE}#/run/alarm/history/list",
    # Estacao em "trouble" (jaíba) — pagina visao geral
    "station_jaiba": f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id={ZONE}#/view/station/NE=46380856/dashboard",
}

INTERESTING = ("/fm/v1/", "/alarm/", "/devtypes")

from playwright.sync_api import sync_playwright


def coletar(page, tag):
    print(f"\n=== {tag} ===")
    print(f"URL: {URLS[tag]}")
    capt = []

    def on_request(req):
        if not any(p in req.url for p in INTERESTING): return
        post_data = None
        try: post_data = req.post_data
        except: pass
        capt.append({"phase": "req", "url": req.url, "method": req.method,
                     "post_data": post_data})

    def on_response(resp):
        if not any(p in resp.url for p in INTERESTING): return
        try: body = resp.text()
        except: body = ""
        capt.append({"phase": "resp", "url": resp.url, "status": resp.status,
                     "body_preview": body[:1500]})

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        page.goto(URLS[tag], wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"  WARN goto: {e}")
    time.sleep(8)

    with open(os.path.join(OUT, f"{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(capt, f, ensure_ascii=False, indent=2)

    reqs = [c for c in capt if c["phase"] == "req" and c["method"] == "POST"]
    print(f"  {len(reqs)} POST requests interessantes")
    for r in reqs:
        url = r["url"].split("?")[0]
        url_short = "..." + url[-70:] if len(url) > 70 else url
        body = r["post_data"]
        if body:
            try: body = json.dumps(json.loads(body))[:400]
            except: body = str(body)[:400]
        print(f"  POST {url_short}")
        if body: print(f"        body: {body}")

    page.remove_listener("request", on_request)
    page.remove_listener("response", on_response)


with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print("ERRO: rode _poc_login.py primeiro"); sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()
    for tag in URLS:
        coletar(page, tag)
    browser.close()

print(f"\nResultados em: {OUT}")
