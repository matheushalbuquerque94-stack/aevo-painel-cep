"""Diagnostico: chama inverters_daily_energy para varias plantas em sequencia
e mostra exatamente o que cada response retorna.
"""
import os, sys, io, json, time
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from huawei.fusionsolar import FusionSolarClient, KNOWN_LOGINS, br_midnight_ms, BASE

storage = os.path.join(HERE, "_storage_aevomaster.json")
fs = FusionSolarClient(username="aevomaster", password=KNOWN_LOGINS["aevomaster"],
                       storage_state_path=storage)
fs.open()

# Plantas que falharam
DNS = [
    ("NE=33970759", "Juparana 1 (funciona)"),
    ("NE=33967413", "Juparana 2 (falha)"),
    ("NE=33978610", "Sao Francisco 1 (falha)"),
    ("NE=33978622", "Sao Francisco 2 (falha)"),
]

dia_ms = br_midnight_ms(2026, 5, 20)

import json as _json

for dn, label in DNS:
    body = {
        "moList": [{"moType": 20801, "moString": dn}],
        "stationDn": dn,
        "orderBy": "productPower", "page": 1, "pageSize": 100,
        "sort": "desc", "statTime": dia_ms, "statTimeDim": "2",
        "timeZone": -3, "mocId": 20822,
    }
    # Chama POST manualmente p/ ver resposta crua
    headers = fs._common_headers(with_roarand=True)
    headers["content-type"] = "application/json"
    headers["accept"] = "application/json, text/plain, */*"
    headers["locale"] = "pt-BR"
    try:
        r = fs._req.post(f"{BASE}/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list",
                         headers=headers, data=_json.dumps(body), timeout=20000)
        body_text = r.text()
        print(f"\n=== {label} ({dn}) ===")
        print(f"  status={r.status}  ct={r.headers.get('content-type','')[:40]}")
        print(f"  body[:400]={body_text[:400]}")
    except Exception as e:
        print(f"\n=== {label} ===  ERRO: {e}")
    time.sleep(0.3)

fs.close()
