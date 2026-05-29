"""Cliente FusionSolar (Huawei) — extracao de geracao/historico/alarmes via web APIs.

Uso tipico:

    from huawei.fusionsolar import FusionSolarClient
    with FusionSolarClient(username="aevomaster", password="Aevo@123") as fs:
        for st in fs.list_stations():
            print(st["name"], st["daily_kwh"])
        inversores = fs.inverters_daily_energy("NE=38413012", "2026-05-15")
        for inv in inversores:
            print(inv["dn"], inv["name"], inv["energia_kwh"])

Implementacao:
  - Headless Playwright para login (lida com formulario, captcha-less neste portal)
  - Storage state cacheavel (cookies + localStorage) p/ evitar relogin
  - Token roarand (CSRF) extraido via /keep-alive
  - APIs JSON internas chamadas direto via ctx.request (heranca cookies)
  - Auto-reconnect se sessao expirar (detecta status 401/redirect)
"""
from __future__ import annotations
import os
import json
import time
import re
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Dict, List, Any

from playwright.sync_api import sync_playwright, Page, BrowserContext, APIRequestContext

# Credenciais conhecidas (carregadas via .env normalmente)
KNOWN_LOGINS = {
    "aevomaster":      "Aevo@123",
    "gyaevo":          "Aevo@123",
    "GYaevo":          "NetEcoAEVO123",
    "PontodeEquilibrio": "Ponto01!",
}

BASE = "https://la5.fusionsolar.huawei.com"
LOGIN_URL = f"{BASE}/unisso/login.action"
CLOUD_URL = (f"{BASE}/uniportal/pvmswebsite/assets/build/cloud.html"
             f"?app-id=smartpvms&instance-id=smartpvms"
             f"&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115")

# Signal IDs descobertos no PoC:
SIGNAL_DAILY_ENERGY = 30016   # "Capacidade de geracao do dia corrente" (kWh acumulador)
SIGNAL_ACTIVE_POWER = 30014   # "Potencia ativa" (kW)
SIGNAL_DC_INPUT_POWER = 30017 # "Potencia total de entrada" (kW)

# mocId =
MOC_STATION = 20801
MOC_INVERTER = 20822
MOC_LOGGER = 20821


def br_midnight_ms(year: int, month: int, day: int) -> int:
    """Retorna epoch_ms da meia-noite (BRT, UTC-3) do dia dado."""
    dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    return int(dt.timestamp() * 1000)


def parse_date(d) -> date:
    """Aceita date, datetime, 'YYYY-MM-DD' ou epoch."""
    if isinstance(d, date) and not isinstance(d, datetime): return d
    if isinstance(d, datetime): return d.date()
    if isinstance(d, str):
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    if isinstance(d, (int, float)):
        return datetime.fromtimestamp(d).date()
    raise ValueError(f"data invalida: {d}")


