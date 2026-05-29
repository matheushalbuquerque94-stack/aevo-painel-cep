"""PoC #4: Capturar request bodies + headers de chamadas POST.

Objetivo: descobrir o formato exato (body, headers) do
  - /rest/pvms/web/report/v1/inverter/energy-generate-kpi-list (POST)
  - /rest/pvms/fm/v1/query (alarmes POST)
  - /rest/dp/pvms/organization/v1/tree (children POST)

Navega em telas que disparam essas chamadas e captura tudo.
"""
import os, sys, io, json, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_state.json")
OUT = os.path.join(HERE, "_post_capture")
os.makedirs(OUT, exist_ok=True)

# Telas-alvo: reportv3 dispara energy-generate-kpi-list (lista inversores+energia)
URLS = {
    "reportv3_andradas":  "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/reportv3/inverter/NE=53128732",
    "reportv3_araguari":  "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/reportv3/inverter/NE=38413012",
    "alarm_andradas":     "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/alarm",
}

from playwright.sync_api import sync_playwright

INTERESTING_PATHS = (
    "/energy-generate-kpi-list",
    "/fm/v1/query",
    "/organization/v1/tree",
    "/organization/v1/locate-tree",
    "/device-history-data",
    "/device-statistics-signal",
    "/devices",   # phyresource/devices
    "/station-list",
    "/inverter",
    "/report",
)


def is_interesting(url):
    return any(p in url for p in INTERESTING_PATHS) and "/rest/" in url


def coletar(page, tag):
    print(f"\n=== {tag} ===")
    capturadas = []

    def on_request(req):
        url = req.url
        if not is_interesting(url): return
        post_data = None
        try: post_data = req.post_data
        except Exception: pass
        capturadas.append({
            "phase": "req",
            "url": url,
            "method": req.method,
            "headers": dict(req.headers),
            "post_data": post_data,
        })

    def on_response(resp):
        url = resp.url
        if not is_interesting(url): return
        try:
            body = resp.text()
        except: body = ""
        capturadas.append({
            "phase": "resp",
            "url": url,
            "status": resp.status,
            "body_len": len(body),
            "body_preview": body[:1000],
        })

    page.on("request", on_request)
    page.on("response", on_response)

    page.goto(URLS[tag], wait_until="networkidle", timeout=30000)
    time.sleep(6)

    # Salva tudo
    with open(os.path.join(OUT, f"{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(capturadas, f, ensure_ascii=False, indent=2)

    # Imprime resumo
    reqs = [c for c in capturadas if c["phase"] == "req"]
    print(f"  {len(reqs)} requests interessantes")
    for r in reqs:
        u = r["url"].split("?")[0]
        u_short = "..." + u[-80:] if len(u) > 80 else u
        method = r["method"]
        body_preview = ""
        if r["post_data"]:
            try:
                parsed = json.loads(r["post_data"])
                body_preview = json.dumps(parsed)[:200]
            except:
                body_preview = r["post_data"][:200]
        print(f"  {method:<5} {u_short}")
        if body_preview:
            print(f"        body: {body_preview}")
    page.remove_listener("request", on_request)
    page.remove_listener("response", on_response)


with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print(f"ERRO: rode _poc_login.py primeiro")
        sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()
    for tag in URLS:
        coletar(page, tag)
    browser.close()

print(f"\nResultados em: {OUT}")
