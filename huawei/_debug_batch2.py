"""Reproduz exatamente o fluxo do batch — incluindo 28 day calls — para entender
porque a SEGUNDA planta falha.
"""
import os, sys, io, time
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from huawei.fusionsolar import FusionSolarClient, KNOWN_LOGINS

storage = os.path.join(HERE, "_storage_aevomaster.json")
fs = FusionSolarClient(username="aevomaster", password=KNOWN_LOGINS["aevomaster"],
                       storage_state_path=storage)
fs.open()
print(f"open() ok, roarand={fs._roarand[:20]}...")

STATIONS = [
    ("NE=33970759", "Juparana 1"),
    ("NE=33967413", "Juparana 2"),
    ("NE=33978610", "Sao Francisco 1"),
]

for dn, label in STATIONS:
    print(f"\n=== {label} ({dn}) ===")
    print(f"  roarand antes = {fs._roarand[:20] if fs._roarand else None}")
    fs.set_station_context(dn)
    print(f"  roarand pos-context = {fs._roarand[:20] if fs._roarand else None}")
    # 1 dia (rapido)
    invs = fs.inverters_daily_energy(dn, date(2026, 5, 20))
    print(f"  dia 20: {len(invs)} inversores")
    if invs:
        print(f"    primeiro: {invs[0]['dn']} {invs[0]['name']} energia={invs[0]['energia_kwh']}")
    # Simula 28 day-calls
    n_ok = 0
    for d in range(1, 29):
        try:
            invs = fs.inverters_daily_energy(dn, date(2026, 5, d))
            if invs: n_ok += 1
        except: pass
    print(f"  28 day calls: {n_ok} retornaram dados")

fs.close()