class FusionSolarClient:
    """Cliente para portal FusionSolar (la5.fusionsolar.huawei.com).

    Pode receber username/senha (faz login) OU storage_state_path
    (reusa sessao). Recomendado: passar storage_state_path p/ cache.
    """

    def __init__(self,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 storage_state_path: Optional[str] = None,
                 headless: bool = True,
                 timeout_ms: int = 30000,
                 min_delay_ms: Optional[int] = None):
        self.username = username
        self.password = password
        self.storage_state_path = storage_state_path
        self.headless = headless
        self.timeout = timeout_ms
        # Espaçamento minimo entre chamadas (anti rate-limit / stealth)
        # Default via env HUAWEI_MIN_DELAY_MS, ou 0 (sem espera)
        if min_delay_ms is None:
            try: min_delay_ms = int(os.environ.get("HUAWEI_MIN_DELAY_MS", "0"))
            except: min_delay_ms = 0
        self.min_delay_ms = max(0, min_delay_ms)
        self._last_request_ts = 0.0
        self._playwright = None
        self._browser = None
        self._ctx: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._req: Optional[APIRequestContext] = None
        self._roarand: Optional[str] = None

    def _wait_min_delay(self):
        """Garante intervalo minimo entre chamadas (anti rate-limit)."""
        if self.min_delay_ms <= 0: return
        elapsed_ms = (time.time() - self._last_request_ts) * 1000
        if elapsed_ms < self.min_delay_ms:
            time.sleep((self.min_delay_ms - elapsed_ms) / 1000.0)
        self._last_request_ts = time.time()

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def open(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        ctx_kwargs = {"viewport": {"width": 1440, "height": 900}, "locale": "pt-BR"}
        # Reutiliza storage state se existir
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            ctx_kwargs["storage_state"] = self.storage_state_path
        self._ctx = self._browser.new_context(**ctx_kwargs)
        self._page = self._ctx.new_page()
        self._req = self._ctx.request

        # Tenta usar sessao existente
        if "storage_state" in ctx_kwargs:
            ok = self._init_session()
            if ok: return self
            # Sessao expirou ou invalida -> precisa relogar

        # Faz login
        if not self.username or not self.password:
            raise RuntimeError(
                "Sessao expirou e credenciais nao foram fornecidas. "
                "Passe username/password ou re-rode o login manual.")
        self._do_login()
        self._init_session()
        # Salva storage state se path fornecido
        if self.storage_state_path:
            self._ctx.storage_state(path=self.storage_state_path)

    def close(self):
        try:
            if self._browser: self._browser.close()
        except: pass
        try:
            if self._playwright: self._playwright.stop()
        except: pass

    # ── Login + sessao ────────────────────────────────────────────────────
    def _do_login(self):
        self._page.goto(LOGIN_URL, wait_until="networkidle", timeout=self.timeout)
        # Localiza input de username
        sel_user = None
        for s in ('input[name="username"]', 'input#username',
                  'input[placeholder*="ome"]', 'input[type="text"]'):
            if self._page.query_selector(s):
                sel_user = s; break
        if not sel_user:
            raise RuntimeError("Nao localizou campo de username na pagina de login")
        self._page.fill(sel_user, self.username)
        self._page.fill('input[type="password"]', self.password)
        btn = self._page.query_selector(
            'button:has-text("Login"),button:has-text("Entrar"),'
            'button:has-text("Iniciar"),button[type="submit"]')
        if btn:
            btn.click()
        else:
            self._page.press('input[type="password"]', "Enter")
        try:
            self._page.wait_for_load_state("networkidle", timeout=20000)
        except Exception: pass
        time.sleep(2)
        # Detecta captcha
        if "captcha" in self._page.url.lower() or self._page.query_selector('img[src*="captcha"]'):
            raise RuntimeError(f"CAPTCHA detectado p/ {self.username}; reveja credenciais")

    def _init_session(self) -> bool:
        """Navega p/ cloud.html e captura roarand. Retorna False se nao logado."""
        try:
            self._page.goto(CLOUD_URL, wait_until="networkidle", timeout=self.timeout)
        except Exception:
            return False
        time.sleep(2)
        # Se a URL terminou em login.action, sessao expirou
        if "login" in self._page.url.lower() and "cloud.html" not in self._page.url:
            return False
        # Pega roarand
        self._roarand = self._fetch_roarand()
        return self._roarand is not None

    def _fetch_roarand(self) -> Optional[str]:
        try:
            r = self._req.get(f"{BASE}/rest/dpcloud/auth/v1/keep-alive",
                              headers=self._common_headers(),
                              timeout=self.timeout)
            if r.status != 200: return None
            data = r.json()
            return data.get("payload")
        except Exception:
            return None

    def _common_headers(self, with_roarand=False) -> Dict[str, str]:
        h = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "x-requested-with": "XMLHttpRequest",
            "x-non-renewal-session": "true",
            "x-timezone-offset": "-180",
            "referer": CLOUD_URL,
        }
        if with_roarand and self._roarand:
            h["roarand"] = self._roarand
        return h

    def _post(self, path: str, body: Dict[str, Any], _retried=False) -> Optional[Dict[str, Any]]:
        self._wait_min_delay()
        if not self._roarand:
            self._roarand = self._fetch_roarand()
        headers = self._common_headers(with_roarand=True)
        headers["content-type"] = "application/json"
        headers["accept"] = "application/json, text/plain, */*"
        headers["locale"] = "pt-BR"
        try:
            r = self._req.post(f"{BASE}{path}", headers=headers,
                               data=json.dumps(body), timeout=self.timeout)
            if r.status == 401 or r.status == 403:
                # Sessao expirou: tenta reconectar
                if self._do_login_recover():
                    return self._post(path, body)
                return None
            if r.status != 200:
                if not _retried:
                    # Tenta refresh roarand + retry uma vez (so se conseguir novo token)
                    new = self._fetch_roarand()
                    if new: self._roarand = new
                    return self._post(path, body, _retried=True)
                return None
            if "json" not in (r.headers.get("content-type", "")).lower():
                return None
            data = r.json()
            # Detecta erro mesmo com 200: payload diz success=false
            if isinstance(data, dict):
                if data.get("success") is False and not _retried:
                    new = self._fetch_roarand()
                    if new: self._roarand = new
                    return self._post(path, body, _retried=True)
            return data
        except Exception:
            return None

    def refresh_session(self):
        """Tenta refresh do roarand. Se falhar, MANTEM o atual (ainda pode estar valido)."""
        new = self._fetch_roarand()
        if new: self._roarand = new

    def _get(self, path: str) -> Optional[Any]:
        self._wait_min_delay()
        headers = self._common_headers(with_roarand=True)
        try:
            r = self._req.get(f"{BASE}{path}", headers=headers, timeout=self.timeout)
            if r.status == 401 or r.status == 403:
                if self._do_login_recover(): return self._get(path)
                return None
            if r.status != 200: return None
            if "json" in (r.headers.get("content-type", "")).lower():
                return r.json()
            return r.text()
        except Exception:
            return None

    def _do_login_recover(self) -> bool:
        if not self.username or not self.password:
            return False
        try:
            self._do_login()
            ok = self._init_session()
            if ok and self.storage_state_path:
                self._ctx.storage_state(path=self.storage_state_path)
            return ok
        except Exception:
            return False

    # ── APIs ──────────────────────────────────────────────────────────────
    def list_stations(self, page_size: int = 200) -> List[Dict[str, Any]]:
        """Lista todas as estacoes acessiveis pelo login.
        Retorna dict com: dn, name, status, daily_kwh, month_kwh, year_kwh,
        installed_power_mw, lat, lon, grid_connected_at.
        """
        body = {
            "curPage": 1, "pageSize": page_size,
            "gridConnectedTime": "",
            "queryTime": int(time.time() * 1000),
            "timeZone": -3,
            "sortId": "createTime", "sortDir": "DESC",
            "locale": "pt_BR",
        }
        data = self._post("/rest/pvms/web/station/v1/station/station-list", body)
        if not data or not data.get("data"): return []
        out = []
        for s in data["data"].get("list", []):
            out.append({
                "dn": s.get("dn"),
                "name": s.get("name"),
                "status": s.get("plantStatus"),
                "daily_kwh": _to_float(s.get("dailyEnergy")),
                "month_kwh": _to_float(s.get("monthEnergy")),
                "year_kwh": _to_float(s.get("yearEnergy")),
                "current_power_kw": _to_float(s.get("currentPower")),
                "installed_power_mw": _to_float(s.get("inverterPower") or s.get("onlyInverterPower")),
                "lat": _to_float(s.get("latitude")),
                "lon": _to_float(s.get("longitude")),
                "grid_connected_at": s.get("gridConnectedTime"),
                "timezone": s.get("timeZone"),
                "area": s.get("areaName"),
                "_raw": s,
            })
        return out

    def set_station_context(self, station_dn: str):
        """Hit /locate-tree para configurar o contexto da estacao no servidor.
        Sem isso, energy-kpi-list pode retornar lista vazia ao trocar de planta.
        """
        path = (f"/rest/dp/pvms/organization/v1/locate-tree"
                f"?targetDn={station_dn}&subNodeTypeIds=20800,20801"
                f"&date={int(time.time()*1000)}&typeIdInclude=23000,23001")
        self._get(path)
        # E tambem o tree=device p/ acolchoar contexto de inversores
        try:
            body = {
                "parentDn": station_dn, "treeDepth": "device",
                "pageParam": {"pageId": 1, "pageSize": 100, "needPage": True},
                "filterCond": {"nameType": "device", "mocIdInclude": [20822]},
                "displayCond": {"self": True, "status": False},
            }
            self._post("/rest/dp/pvms/organization/v1/tree", body)
        except Exception: pass

    def inverters_daily_energy(self, station_dn: str, d) -> List[Dict[str, Any]]:
        """Retorna lista de inversores da estacao com a energia gerada
        no dia `d` (date ou 'YYYY-MM-DD').

        Cada item: {dn, name, energia_kwh, installed_capacity_kwp,
                    ac_peak_power_kw, total_power_kwh, collect_ts}

        IMPORTANTE: chame set_station_context(station_dn) UMA vez antes de
        iterar dias da mesma planta — necessario p/ trocar contexto no servidor.
        """
        d = parse_date(d)
        stat_ms = br_midnight_ms(d.year, d.month, d.day)
        body = {
            "moList": [{"moType": MOC_STATION, "moString": station_dn}],
            "stationDn": station_dn,
            "orderBy": "productPower",
            "page": 1, "pageSize": 100,
            "sort": "desc",
            "statTime": stat_ms,
            "statTimeDim": "2",  # DAY
            "timeZone": -3,
            "mocId": MOC_INVERTER,
        }
        data = self._post("/rest/pvms/web/report/v1/inverter/energy-generate-kpi-list", body)
        if not data or not data.get("data"): return []
        out = []
        for it in data["data"].get("list", []):
            name = (it.get("deviceName") or "").replace("&#x28;", "(").replace("&#x29;", ")")
            out.append({
                "dn": it.get("dn") or it.get("deviceDn"),
                "name": name,
                "energia_kwh": _to_float(it.get("productPower")),
                "installed_capacity_kwp": _to_float(it.get("installedCapacity")),
                "ac_peak_power_kw": _to_float(it.get("acPeakPower")),
                "total_power_kwh": _to_float(it.get("totalPower")),
                "collect_ts": it.get("collectTime"),
                "_raw": it,
            })
        return out

    def inverters_month_energy(self, station_dn: str, year: int, month: int) -> List[Dict[str, Any]]:
        """Sum mes inteiro: itera dias e agrega. Retorna lista de inversores
        com {dn, name, dias: [{dia, energia_kwh}], total_kwh}.
        """
        import calendar
        n_days = calendar.monthrange(year, month)[1]
        per_inv: Dict[str, Dict[str, Any]] = {}
        for d in range(1, n_days + 1):
            try: dia = date(year, month, d)
            except: continue
            # Nao tenta dias futuros
            if dia > datetime.now().date(): break
            lst = self.inverters_daily_energy(station_dn, dia)
            for it in lst:
                dn = it["dn"]
                rec = per_inv.setdefault(dn, {"dn": dn, "name": it["name"],
                                              "installed_capacity_kwp": it.get("installed_capacity_kwp"),
                                              "dias": [], "total_kwh": 0.0})
                rec["dias"].append({"dia": dia.strftime("%Y-%m-%d"),
                                    "energia_kwh": it["energia_kwh"]})
                rec["total_kwh"] += it["energia_kwh"] or 0
        return list(per_inv.values())

    def history_5min(self, inverter_dn: str, d, signals=(SIGNAL_DAILY_ENERGY, SIGNAL_ACTIVE_POWER)) -> Dict[int, List[Dict[str, Any]]]:
        """Retorna serie 5-min do dia. Dict {signal_id: [{ts, value}, ...]}.
        Filtra valores NaN (1.7976931348623157E308)."""
        d = parse_date(d)
        date_ms = br_midnight_ms(d.year, d.month, d.day)
        # Multiplos signalIds no query string
        sig_qs = "&".join(f"signalIds={s}" for s in signals)
        path = (f"/rest/pvms/web/device/v1/device-history-data"
                f"?showDst=true&{sig_qs}&deviceDn={inverter_dn}&date={date_ms}")
        data = self._get(path)
        out: Dict[int, List[Dict[str, Any]]] = {}
        if not data or not data.get("data"): return out
        for sid_str, payload in data["data"].items():
            try: sid = int(sid_str)
            except: continue
            series = []
            for p in payload.get("pmDataList", []):
                v = p.get("counterValue")
                if v is None or v > 1e30: continue
                series.append({"ts": p.get("startTime"), "value": v})
            out[sid] = series
        return out

    def alarms_for_station(self, station_dn: str,
                           data_type: str = "HISTORY",
                           page_size: int = 200,
                           max_pages: int = 50) -> List[Dict[str, Any]]:
        """Retorna lista de alarmes da estacao.

        Args:
          station_dn: DN da estacao (NE=...)
          data_type: 'CURRENT' (ativos agora) ou 'HISTORY' (todos historicos)
          page_size: tamanho de pagina (max 200 testado OK)
          max_pages: limite de seguranca (200 x 50 = 10k alarmes)

        Cada item tem:
          alarm_id, alarm_name, severity (1=critical, 2=major, 3=minor, 4=warning),
          inversor (devNameStr), occur_ts (epoch ms), clear_ts (0 se ativo),
          cleared (0/1), duracao_h (computado), inicio (datetime), fim (datetime)
        """
        all_hits = []
        for pg in range(1, max_pages + 1):
            body = {
                "dataType": data_type, "domainType": "OC_SOLAR",
                "pageNo": pg, "pageSize": page_size,
                "nativeMeDn": station_dn,
            }
            r = self._post("/rest/pvms/fm/v1/query", body)
            if not r or not r.get("data"): break
            hits = r["data"].get("hits", [])
            if not hits: break
            all_hits.extend(hits)
            total = r["data"].get("totalCount", 0)
            if len(all_hits) >= total: break

        from datetime import datetime as _dt
        out = []
        for h in all_hits:
            occur_ms = h.get("occurTime") or h.get("latestOccurTime") or 0
            clear_ms = h.get("clearTime") or 0
            cleared = bool(h.get("cleared"))
            try: inicio = _dt.fromtimestamp(occur_ms / 1000) if occur_ms else None
            except: inicio = None
            try: fim = _dt.fromtimestamp(clear_ms / 1000) if clear_ms else None
            except: fim = None
            # Filtra apenas inversores (mocId 20822)
            if h.get("mocId") not in (20822, "20822"): continue
            dur_h = None
            if inicio and fim:
                dur_h = max(0, (fim - inicio).total_seconds() / 3600)
            out.append({
                "alarm_id": h.get("alarmId"),
                "alarm_name": h.get("alarmName"),
                "severity": h.get("severity"),
                "inversor": h.get("devNameStr"),
                "inv_dn": h.get("nativeMoDn"),
                "occur_ms": occur_ms,
                "clear_ms": clear_ms,
                "cleared": cleared,
                "inicio": inicio,
                "fim": fim,
                "duracao_h": dur_h,
                "_raw": h,
            })
        return out

    def list_signals(self, inverter_dn: str) -> List[Dict[str, Any]]:
        """Lista todos os signals disponiveis num inversor (74 no Huawei SUN2000)."""
        data = self._get(f"/rest/pvms/web/device/v1/device-statistics-signal?deviceDn={inverter_dn}")
        if not data or not data.get("data"): return []
        out = []
        for s in data["data"].get("signalList", []):
            out.append({
                "id": s.get("id"),
                "name": s.get("name"),
                "unit": (s.get("unit") or {}).get("unit", ""),
                "period": s.get("period"),
            })
        return out


