"""Extracao Huawei -> formato compativel com schema reports.energy_daily.

Uso pelo ETL:
    from huawei.extract_huawei import coletar_huawei_mes
    df_daily, df_inv = coletar_huawei_mes(plant_id, 2026, 5)

Retorna:
  df_daily: DataFrame[dia, inversor, modelo, energia_kwh] (formato do app.py)
  df_inv  : DataFrame[inversor, modelo, kwp, energia_kwh, ...] (resumo p/ KPIs)
  fonte   : "Huawei FusionSolar"

Estrategia:
  - Itera dias do mes (de 1 a min(N, hoje))
  - Para cada dia, POST energy-generate-kpi-list com statTime=meia-noite_brt
  - Retorna 1 linha por inversor por dia
"""
import os, sys, calendar
from datetime import datetime, date
from typing import Tuple, Optional

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path: sys.path.insert(0, PARENT)

from huawei.fusionsolar import FusionSolarClient, KNOWN_LOGINS
from huawei.huawei_map import HUAWEI_MAP
from huawei.storage_backup import download_storage, upload_storage


# Cache de clientes por login (evita relogin entre plantas)
_CLIENTS = {}

# Ordem de failover: se o login primario falhar, tenta esses em ordem.
# aevomaster eh o que tem acesso a TODAS as 41 plantas.
_FAILOVER_ORDER = ["aevomaster", "gyaevo", "GYaevo", "PontodeEquilibrio"]

# Registra logins que ja falharam nesta sessao (evita tentar de novo)
_DEAD_LOGINS = set()

# Conn supabase opcional p/ backup/restore de storage_state.
# Settada via set_supabase_conn() — chamada pelo ETL.
_SB_CONN = None


def set_supabase_conn(conn):
    """Conecta este modulo a uma conexao Supabase aberta.
    Quando settada, _try_open_client tenta puxar/persistir storage_state.
    """
    global _SB_CONN
    _SB_CONN = conn


def _try_open_client(login: str) -> Optional["FusionSolarClient"]:
    """Tenta abrir cliente p/ um login especifico. Retorna None se falhar.

    Ordem de tentativa do storage:
      1. Arquivo local _storage_<login>.json se existir
      2. Backup no Supabase (se _SB_CONN settada)
      3. Login fresh com user/pwd
    Apos login bem-sucedido, persiste pro Supabase.
    """
    pwd = KNOWN_LOGINS.get(login)
    if not pwd:
        return None
    storage = os.path.join(HERE, f"_storage_{login}.json")

    # 1. Tenta puxar do Supabase se nao tem local
    if not os.path.exists(storage) and _SB_CONN is not None:
        if download_storage(login, storage, _SB_CONN):
            print(f"  [huawei] storage de {login} restaurado do Supabase")

    client = None
    try:
        client = FusionSolarClient(username=login, password=pwd,
                                   storage_state_path=storage)
        client.open()
        # Smoke test: list_stations p/ verificar sessao boa
        sts = client.list_stations(page_size=5)
        if sts is None: raise RuntimeError("list_stations retornou None")
        # Persiste storage atualizado no Supabase (best-effort)
        if _SB_CONN is not None and os.path.exists(storage):
            upload_storage(login, storage, _SB_CONN,
                           notes=f"saved by ETL run for {login}")
        return client
    except Exception as e:
        print(f"  [huawei] falha p/ login={login}: {str(e)[:80]}")
        try:
            if client: client.close()
        except: pass
        return None


def _get_client(login: str, allow_failover: bool = True) -> FusionSolarClient:
    """Retorna cliente. Tenta login primario; se falhar e allow_failover=True,
    tenta as proximas contas em _FAILOVER_ORDER.
    """
    # Cache hit
    if login in _CLIENTS:
        return _CLIENTS[login]
    # Primario
    if login not in _DEAD_LOGINS:
        client = _try_open_client(login)
        if client:
            _CLIENTS[login] = client
            return client
        _DEAD_LOGINS.add(login)
    if not allow_failover:
        raise RuntimeError(f"Login Huawei '{login}' falhou (failover desativado)")
    # Failover: tenta os outros
    for backup in _FAILOVER_ORDER:
        if backup == login or backup in _DEAD_LOGINS: continue
        if backup in _CLIENTS:
            print(f"  [huawei] failover {login} -> {backup} (cache)")
            return _CLIENTS[backup]
        print(f"  [huawei] failover: tentando {backup}...")
        client = _try_open_client(backup)
        if client:
            _CLIENTS[backup] = client
            return client
        _DEAD_LOGINS.add(backup)
    raise RuntimeError(f"Todos os logins Huawei falharam: {_FAILOVER_ORDER}")


