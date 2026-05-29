"""PoC #8: Testar fm/v1/query com dataType=HISTORY + filtros de data + paginacao.

Tambem testa se ha endpoint separado p/ histórico, e se severity/mocId filtram.
"""
import os, sys, io, json, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(HERE, "_storage_aevomaster.json")
OUT = os.path.join(HERE, "_alarm_history")
os.makedirs(OUT, exist_ok=True)

BASE = "https://la5.fusionsolar.huawei.com"
SEED_URL = (f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html"
            f"?app-id=smartpvms&instance-id=smartpvms"
            f"&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115"
            f"#/view/device/NE=46380856/inverter/alarm")

from playwright.sync_api import sync_playwright


def br_ms(y, m, d):
    dt = datetime(y, m, d, tzinfo=timezone(timedelta(hours=-3)))
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
            print(f"    [{r.status}] {label}: {r.text()[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"    [err] {label}: {e}")
        return None


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=STORAGE, viewport={"width": 1440, "height": 900}, locale="pt-BR")
    page = ctx.new_page()
    page.goto(SEED_URL, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    req = ctx.request

    # roarand
    r = req.get(f"{BASE}/rest/dpcloud/auth/v1/keep-alive",
                headers={"accept": "application/json", "x-non-renewal-session": "true"})
    roarand = r.json()["payload"]
    print(f"roarand={roarand[:30]}...")

    # ── 1. CURRENT alarmes Jaíba (control) ───────────────────────────────
    print("\n[1] CURRENT alarmes Jaíba (controle)...")
    body = {"dataType": "CURRENT", "domainType": "OC_SOLAR",
            "pageNo": 1, "pageSize": 100, "nativeMeDn": "NE=46380856"}
    cur = post(req, "/rest/pvms/fm/v1/query", body, roarand, "current")
    with open(os.path.join(OUT, "current_jaiba.json"), "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    if cur and cur.get("data"):
        hits = cur["data"].get("hits", [])
        print(f"    total={cur['data'].get('totalCount')}  hits={len(hits)}")
        if hits:
            h = hits[0]
            print(f"    sample: {h.get('alarmName')[:40]:<40} inv={h.get('devNameStr')[:25]:<25} "
                  f"occur={h.get('occurTimeStr')} cleared={h.get('cleared')}")

    # ── 2. HISTORY alarmes Jaíba ─────────────────────────────────────────
    print("\n[2] HISTORY alarmes Jaíba (todo periodo)...")
    body = {"dataType": "HISTORY", "domainType": "OC_SOLAR",
            "pageNo": 1, "pageSize": 100, "nativeMeDn": "NE=46380856"}
    hist = post(req, "/rest/pvms/fm/v1/query", body, roarand, "history")
    with open(os.path.join(OUT, "history_jaiba.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    if hist and hist.get("data"):
        hits = hist["data"].get("hits", [])
        print(f"    total={hist['data'].get('totalCount')}  hits={len(hits)}")
        # estatistica de cleared/severity
        cleared = sum(1 for h in hits if h.get("cleared"))
        print(f"    cleared={cleared}/{len(hits)}")
        for h in hits[:5]:
            print(f"    {h.get('alarmName')[:35]:<35} inv={h.get('devNameStr')[:25]:<25} "
                  f"occur={h.get('occurTimeStr')} clear={h.get('clearType')}")

    # ── 3. HISTORY com filtro de data (maio/2026) ────────────────────────
    print("\n[3] HISTORY maio/2026 com filtro de data...")
    begin = br_ms(2026, 5, 1)
    end   = br_ms(2026, 6, 1)
    body = {"dataType": "HISTORY", "domainType": "OC_SOLAR",
            "pageNo": 1, "pageSize": 200, "nativeMeDn": "NE=46380856",
            "beginTime": begin, "endTime": end}
    hist2 = post(req, "/rest/pvms/fm/v1/query", body, roarand, "history-maio")
    with open(os.path.join(OUT, "history_jaiba_maio.json"), "w", encoding="utf-8") as f:
        json.dump(hist2, f, ensure_ascii=False, indent=2)
    if hist2 and hist2.get("data"):
        hits = hist2["data"].get("hits", [])
        print(f"    total={hist2['data'].get('totalCount')}  hits={len(hits)}")

    # ── 4. CURRENT — pega TUDO via paginacao ────────────────────────────
    print("\n[4] CURRENT — pagina ate o fim...")
    all_hits = []
    page_no = 1
    while True:
        body = {"dataType": "CURRENT", "domainType": "OC_SOLAR",
                "pageNo": page_no, "pageSize": 100, "nativeMeDn": "NE=46380856"}
        r = post(req, "/rest/pvms/fm/v1/query", body, roarand, f"pg{page_no}")
        if not r or not r.get("data"): break
        hits = r["data"].get("hits", [])
        all_hits.extend(hits)
        total = r["data"].get("totalCount", 0)
        print(f"    pg{page_no}: {len(hits)} hits  (acumulado={len(all_hits)}/{total})")
        if len(all_hits) >= total or len(hits) == 0: break
        page_no += 1
    print(f"    TOTAL CURRENT Jaíba: {len(all_hits)} alarmes")

    # ── 5. Teste outra estacao (Talisma — connected, deveria ter pouco) ──
    print("\n[5] CURRENT Talisma (connected)...")
    body = {"dataType": "CURRENT", "domainType": "OC_SOLAR",
            "pageNo": 1, "pageSize": 100, "nativeMeDn": "NE=35236132"}
    r = post(req, "/rest/pvms/fm/v1/query", body, roarand, "talisma")
    if r and r.get("data"):
        print(f"    total={r['data'].get('totalCount')} hits={len(r['data'].get('hits',[]))}")

    browser.close()

print(f"\nResultados em: {OUT}")