def _to_float(v) -> Optional[float]:
    if v is None: return None
    try: return float(v)
    except: return None


# ────────────────────────────────────────────────────────────────────────
# CLI de teste
# ────────────────────────────────────────────────────────────────────────
def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="aevomaster")
    ap.add_argument("--pwd",  default=None)
    ap.add_argument("--cmd", choices=["stations", "inverters", "month", "history"],
                    default="stations")
    ap.add_argument("--station-dn", default="NE=38413012")
    ap.add_argument("--inv-dn", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--ano", type=int)
    ap.add_argument("--mes", type=int)
    args = ap.parse_args()

    pwd = args.pwd or KNOWN_LOGINS.get(args.user)
    here = os.path.dirname(os.path.abspath(__file__))
    storage = os.path.join(here, f"_storage_{args.user}.json")
    with FusionSolarClient(username=args.user, password=pwd,
                           storage_state_path=storage) as fs:
        if args.cmd == "stations":
            for st in fs.list_stations():
                print(f"{st['dn']:<22} {st['name'][:30]:<30} {st['status']:<14} "
                      f"daily={st['daily_kwh']} kWh  month={st['month_kwh']} kWh")
        elif args.cmd == "inverters":
            d = args.date or datetime.now().strftime("%Y-%m-%d")
            for inv in fs.inverters_daily_energy(args.station_dn, d):
                print(f"  {inv['dn']:<22} {inv['name'][:25]:<25} "
                      f"{inv['energia_kwh']:>8.1f} kWh  cap={inv['installed_capacity_kwp']} kWp")
        elif args.cmd == "month":
            ano = args.ano or datetime.now().year
            mes = args.mes or datetime.now().month
            for inv in fs.inverters_month_energy(args.station_dn, ano, mes):
                print(f"\n{inv['dn']:<22} {inv['name'][:25]:<25} TOTAL={inv['total_kwh']:.1f} kWh")
                for d in inv["dias"][:5]:
                    print(f"    {d['dia']}: {d['energia_kwh']:.1f} kWh")
        elif args.cmd == "history":
            d = args.date or datetime.now().strftime("%Y-%m-%d")
            inv = args.inv_dn or "NE=38478451"
            series = fs.history_5min(inv, d)
            for sid, pts in series.items():
                if pts:
                    vs = [p["value"] for p in pts]
                    print(f"sig {sid}: {len(pts)} pts, min={min(vs)}, max={max(vs)}")


if __name__ == "__main__":
    _cli()