def close_all_clients():
    for c in _CLIENTS.values():
        try: c.close()
        except: pass
    _CLIENTS.clear()
    _DEAD_LOGINS.clear()


def coletar_huawei_mes(plant_id: int, ano: int, mes: int) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Coleta dados de 1 mes inteiro do FusionSolar para 1 planta AEVO.

    Args:
      plant_id: id da plant_plant
      ano, mes: periodo

    Returns:
      (df_daily, df_inv, fonte)
      df_daily: colunas [dia (str YYYY-MM-DD), inversor (str), modelo (str), energia_kwh (float)]
      df_inv:   colunas [inversor, modelo, kwp, energia_kwh, dispersao_pct]
      fonte:    "Huawei FusionSolar"

    Raises:
      KeyError se plant_id nao esta no HUAWEI_MAP
    """
    info = HUAWEI_MAP.get(plant_id)
    if not info:
        raise KeyError(f"plant_id={plant_id} nao mapeado em HUAWEI_MAP")
    station_dn = info["dn"]
    login = info["login"]

    fs = _get_client(login)
    # Refresh roarand + configura contexto da estacao no servidor (sem isso
    # subsequent stations retornam lista vazia)
    fs.refresh_session()
    fs.set_station_context(station_dn)

    # ── 1. Itera dias do mes ─────────────────────────────────────────────
    n_days = calendar.monthrange(ano, mes)[1]
    hoje = datetime.now().date()
    rows_daily = []
    inv_capacities = {}  # inversor -> kwp
    empty_streak = 0

    for d in range(1, n_days + 1):
        try: dia = date(ano, mes, d)
        except: continue
        if dia > hoje: break  # nao chama API p/ futuro
        try:
            invs = fs.inverters_daily_energy(station_dn, dia)
        except Exception as e:
            print(f"  WARN: falha p/ {station_dn} {dia}: {e}")
            continue
        # Se voltou vazio em multiplos dias consecutivos, refresca sessao + retry
        if not invs:
            empty_streak += 1
            if empty_streak >= 2:
                fs.refresh_session()
                empty_streak = 0
                # Retry o mesmo dia apos refresh
                try: invs = fs.inverters_daily_energy(station_dn, dia)
                except: invs = []
            if not invs:
                continue
        empty_streak = 0
        # Detecta nomes duplicados (alguns SmartLoggers tem 2+ inv com mesmo nome)
        # — diferencia via DN p/ evitar conflito no upsert (plant_id,dia,inversor)
        nome_counts = {}
        for it in invs:
            nome_counts[it.get("name") or ""] = nome_counts.get(it.get("name") or "", 0) + 1
        for it in invs:
            base_name = it.get("name") or it.get("dn")
            kwp = it.get("installed_capacity_kwp") or 0
            energia = it.get("energia_kwh") or 0
            # Se duplicado, sufixa com sufixo do DN p/ tornar unico
            if nome_counts.get(it.get("name") or "", 0) > 1:
                dn = it.get("dn", "")
                suffix = dn.replace("NE=", "")[-4:] if dn else ""
                name = f"{base_name}-{suffix}"
            else:
                name = base_name
            inv_capacities[name] = kwp
            rows_daily.append({
                "dia": dia.strftime("%Y-%m-%d"),
                "inversor": name,
                "modelo": "Huawei SUN2000",
                "energia_kwh": float(energia),
            })

    df_daily = pd.DataFrame(rows_daily,
                            columns=["dia", "inversor", "modelo", "energia_kwh"])

    # ── 2. Agrega por inversor ───────────────────────────────────────────
    if df_daily.empty:
        df_inv = pd.DataFrame(columns=["inversor", "modelo", "kwp", "energia_kwh"])
    else:
        agg = df_daily.groupby("inversor")["energia_kwh"].sum().reset_index()
        agg["modelo"] = "Huawei SUN2000"
        agg["kwp"] = agg["inversor"].map(inv_capacities).fillna(0)
        # Dispersao vs maior gerador
        e_max = agg["energia_kwh"].max() or 1
        agg["dispersao_pct"] = (agg["energia_kwh"] / e_max * 100).round(2)
        df_inv = agg[["inversor", "modelo", "kwp", "energia_kwh", "dispersao_pct"]]

    return df_daily, df_inv, "Huawei FusionSolar"


# ── Classificacao de alarmes Huawei -> responsavel ──────────────────────
# Baseado em nomes de alarmes observados no portal FusionSolar.
# Categorias alinhadas com o sistema de 5-estados:
#   Concessionaria: problemas de rede eletrica (sobre/sub tensao, freq, falha rede)
#   Equipamento/O&M: falhas internas (coletor, MPPT, fan, isolamento, modulos)
#   Comunicacao: dongle/RS485/cabo de comunicacao
#   Irradiacao: baixa irradiacao (raro como alarme)
#   Outros: nao classificado
ALARM_KEYWORDS = {
    "Concessionaria": [
        "rede eletric", "rede el�tric", "energia de rede", "subtens", "sobretens",
        "frequenc", "frequ�nc", "rede an", "grid", "tensao da rede", "phase",
        "fora de fase", "queda de rede", "falha de rede",
    ],
    "Equipamento / O&M": [
        "coletor", "isolament", "isol ", "mppt", "fan", "ventilador",
        "boost", "anti-pid", "pid", "ground", "aterramento", "curto",
        "modulo", "m�dulo", "string ", "diodo", "igbt", "fus",
        "alta temp", "temperatura", "sobreaquec", "sobrecorrent",
        "auto-test", "autoteste", "fal coletor",
    ],
    "Comunicacao": [
        "comunic", "dongle", "rs485", "modbus", "cabo de comun",
        "offline", "perda de conex", "sinal fraco",
    ],
    "Irradiacao": [
        "baixa irradiac", "baixa irradia", "low irrad",
    ],
}


def _classify_alarm(alarm_name: str) -> str:
    """Mapeia nome do alarme Huawei para responsavel.
    Retorna: 'Concessionaria' | 'Equipamento / O&M' | 'Comunicacao' | 'Irradiacao' | 'Outros'
    """
    if not alarm_name: return "Outros"
    name_lower = alarm_name.lower()
    for resp, kws in ALARM_KEYWORDS.items():
        for kw in kws:
            if kw in name_lower:
                return resp
    return "Outros"


def _coletar_paradas_huawei(pid, station_dn, ano, mes, df_daily, login):
    """Coleta alarmes HISTORY+CURRENT, clipa no mes, gera df_paradas + disp_dia_inv + kpis_5est.

    Returns: (df_paradas, disp_dia_inv, disp_op_media, kpis_5est)
      df_paradas: cols [inversor, inicio, fim, duracao_h, tipo, causa, responsavel]
      disp_dia_inv: dict {dia: {inversor: pct_disponivel}}
      disp_op_media: float (% medio do mes)
      kpis_5est: dict com tier=1 + pct_geracao/pct_conc/pct_om/pct_com/pct_irr/pct_ger_pure
    """
    from datetime import datetime as _dt, timedelta
    import calendar as _cal

    fs = _get_client(login)
    # Refresh + context p/ trocar de estacao
    fs.refresh_session()
    fs.set_station_context(station_dn)

    # 1. Coleta HISTORY (todos resolvidos) + CURRENT (em aberto)
    try:
        hist = fs.alarms_for_station(station_dn, "HISTORY", page_size=200)
    except Exception as e:
        print(f"  WARN alarmes HISTORY {station_dn}: {e}"); hist = []
    try:
        cur = fs.alarms_for_station(station_dn, "CURRENT", page_size=200)
    except Exception as e:
        print(f"  WARN alarmes CURRENT {station_dn}: {e}"); cur = []

    # 2. Periodo do mes (BRT)
    mes_inicio = _dt(ano, mes, 1)
    n_days = _cal.monthrange(ano, mes)[1]
    mes_fim = _dt(ano, mes, n_days, 23, 59, 59)

    # 3. Constroi df_paradas — clipa alarmes nas bordas do mes
    rows = []
    now_dt = _dt.now()
    for src, lst in (("HISTORY", hist), ("CURRENT", cur)):
        for a in lst:
            ini = a.get("inicio")
            fim = a.get("fim")
            if ini is None: continue
            # Alarmes ativos (CURRENT) usam now() como fim, mas clipa em hoje/agora
            if fim is None:
                fim = min(now_dt, mes_fim)
            # Filtra alarmes totalmente fora do mes
            if fim < mes_inicio or ini > mes_fim: continue
            # Clipa nas bordas do mes
            ini_clip = max(ini, mes_inicio)
            fim_clip = min(fim, mes_fim)
            dur_h = max(0, (fim_clip - ini_clip).total_seconds() / 3600)
            if dur_h <= 0: continue
            # Tipo derivado de severity: 1=critical, 2=major, 3=minor, 4=warning
            sev = a.get("severity")
            tipo = {1: "Critico", 2: "Maior", 3: "Menor", 4: "Aviso"}.get(sev, "Alarme")
            alarm_name = a.get("alarm_name") or ""
            rows.append({
                "inversor": a.get("inversor") or "",
                "inicio": ini_clip.strftime("%d/%m/%Y %H:%M"),
                "fim": fim_clip.strftime("%d/%m/%Y %H:%M") if a.get("cleared") or src == "CURRENT" else "",
                "duracao_h": round(dur_h, 2),
                "tipo": tipo,
                "causa": alarm_name,
                "responsavel": _classify_alarm(alarm_name),
            })
    df_paradas = pd.DataFrame(rows, columns=[
        "inversor", "inicio", "fim", "duracao_h", "tipo", "causa", "responsavel"])

    # 4. disp_dia_inv: % de tempo do dia que cada inversor estava OK
    #    Sempre calcula — mesmo sem paradas (= 100% em todo dia/inv)
    invs = list(df_daily["inversor"].unique()) if not df_daily.empty else []

    horas_off = {d: {} for d in range(1, n_days + 1)}
    for src, lst in (("HISTORY", hist), ("CURRENT", cur)):
        for a in lst:
            ini = a.get("inicio"); fim = a.get("fim")
            if ini is None: continue
            if fim is None: fim = min(now_dt, mes_fim)
            if fim < mes_inicio or ini > mes_fim: continue
            ini_c = max(ini, mes_inicio)
            fim_c = min(fim, mes_fim)
            inv = a.get("inversor") or ""
            # Distribui horas entre dias afetados
            cur_d = ini_c
            while cur_d.date() <= fim_c.date():
                dia = cur_d.day
                dia_inicio = _dt(cur_d.year, cur_d.month, cur_d.day, 0, 0, 0)
                dia_fim    = _dt(cur_d.year, cur_d.month, cur_d.day, 23, 59, 59)
                seg_ini = max(ini_c, dia_inicio)
                seg_fim = min(fim_c, dia_fim)
                dh = max(0, (seg_fim - seg_ini).total_seconds() / 3600)
                if dh > 0 and inv:
                    horas_off[dia][inv] = horas_off[dia].get(inv, 0.0) + dh
                cur_d = dia_fim + timedelta(seconds=1)

    # Converte horas_off -> disp_pct
    HORAS_SOLARES_DIA = 11.5
    disp_dia_inv = {}
    soma_disp = 0.0; n_pts = 0
    inv_dias_com_parada = set()  # (inv, dia) com qualquer parada — p/ pct_ger_pure
    for dia in range(1, n_days + 1):
        disp_dia_inv[dia] = {}
        for inv in invs:
            h = horas_off[dia].get(inv, 0.0)
            h_cap = min(h, HORAS_SOLARES_DIA)
            pct = (1 - h_cap / HORAS_SOLARES_DIA) * 100
            disp_dia_inv[dia][inv] = round(pct, 2)
            soma_disp += pct; n_pts += 1
            if h > 0: inv_dias_com_parada.add((inv, dia))
    disp_op_media = round(soma_disp / n_pts, 2) if n_pts else 100.0

    # ── 5. kpis_5est (categorizacao por responsavel) ─────────────────────
    # Horas off por categoria — usa ja clipados ao mes
    horas_por_resp = {"Concessionaria": 0.0, "Equipamento / O&M": 0.0,
                      "Comunicacao": 0.0, "Irradiacao": 0.0, "Outros": 0.0}
    for src, lst in (("HISTORY", hist), ("CURRENT", cur)):
        for a in lst:
            ini = a.get("inicio"); fim = a.get("fim")
            if ini is None: continue
            if fim is None: fim = min(now_dt, mes_fim)
            if fim < mes_inicio or ini > mes_fim: continue
            ini_c = max(ini, mes_inicio)
            fim_c = min(fim, mes_fim)
            dh = max(0, (fim_c - ini_c).total_seconds() / 3600)
            if dh <= 0: continue
            resp = _classify_alarm(a.get("alarm_name") or "")
            horas_por_resp[resp] += dh

    # Distribui downtime entre as 4 categorias proporcionalmente.
    # Total downtime = (100 - pct_geracao) — vem da disp_op_media baseada em horas_off
    # capadas em horas_solares (11.5h/dia/inv).
    pct_geracao = round(disp_op_media, 2)
    pct_downtime = max(0, 100 - pct_geracao)

    horas_off_total = sum(horas_por_resp.values()) or 1
    # Distribui Outros 50/50 entre conc e om antes de calcular fracoes
    h_outros = horas_por_resp.pop("Outros", 0.0)
    horas_por_resp["Concessionaria"]   += h_outros * 0.5
    horas_por_resp["Equipamento / O&M"] += h_outros * 0.5

    frac_conc = horas_por_resp["Concessionaria"]    / horas_off_total
    frac_om   = horas_por_resp["Equipamento / O&M"] / horas_off_total
    frac_com  = horas_por_resp["Comunicacao"]       / horas_off_total
    frac_irr  = horas_por_resp["Irradiacao"]        / horas_off_total

    pct_conc = round(frac_conc * pct_downtime, 2)
    pct_om   = round(frac_om   * pct_downtime, 2)
    pct_com  = round(frac_com  * pct_downtime, 2)
    pct_irr  = round(frac_irr  * pct_downtime, 2)
    n_inv = max(len(invs), 1)

    # pct_ger_pure = % de pares (inv, dia) SEM nenhuma parada
    total_pares = n_inv * n_days
    pares_com_parada = len(inv_dias_com_parada)
    pct_ger_pure = round((total_pares - pares_com_parada) / total_pares * 100, 2) if total_pares else 100.0

    kpis_5est = {
        "tier": 1,
        "pct_geracao": pct_geracao,
        "pct_ger_pure": pct_ger_pure,
        "pct_conc": pct_conc,
        "pct_om": pct_om,
        "pct_com": pct_com,
        "pct_irr": pct_irr,
    }

    return df_paradas, disp_dia_inv, disp_op_media, kpis_5est


def coletar_dados_usina_huawei(pid: int, ano: int, mes: int,
                               poa_manual: float = 0.0,
                               pv_overrides: Optional[dict] = None) -> dict:
    """Versao Huawei do coletar_dados_usina do app.py — mesma assinatura/output.

    Reusa helpers do app.py para POA, PVsyst, alertas, KPIs, etc. So substitui
    a fonte de dados de geracao (ISC/Banco) pela FusionSolar.

    Returns dict compativel com upsert_energy_daily/upsert_kpis/replace_paradas.
    """
    if pv_overrides is None: pv_overrides = {}
    # Importa app no scope da funcao p/ aceitar stub do streamlit feito pelo ETL
    import app as _app
    import calendar as _cal

    notes = ["Fonte Huawei FusionSolar"]
    df_cad = _app.sql(f"SELECT name,nominal_power_kwp,om_contract,contract_end "
                      f"FROM public.plant_plant WHERE id={pid}")
    if df_cad.empty:
        return {"error": f"usina id={pid} nao encontrada"}
    cad = df_cad.iloc[0].to_dict()
    kwp = float(cad.get("nominal_power_kwp") or 0)

    # PVsyst + overrides
    df_pv = _app.load_pvsyst(pid, ano, mes)
    pvsyst = df_pv.iloc[0].to_dict() if not df_pv.empty else {}
    for k, v in pv_overrides.items():
        if (not pvsyst.get(k)) and v: pvsyst[k] = v

    # Alertas AEVO (banco)
    df_al = _app.load_alertas(pid, ano, mes)

    # ── Geracao Huawei ──
    df_daily, _df_inv, _fonte = coletar_huawei_mes(pid, ano, mes)
    if df_daily.empty:
        return {"error": "Huawei sem dados de geracao", "cad": cad, "notes": notes}

    fonte_energia = "Huawei FusionSolar"

    # POA (mesma logica do AEVO)
    glob_inc = float(pvsyst.get("glob_inc") or 0)
    glob_hor = float(pvsyst.get("glob_hor") or 0)
    poa_banco, ghi_banco = _app.load_poa_banco(pid, ano, mes)
    poa, fonte_poa = _app.resolve_poa(poa_manual, poa_banco, glob_inc, glob_hor, ghi_banco)
    tem_estacao = len(_app.get_ws_ids(pid)) > 0
    df_poa_dia = _app.load_poa_diaria(pid, ano, mes) if tem_estacao else pd.DataFrame()

    # ── Paradas/disponibilidade Huawei ──
    info = HUAWEI_MAP.get(pid)
    station_dn = info["dn"]
    df_paradas, disp_dia_inv, disp_op_media, kpis_5est = _coletar_paradas_huawei(
        pid, station_dn, ano, mes, df_daily, info["login"])
    df_disp_op = pd.DataFrame()  # nao usado direto p/ Huawei (disp_dia_inv ja resolve)

    dias_mes = _cal.monthrange(ano, mes)[1]
    kpis = _app.calc_kpis(df_daily, dias_mes, kwp, poa, pvsyst, df_disp_op)

    return {
        "cad": cad, "kwp": kwp, "pvsyst": pvsyst,
        "ps_id_isc": None, "tem_estacao": tem_estacao,
        "df_al": df_al, "df_daily": df_daily, "df_paradas": df_paradas,
        "df_disp_op": df_disp_op, "df_poa_dia": df_poa_dia,
        "disp_op_media": disp_op_media, "disp_dia_inv": disp_dia_inv,
        "kpis": kpis, "kpis_5est": kpis_5est,
        "poa": poa, "fonte_poa": fonte_poa,
        "fonte_energia": fonte_energia,
        "notes": notes,
    }


# ── CLI de teste ─────────────────────────────────────────────────────────
def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plant", type=int, required=True)
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, required=True)
    args = ap.parse_args()

    print(f"Coletando plant_id={args.plant}  {args.ano}-{args.mes:02d}...")
    try:
        df_daily, df_inv, fonte = coletar_huawei_mes(args.plant, args.ano, args.mes)
    finally:
        close_all_clients()

    print(f"\nFonte: {fonte}")
    print(f"\ndf_daily: {len(df_daily)} linhas")
    if not df_daily.empty:
        print(df_daily.head(10).to_string(index=False))
        print(f"... ({len(df_daily)} total)")
        total = df_daily["energia_kwh"].sum()
        n_dias = df_daily["dia"].nunique()
        n_inv = df_daily["inversor"].nunique()
        print(f"\nResumo: {n_dias} dias x {n_inv} inversores = {total:,.1f} kWh")

    print(f"\ndf_inv: {len(df_inv)} inversores")
    if not df_inv.empty:
        print(df_inv.to_string(index=False))


if __name__ == "__main__":
    _cli()
