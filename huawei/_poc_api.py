"""PoC #2: descobrir as APIs JSON internas que alimentam as telas.

Estrategia: reusa sessao salva, navega pelas telas chave, captura
todas as requests XHR/fetch que retornam JSON. Estas APIs sao bem mais
robustas que parse de HTML para extrair os dados.
"""
import os, sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_state.json")
OUT = os.path.join(HERE, "_api_capture")
os.makedirs(OUT, exist_ok=True)

URLS = {
    "history": "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/history",
    "alarm": "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/alarm",
    "details": "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/details",
    "reportv3": "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/reportv3/inverter/NE=53128738",
}

from playwright.sync_api import sync_playwright

# Captura request/response de cada tela separadamente
def coletar(page, tag):
    print(f"\n=== {tag} ===")
    print(f"URL: {URLS[tag]}")
    capturadas = []

    def on_response(resp):
        url = resp.url
        # Filtrar para nao capturar assets (js/css/imgs)
        ct = resp.headers.get("content-type", "")
        if "json" not in ct.lower(): return
        if "/rest/" not in url and "/inverter" not in url and "/device" not in url and "/report" not in url: return
        try:
            body = resp.text()
            capturadas.append({
                "url": url, "status": resp.status,
                "content_type": ct,
                "body_len": len(body),
                "body_preview": body[:500],
            })
        except Exception as e:
            capturadas.append({"url": url, "err": str(e)})

    page.on("response", on_response)

    page.goto(URLS[tag], wait_until="networkidle", timeout=30000)
    time.sleep(8)  # dar tempo do SPA carregar
    page.screenshot(path=os.path.join(OUT, f"{tag}.png"), full_page=False)

    # Filtrar duplicatas (mesma URL)
    seen = set()
    uniques = []
    for c in capturadas:
        u = c["url"].split("?")[0]
        if u in seen: continue
        seen.add(u); uniques.append(c)

    print(f"  {len(capturadas)} responses JSON, {len(uniques)} URLs unicos")
    for c in uniques[:20]:
        u = c["url"]
        if len(u) > 110: u = u[:110] + "..."
        print(f"  [{c.get('status','?')}] {u}")
        if c.get("body_len", 0) > 0 and c.get("body_len", 0) < 2000:
            print(f"      body: {c.get('body_preview','')[:200]}")

    # Salvar tudo num JSON
    with open(os.path.join(OUT, f"{tag}_capture.json"), "w", encoding="utf-8") as f:
        json.dump(capturadas, f, ensure_ascii=False, indent=2)

with sync_playwright() as p:
    if not os.path.exists(STORAGE):
        print(f"ERRO: rode _poc_login.py primeiro para criar {STORAGE}")
        sys.exit(1)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        storage_state=STORAGE,
        viewport={"width": 1440, "height": 900},
        locale="pt-BR",
    )
    page = ctx.new_page()

    for tag in URLS:
        coletar(page, tag)

    browser.close()

print(f"\nResultados em: {OUT}")
