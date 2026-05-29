import streamlit as st
import pandas as pd
import asyncio
import tempfile
import os
import psycopg2
import requests
import json
import uuid
import base64
import calendar
from datetime import datetime, timedelta
import pickle

# ── Cache disco ────────────────────────────────────────────
_CACHE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"cache")
def _cache_path(ps_id,ano,mes,tag):
    os.makedirs(_CACHE_DIR,exist_ok=True)
    return os.path.join(_CACHE_DIR,"%s_%d_%02d_%s.pkl"%(ps_id,ano,mes,tag))
def _mes_fechado(ano,mes):
    n=datetime.now(); return (ano,mes)<(n.year,n.month)
def _cache_load(ps_id,ano,mes,tag):
    p=_cache_path(ps_id,ano,mes,tag)
    if os.path.exists(p):
        try:
            with open(p,"rb") as f: return pickle.load(f)
        except: pass
    return None
def _cache_save(ps_id,ano,mes,tag,data):
    try:
        with open(_cache_path(ps_id,ano,mes,tag),"wb") as f: pickle.dump(data,f)
    except: pass

ISC_MAP    = {58:1549319, 61:1517600, 63:1498312, 65:1494628, 66:1483368, 67:1479714, 69:1477206, 75:1311937, 76:1311924, 87:1552680, 94:1531227, 95:1566066, 472:1467815, 473:1467043, 476:1596115, 479:1601156, 491:1325867, 1258:1646228, 1260:1640994, 1364:1675883}

_CHARTJS_CODE = ""
def _ensure_chartjs():
    global _CHARTJS_CODE
    if _CHARTJS_CODE: return
    import urllib.request
    try:
        _CHARTJS_CODE = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js", timeout=15).read().decode("utf-8")
    except:
        try:
            import subprocess; subprocess.run(["pip","install","requests","--break-system-packages","-q"],capture_output=True)
            import requests as _rq; _CHARTJS_CODE = _rq.get("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js",timeout=15).text
        except:
            _CHARTJS_CODE = "/* CHART.JS FAILED */"

import _env as _env_module
ISC_BASE   = "https://gateway.isolarcloud.com.hk/openapi"
ISC_APPKEY = _env_module.get("ISC_APPKEY", "C7F86D8BAD458C1AC1E41C36F013E1E1")
ISC_SECRET = _env_module.get("ISC_SECRET", "dzv6fax07b6zu03vdsa5xfuy962va24z")
ISC_USER   = _env_module.get("ISC_USER", "service@aevoservice.com.br")
ISC_PASS   = _env_module.get("ISC_PASS", "")
ISC_RSA    = ("MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCfZcK8eOx6FL3BUe8BLnDdHxst"
              "YNOid5vboZarD2T-f4wxSyd1JBWGspE6XsjuX78EFAsgtN-QQK6RFs8KrfDCMVUxQ"
              "BotK3INjdBfis076AujjEv0lIuJv2agQOm_1PxuiqeXSkEAUg05bEsueaVOtPDKSp"
              "T7H3zF6WT6nfjbiQIDAQAB")
LOGO_B64   = "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"
MESES      = ["","Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
              "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

# â\x94\x80â\x94\x80 iSolarCloud â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80
def isc_headers(token=None):
    h = {"sys_code":"901","lang":"_pt_BR","x-access-key":ISC_SECRET,
         "x-random-access-key":str(uuid.uuid4()),"appkey":ISC_APPKEY,
         "Content-Type":"application/json"}
    if token: h["token"] = token
    return h

def isc_encrypt(password):
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    pub = ISC_RSA.replace("-","+").replace("_","/")
    pad = 4 - len(pub) % 4
    if pad != 4: pub += "=" * pad
    pem = "-----BEGIN PUBLIC KEY-----" + chr(10)
    pem += chr(10).join(pub[i:i+64] for i in range(0,len(pub),64))
    pem += chr(10) + "-----END PUBLIC KEY-----"
    key = RSA.import_key(pem)
    return base64.b64encode(PKCS1_v1_5.new(key).encrypt(password.encode())).decode()

@st.cache_data(ttl=3600)
def isc_login():
    try:
        r = requests.post(ISC_BASE+"/login", headers=isc_headers(),
            data=json.dumps({"user_account":ISC_USER,
                             "user_password":isc_encrypt(ISC_PASS),
                             "appkey":ISC_APPKEY}), timeout=30)
        resp = r.json()
        if resp.get("result_code") == "1":
            return resp["result_data"]["token"]
    except: pass
    return None

@st.cache_data(ttl=3600)
def isc_get_devices(ps_id, token):
    try:
        r = requests.post(ISC_BASE+"/getDeviceList",
            headers=isc_headers(token),
            data=json.dumps({"ps_id":str(ps_id),"curPage":1,"size":200,"appkey":ISC_APPKEY}),
            timeout=30)
        resp = r.json()
        if resp.get("result_code") == "1":
            return [d for d in resp.get("result_data",{}).get("pageList",[])
                    if d.get("device_type") == 1]
    except: pass
    return []

def isc_p2_fim_dia(ps_keys, data, token):
    ds=data.strftime("%Y%m%d")
    # Janelas em ordem de preferência: 23:50-23:59 (2 tentativas) → 15:00-17:59 (fallback)
    janelas=[(ds+"235000",ds+"235959"),(ds+"235000",ds+"235959"),(ds+"150000",ds+"175959")]
    for ini,fim in janelas:
        try:
            import time as _t; _t.sleep(0.2)
            r=requests.post(ISC_BASE+"/getDevicePointMinuteDataList",
                headers=isc_headers(token),
                data=json.dumps({"points":"p2","ps_key_list":ps_keys,
                    "start_time_stamp":ini,"end_time_stamp":fim,
                    "appkey":ISC_APPKEY,"curPage":1,"size":200}),timeout=30)
            resp=r.json()
            if resp.get("result_code")=="1":
                resultado={}
                for ps_key,leituras in resp.get("result_data",{}).items():
                    vals=[float(l.get("p2",0) or 0) for l in leituras if l.get("p2")]
                    if vals: resultado[ps_key]=max(vals)
                if resultado: return resultado
        except: pass
    return {}

@st.cache_data(ttl=1800)
def isc_energia_mensal(ps_id, ano, mes, token):
    dias_mes = calendar.monthrange(ano,mes)[1]
    inversores = isc_get_devices(ps_id, token)
    if not inversores: return pd.DataFrame(), "Sem inversores", set()
    ps_keys  = [d["ps_key"] for d in inversores]
    nome_map = {d["ps_key"]:d["device_name"] for d in inversores}
    modelo_map = {d["ps_key"]:d.get("device_model_code","") for d in inversores}
    data_ini = datetime(ano,mes,1) - timedelta(days=1)
    p2_hist  = {}
    progress = st.progress(0, text="Buscando dados iSolarCloud...")
    total = dias_mes + 1
    for i in range(total):
        data = data_ini + timedelta(days=i)
        p2d  = isc_p2_fim_dia(ps_keys, data, token)
        if p2d: p2_hist[data.date()] = p2d
        progress.progress(int((i+1)/total*100),
                          text="iSolarCloud: %s (%d/%d)" % (data.strftime("%d/%m"),i+1,total))
    progress.empty()
    if len(p2_hist) < 2: return pd.DataFrame(), "Dados insuficientes", set()
    # Filtrar inversores fantasma: se max(p2) = 0 em todo o historico → nunca gerou
    fantasmas = set()
    for pk in ps_keys:
        max_p2 = max((p2_hist.get(d,{}).get(pk,0) for d in p2_hist), default=0)
        if max_p2 <= 0:
            fantasmas.add(pk)
    if fantasmas:
        nomes_f = [nome_map.get(pk,pk) for pk in fantasmas]
        st.caption("Excluídos %d inversores fantasma (p2=0 no histórico): %s" % (len(fantasmas), ", ".join(nomes_f)))
        ps_keys = [pk for pk in ps_keys if pk not in fantasmas]
    datas = sorted(p2_hist.keys())
    rows  = []
    for i in range(1, len(datas)):
        d_ant, d_cur = datas[i-1], datas[i]
        if d_cur.month != mes or d_cur.year != ano: continue
        for ps_key in ps_keys:
            p_ant = p2_hist.get(d_ant,{}).get(ps_key)
            p_cur = p2_hist.get(d_cur,{}).get(ps_key)
            if p_ant is not None and p_cur is not None and p_cur >= p_ant:
                rows.append({"dia":d_cur,"inversor":nome_map.get(ps_key,ps_key),
                             "modelo":modelo_map.get(ps_key,""),
                             "energia_kwh":round((p_cur-p_ant)/1000,2)})
    if not rows: return pd.DataFrame(), "Sem energia", set()
    # ── Filtro fantasma 3 meses ──────────────────────────────────
    _en_por_inv={}
    for r in rows: _en_por_inv[r["inversor"]]=_en_por_inv.get(r["inversor"],0)+r["energia_kwh"]
    _susp_nomes=set(n for n,e in _en_por_inv.items() if e<=0)
    _susp_nomes|=set(nome_map.get(pk,pk) for pk in ps_keys)-set(_en_por_inv.keys())
    _fantasmas_3m=set()
    if _susp_nomes:
        _pk_de_nome={nome_map.get(pk,pk):pk for pk in ps_keys}
        _pk_susp=[_pk_de_nome[n] for n in _susp_nomes if n in _pk_de_nome]
        if _pk_susp:
            _p2_n1={pk:p2_hist.get(data_ini.date(),{}).get(pk,0) for pk in _pk_susp}
            _fim_n2=datetime(data_ini.year,data_ini.month,1)-timedelta(days=1)
            _p2_n2=isc_p2_fim_dia(_pk_susp,_fim_n2,token)
            _ainda=[pk for pk in _pk_susp if (_p2_n1.get(pk,0)-(_p2_n2.get(pk,0) or 0))<=0]
            if _ainda:
                _fim_n3=datetime(_fim_n2.year,_fim_n2.month,1)-timedelta(days=1)
                _p2_n3=isc_p2_fim_dia(_ainda,_fim_n3,token)
                _fantasmas_3m=set(pk for pk in _ainda if ((_p2_n2.get(pk,0) or 0)-(_p2_n3.get(pk,0) or 0))<=0)
            if _fantasmas_3m:
                _nf=sorted(nome_map.get(pk,pk) for pk in _fantasmas_3m)
                st.caption("Excluidos %d inversores fantasma (0 kWh em 3 meses): %s"%(len(_fantasmas_3m),", ".join(_nf)))
                _nf_set=set(_nf)
                rows=[r for r in rows if r["inversor"] not in _nf_set]
    if not rows: return pd.DataFrame(), "Sem energia", _fantasmas_3m
    return pd.DataFrame(rows), "iSolarCloud", _fantasmas_3m

# ── AEVO19: Classificação 5 estados via iSolarCloud ─────────────────────────
@st.cache_data(ttl=1800)
def isc_5estados_mensal(ps_id, ano, mes, token, excluir_pks=None):
    """AEVO19: p26 como indicador primário. Solar set mínimo 07:30. Sem COM."""
    LIMIAR_ON=0.5
    MODEL_THRESHOLDS={
        "SG125HV":{"vac_nom":615,"vac_sub":554,"vac_sob":677,"vdc_start":500,"vdc_voc":1200},
        "SG250HX":{"vac_nom":820,"vac_sub":738,"vac_sob":902,"vdc_start":500,"vdc_voc":1200},
        "SG333HX":{"vac_nom":830,"vac_sub":747,"vac_sob":913,"vdc_start":500,"vdc_voc":1200},
        "DEFAULT":{"vac_nom":615,"vac_sub":554,"vac_sob":677,"vdc_start":500,"vdc_voc":1200},
    }
    dias_mes=calendar.monthrange(ano,mes)[1]
    inversores=isc_get_devices(ps_id, token)
    if not inversores: return pd.DataFrame(),pd.DataFrame(),0.0,{},{}
    if excluir_pks:
        _exc=set(excluir_pks)
        inversores=[d for d in inversores if d["ps_key"] not in _exc]
        if not inversores: return pd.DataFrame(),pd.DataFrame(),0.0,{},{}
    ps_keys=[d["ps_key"] for d in inversores]
    nome_map={d["ps_key"]:d["device_name"] for d in inversores}
    modelo_map={}
    for d in inversores:
        mk="DEFAULT"
        raw=str(d.get("device_model_code","") or "").upper()
        for m in ["SG125HV","SG250HX","SG333HX"]:
            if m in raw: mk=m; break
        modelo_map[d["ps_key"]]=mk
    modelos_usina=sorted(set(modelo_map.values()))
    st.caption("AEVO19 — Modelos: %s — %d inversores"%(", ".join(modelos_usina), len(inversores)))
    n_inv=len(inversores)

    def _fetch(pt,ini,fim):
        try:
            import time as _t; _t.sleep(0.2)
            r=requests.post(ISC_BASE+"/getDevicePointMinuteDataList",
                headers=isc_headers(token),
                data=json.dumps({"points":pt,"ps_key_list":ps_keys,
                    "start_time_stamp":ini,"end_time_stamp":fim,
                    "appkey":ISC_APPKEY,"curPage":1,"size":5000}),timeout=30)
            resp=r.json()
            if resp.get("result_code")!="1": return {}
            out={}
            for pk,leituras in resp.get("result_data",{}).items():
                for l in leituras:
                    ts=l.get("time_stamp","")
                    if len(ts)<14: continue
                    hm=int(ts[8:12])
                    if hm<630 or hm>1800: continue
                    val=l.get(pt)
                    if val is not None and str(val) not in ("--","None",""):
                        try: out[(ts,pk)]=float(val)
                        except: out[(ts,pk)]=0.0
            return out
        except: return {}

    janelas=[]
    for d in range(1,dias_mes+1):
        ds="{}{:02d}{:02d}".format(ano,mes,d)
        for h0 in [6,9,12,15]:
            janelas.append((ds,h0,ds+"{:02d}0000".format(h0),ds+"{:02d}5959".format(h0+2)))

    # PASSO 1: p26
    progress=st.progress(0,text="AEVO19: Passo 1/2 — p26 (status)...")
    p26_data={}
    for i,(ds,h0,ini,fim) in enumerate(janelas):
        progress.progress(min(int((i+1)/len(janelas)*55),55),
            text="Passo 1/2: p26 %s %02d:00 (%d/%d)"%(ds,h0,i+1,len(janelas)))
        p26_data.update(_fetch("p26",ini,fim))
    if not p26_data:
        progress.empty(); return pd.DataFrame(),pd.DataFrame(),0.0,{},{}

    # Fantasmas
    pk_com_p26=set(pk for (_,pk) in p26_data.keys())
    fantasmas=set()
    for pk in ps_keys:
        if pk not in pk_com_p26:
            try:
                ds_mid="{}{:02d}15".format(ano,mes)
                _r=requests.post(ISC_BASE+"/getDevicePointMinuteDataList",
                    headers=isc_headers(token),
                    data=json.dumps({"points":"p2","ps_key_list":[pk],
                        "start_time_stamp":ds_mid+"110000","end_time_stamp":ds_mid+"125959",
                        "appkey":ISC_APPKEY,"curPage":1,"size":50}),timeout=15)
                _resp=_r.json()
                max_v=0
                if _resp.get("result_code")=="1":
                    for _k,_ls in _resp.get("result_data",{}).items():
                        for _l in _ls:
                            v=float(_l.get("p2",0) or 0)
                            if v>max_v: max_v=v
                if max_v<=0: fantasmas.add(pk)
            except: fantasmas.add(pk)
    if fantasmas:
        nf=[nome_map.get(pk,pk) for pk in fantasmas]
        st.caption("Excluídos %d inversores fantasma: %s"%(len(fantasmas),", ".join(nf)))
        ps_keys=[pk for pk in ps_keys if pk not in fantasmas]
        n_inv=len(ps_keys)
        p26_data={(t,p):v for (t,p),v in p26_data.items() if p not in fantasmas}

    # Solar set POR DIA: min(primeiro ON, 07:30) → max(último ON, 17:30)
    import collections
    dias_on=collections.defaultdict(list)
    for (t,p),v in p26_data.items():
        if v>LIMIAR_ON: dias_on[t[:8]].append(t)
    solar_set=set()
    for dia_s in sorted(dias_on.keys()):
        ts_list=sorted(dias_on[dia_s])
        first_on=ts_list[0] if ts_list else dia_s+"073000"
        last_on=ts_list[-1] if ts_list else dia_s+"173000"
        solar_start=min(first_on, dia_s+"073000")
        solar_end=max(last_on, dia_s+"173000")
        for hh in range(6,19):
            for mm in range(0,60,5):
                t="{}{:02d}{:02d}00".format(dia_s,hh,mm)
                if solar_start<=t<=solar_end:
                    solar_set.add(t)
    # Dias SEM nenhum ON: solar set 07:30-17:30
    all_dias=set(t[:8] for t,_ in p26_data.keys())
    for dia_s in all_dias:
        if dia_s not in dias_on:
            for hh in range(7,18):
                for mm in range(0,60,5):
                    t="{}{:02d}{:02d}00".format(dia_s,hh,mm)
                    hhmm=int(t[8:12])
                    if 730<=hhmm<=1730: solar_set.add(t)
    st.caption("Solar set: %d timestamps válidos"%len(solar_set))

    # Janelas com parada
    janelas_problema=set()
    for t in solar_set:
        for pk in ps_keys:
            v=p26_data.get((t,pk))
            if v is None or v<=LIMIAR_ON:
                janelas_problema.add(t[:10]); break

    # PASSO 2: p5+p15 para paradas
    p5_data={}; p15_data={}
    if janelas_problema:
        jprob=[(ds,h0,ini,fim) for ds,h0,ini,fim in janelas
               if any(ds+"{:02d}".format(h0+dh) in janelas_problema for dh in range(3))]
        st.caption("Passo 2: %d janelas com paradas → buscando p5+p15"%len(jprob))
        for i,(ds,h0,ini,fim) in enumerate(jprob):
            progress.progress(55+min(int((i+1)/max(len(jprob),1)*44),44),
                text="Passo 2/2: p5+p15 %s %02d:00 (%d/%d)"%(ds,h0,i+1,len(jprob)))
            p5_data.update(_fetch("p5",ini,fim))
            p15_data.update(_fetch("p15",ini,fim))

    progress.progress(100,text="AEVO19: Classificando...")

    # Partida por inversor por dia: primeiro p26=0 → primeiro p26>0.5
    # Se volta EMPTY após p26=0 → falha na partida → tracking desde p26=0
    # Se 07:30 sem nunca p26=0 → tracking desde 07:30
    inv_tracking={}  # {(pk,dia): tracking_start_ts}
    for pk in ps_keys:
        pk_ts=sorted(set(t for (t,p) in p26_data.keys() if p==pk))
        dias_inv=sorted(set(t[:8] for t in pk_ts))
        for dia_s in dias_inv:
            first_zero=None; first_on=None
            for hh in range(6,19):
                for mm in range(0,60,5):
                    t="{}{:02d}{:02d}00".format(dia_s,hh,mm)
                    v=p26_data.get((t,pk))
                    hhmm=t[8:12]
                    if v is not None and v<=LIMIAR_ON and first_zero is None:
                        first_zero=t
                    if v is not None and v>LIMIAR_ON and first_on is None:
                        first_on=t; break
                    if first_zero and v is None and hhmm>"0700":
                        inv_tracking[(pk,dia_s)]=first_zero; break
                    if hhmm>="0730" and first_zero is None and first_on is None:
                        inv_tracking[(pk,dia_s)]=dia_s+"073000"; break
                if (pk,dia_s) in inv_tracking or first_on: break
            if (pk,dia_s) not in inv_tracking:
                if first_on: inv_tracking[(pk,dia_s)]=first_on
                elif first_zero: inv_tracking[(pk,dia_s)]=first_zero
                else: inv_tracking[(pk,dia_s)]=dia_s+"073000"

    # Declínio: último p26>0.5 por inversor por dia
    inv_last_on={}
    for pk in ps_keys:
        for dia_s in sorted(set(t[:8] for (t,p) in p26_data.keys() if p==pk)):
            on_ts=[t for (t,p),v in p26_data.items() if p==pk and t[:8]==dia_s and v>LIMIAR_ON]
            if on_ts: inv_last_on[(pk,dia_s)]=max(on_ts)

    # Classificar
    rows=[]
    for t in solar_set:
        dia_s=t[:8]
        for pk in ps_keys:
            track=inv_tracking.get((pk,dia_s))
            last=inv_last_on.get((pk,dia_s))
            if track and t<track: continue
            if last and t>last: continue
            v26=p26_data.get((t,pk))
            is_on=(v26 is not None and v26>LIMIAR_ON)
            is_empty=(v26 is None)
            n_off=sum(1 for pk2 in ps_keys if p26_data.get((t,pk2)) is None or p26_data.get((t,pk2),0)<=LIMIAR_ON)
            maioria_off=n_off/max(len(ps_keys),1)>0.50
            if is_on:
                estado="GER"
            else:
                mk=modelo_map.get(pk,"DEFAULT")
                thr=MODEL_THRESHOLDS[mk]
                vdc=p5_data.get((t,pk)) or 0
                vac=p15_data.get((t,pk)) or 0
                if is_empty and vdc==0:
                    estado="OFR" if maioria_off else "OFM"
                elif vdc<thr["vdc_start"]:
                    estado="IRR"
                elif vac>50:
                    if vac>thr["vac_sob"]: estado="SOB"
                    elif vac<thr["vac_sub"]: estado="SUB"
                    elif maioria_off: estado="OFR"
                    else: estado="OFM"
                elif vdc>thr["vdc_voc"] and maioria_off: estado="OFR"
                elif vdc>thr["vdc_voc"]: estado="OFM"
                elif vdc<=0: estado="DES"
                elif maioria_off: estado="OFR"
                else: estado="OFM"
            rows.append({"ts":t,"ps_key":pk,"inv":nome_map.get(pk,pk),
                         "p26":v26 if v26 is not None else -1,
                         "estado":estado,"dia":dia_s})
    if not rows:
        progress.empty(); return pd.DataFrame(),pd.DataFrame(),0.0,{},{}

    df=pd.DataFrame(rows).sort_values(["ps_key","ts"]).reset_index(drop=True)

    # KPIs
    resultados=[]; paradas=[]
    causa_map={"SOB":"Sobretensao CA","SUB":"Subtensao CA",
               "DES":"Desconexao total","OFR":"OFF (rede/coletivo)",
               "OFM":"OFF (equipamento/trip)","GER":"Gerando",
               "IRR":"Baixa irradiacao"}
    resp_map={"SOB":"Concessionaria","SUB":"Concessionaria",
              "DES":"Equipamento / O&M","OFR":"Concessionaria",
              "OFM":"Equipamento / O&M","GER":"Normal",
              "IRR":"Normal (clima)"}
    for pk in df["ps_key"].unique():
        di=df[df["ps_key"]==pk].copy()
        nome=nome_map.get(pk,pk); total=len(di)
        if total==0: continue
        n_ger=len(di[di["estado"]=="GER"])
        n_irr=len(di[di["estado"]=="IRR"])
        n_conc=len(di[di["estado"].isin(["SOB","SUB","OFR"])])
        n_om=len(di[di["estado"].isin(["DES","OFM"])])
        disp=round((n_ger+n_irr)/total*100,2)
        resultados.append({"inversor":nome,"intervalos_solar":total,
            "disp_op_pct":disp,"horas_off":round((n_conc+n_om)*5/60,2),
            "pct_ger_pure":round(n_ger/total*100,2),
            "pct_conc":round(n_conc/total*100,2),"pct_om":round(n_om/total*100,2),
            "pct_com":0.0,"pct_irr":round(n_irr/total*100,2)})
        di=di.sort_values("ts").reset_index(drop=True)
        di["is_off"]=~di["estado"].isin(["GER","IRR"])
        di["bloco"]=(di["is_off"]!=di["is_off"].shift()).cumsum()
        for _,grp in di[di["is_off"]].groupby("bloco"):
            cp=grp["estado"].value_counts().index[0]
            try:
                from datetime import datetime as _dt
                ini_dt=_dt.strptime(grp["ts"].min()[:14],"%Y%m%d%H%M%S")
                fim_dt=_dt.strptime(grp["ts"].max()[:14],"%Y%m%d%H%M%S")+timedelta(minutes=5)
                ini_f=ini_dt.strftime("%d/%m/%Y %H:%M"); fim_f=fim_dt.strftime("%d/%m/%Y %H:%M")
            except: ini_f=grp["ts"].min(); fim_f=grp["ts"].max()
            paradas.append({"inversor":nome,"inicio":ini_f,"fim":fim_f,
                "duracao_h":round(len(grp)*5/60,4),
                "tipo":"Parada",
                "causa":causa_map.get(cp,cp),"responsavel":resp_map.get(cp,"?")})

    df_disp=pd.DataFrame(resultados)
    df_par=pd.DataFrame(paradas).sort_values("inicio") if paradas else pd.DataFrame()
    disp_media=round(float(df_disp["disp_op_pct"].mean()),2) if not df_disp.empty else 0.0
    kpis_5est={}
    if not df_disp.empty:
        kpis_5est={"pct_geracao":round(float(df_disp["disp_op_pct"].mean()),2),
            "pct_ger_pure":round(float(df_disp["pct_ger_pure"].mean()),2),
            "pct_conc":round(float(df_disp["pct_conc"].mean()),2),
            "pct_om":round(float(df_disp["pct_om"].mean()),2),
            "pct_com":0.0,
            "pct_irr":round(float(df_disp["pct_irr"].mean()),2),"tier":1}
    progress.empty()
    disp_dia_inv={}
    for (pk,dia_s),grp in df.groupby(["ps_key","dia"]):
        nome=nome_map.get(pk,pk)
        n_total=len(grp); n_on=len(grp[grp["estado"].isin(["GER","IRR"])])
        d_int=int(dia_s[6:8])
        if d_int not in disp_dia_inv: disp_dia_inv[d_int]={}
        disp_dia_inv[d_int][nome]=round(n_on/max(n_total,1)*100,1)
    return df_disp,df_par,disp_media,kpis_5est,disp_dia_inv


# â\x94\x80â\x94\x80 Banco â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80
def get_conn():
    return psycopg2.connect(
        host=_env_module.get("AEVO_HOST","shinkansen.proxy.rlwy.net"),
        port=int(_env_module.get("AEVO_PORT","18796")),
        dbname=_env_module.get("AEVO_DB","railway"),
        user=_env_module.get("AEVO_USER","powerbi_readonly_user"),
        password=_env_module.get("AEVO_PASSWORD",""))

def sql(q):
    conn=get_conn(); df=pd.read_sql(q,conn); conn.close(); return df

@st.cache_data(ttl=600)
def get_asset_names(pid):
    return sql("SELECT id,name FROM public.device_asset WHERE plant_id="+str(pid))

@st.cache_data(ttl=600)
def get_ws_ids(pid):
    df=sql("SELECT da.id FROM public.device_asset da "
           "JOIN public.device_asset_type dat ON da.asset_type_id=dat.id "
           "WHERE da.plant_id="+str(pid)+" AND dat.scada_name="+chr(39)+"ws"+chr(39))
    return df["id"].tolist()

@st.cache_data(ttl=600)
def get_inv_ids(pid):
    return sql("SELECT da.id,da.name FROM public.device_asset da "
               "JOIN public.device_asset_type dat ON da.asset_type_id=dat.id "
               "WHERE da.plant_id="+str(pid)+" AND dat.scada_name="+chr(39)+"inv"+chr(39)+" ORDER BY da.name")

def load_pvsyst(pid,ano,mes):
    return sql("SELECT DISTINCT ON (pd.year,pd.month) "
               "pd.e_grid,pd.pr,pd.glob_inc,pd.glob_hor,pd.p50,pd.p75,pd.p90 "
               "FROM public.pvsyst_data pd "
               "WHERE pd.pvsyst_file_id=(SELECT pvsyst_file_id FROM public.plant_plant WHERE id="+str(pid)+") "
               "AND pd.year="+str(ano)+" AND pd.month="+str(mes)+" ORDER BY pd.year,pd.month,pd.id")

def load_alertas(pid,ano,mes):
    inv_ids=get_inv_ids(pid)
    if inv_ids.empty: return pd.DataFrame()
    ids_str=",".join(str(i) for i in inv_ids["id"].tolist())
    if not ids_str: return pd.DataFrame()
    return sql("SELECT ae.name tipo,da.name ativo,"
               "TO_CHAR(aa.created_at AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+","+chr(39)+"DD/MM/YYYY HH24:MI"+chr(39)+") inicio,"
               "TO_CHAR(aa.closed_at  AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+","+chr(39)+"DD/MM/YYYY HH24:MI"+chr(39)+") fim,"
               "ROUND(EXTRACT(EPOCH FROM (COALESCE(aa.closed_at,NOW())-aa.created_at))/3600.0,1) horas,"
               "CASE WHEN aa.closed_at IS NULL THEN "+chr(39)+"Aberto"+chr(39)+" ELSE "+chr(39)+"Fechado"+chr(39)+" END status "
               "FROM public.alert_alert aa "
               "JOIN public.alert_errortype ae ON aa.error_type_id=ae.id "
               "JOIN public.device_asset da ON aa.asset_id=da.id "
               "WHERE aa.asset_id IN ("+ids_str+") "
               "AND EXTRACT(YEAR FROM aa.created_at)="+str(ano)+" "
               "AND EXTRACT(MONTH FROM aa.created_at)="+str(mes)+" "
               "AND NOT ("
               "  EXTRACT(HOUR FROM aa.created_at AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+") >= 17"
               "  AND aa.closed_at IS NOT NULL"
               "  AND EXTRACT(HOUR FROM aa.closed_at AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+") < 8"
               "  AND DATE(aa.closed_at AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+") = DATE(aa.created_at AT TIME ZONE "+chr(39)+"America/Sao_Paulo"+chr(39)+") + 1"
               ") "
               "ORDER BY horas DESC")

def load_inverter_daily_banco(pid,ano,mes):
    """Fallback para o AEVO. A tabela public.inverter_daily_energy nao existe
    no schema atual — retorna DF vazio para o caller fazer fallback gracioso."""
    try:
        return sql("SELECT ide.day::date AS dia,ide.device_id,da.name AS inversor,"
                   "ROUND(ide.daily_energy::numeric,2) AS energia_kwh "
                   "FROM public.inverter_daily_energy ide "
                   "LEFT JOIN public.device_asset da ON ide.device_id=da.id "
                   "WHERE ide.device_plant_id="+str(pid)+" "
                   "AND EXTRACT(YEAR FROM ide.day)="+str(ano)+" "
                   "AND EXTRACT(MONTH FROM ide.day)="+str(mes)+" "
                   "ORDER BY ide.day,da.name")
    except Exception:
        return pd.DataFrame()

def load_poa_banco(pid,ano,mes):
    """Busca POA medido do banco (sensor_reading dp=42) e GHI (dp=40)"""
    ws_ids=get_ws_ids(pid)
    if not ws_ids: return 0.0, 0.0
    ws_str=",".join(str(i) for i in ws_ids)
    dt=str(ano)+"-"+str(mes).zfill(2)+"-01"
    df=sql("SELECT sr.device_datapoint_id dpid,"
           "ROUND((SUM(GREATEST(sr.value,0))*5.0/60.0/1000.0)::numeric,2) kwh_m2 "
           "FROM public.sensor_reading sr "
           "WHERE sr.asset_id IN ("+ws_str+") "
           "AND sr.device_datapoint_id IN (40,42) "
           "AND sr.ts >= "+chr(39)+dt+chr(39)+" "
           "AND sr.ts < "+chr(39)+dt+chr(39)+"::date + INTERVAL "+chr(39)+"1 month"+chr(39)+" "
           "GROUP BY sr.device_datapoint_id")
    poa_banco = float(df[df["dpid"]==42]["kwh_m2"].values[0]) if not df[df["dpid"]==42].empty else 0.0
    ghi_banco = float(df[df["dpid"]==40]["kwh_m2"].values[0]) if not df[df["dpid"]==40].empty else 0.0
    return poa_banco, ghi_banco

def load_poa_diaria(pid,ano,mes):
    ws_ids=get_ws_ids(pid)
    if not ws_ids: return pd.DataFrame()
    ws_str=",".join(str(i) for i in ws_ids)
    dt=str(ano)+"-"+str(mes).zfill(2)+"-01"
    return sql("SELECT DATE(sr.ts) dia,"
               "ROUND((SUM(GREATEST(sr.value,0))*5.0/60.0/1000.0)::numeric,2) kwh_m2 "
               "FROM public.sensor_reading sr "
               "WHERE sr.asset_id IN ("+ws_str+") "
               "AND sr.device_datapoint_id=42 "
               "AND sr.ts >= "+chr(39)+dt+chr(39)+" "
               "AND sr.ts < "+chr(39)+dt+chr(39)+"::date + INTERVAL "+chr(39)+"1 month"+chr(39)+" "
               "GROUP BY DATE(sr.ts) ORDER BY dia")

def load_disp_operacao(pid,ano,mes):
    df_inv_assets=get_inv_ids(pid)
    if df_inv_assets.empty: return pd.DataFrame(),pd.DataFrame(),0.0
    inv_ids=",".join(str(i) for i in df_inv_assets["id"].tolist())
    dt=str(ano)+"-"+str(mes).zfill(2)+"-01"
    try:
        # Buscar ts em UTC puro â\x80\x94 converter no pandas para evitar problemas de tz
        df_pow=sql("SELECT sr.asset_id,"
                   "EXTRACT(EPOCH FROM sr.ts) AS ts_epoch,"
                   "ROUND(sr.value::numeric,3) AS kw "
                   "FROM public.sensor_reading sr "
                   "WHERE sr.asset_id IN ("+inv_ids+") "
                   "AND sr.device_datapoint_id=4 "
                   "AND sr.ts >= "+chr(39)+dt+chr(39)+" "
                   "AND sr.ts < "+chr(39)+dt+chr(39)+"::date + INTERVAL "+chr(39)+"1 month"+chr(39)+" "
                   "ORDER BY sr.ts,sr.asset_id")
    except: return pd.DataFrame(),pd.DataFrame(),0.0
    if df_pow.empty: return pd.DataFrame(),pd.DataFrame(),0.0

    # Converter epoch para datetime local (America/Sao_Paulo = UTC-3)
    import pytz
    tz_sp = pytz.timezone("America/Sao_Paulo")
    df_pow["ts"] = pd.to_datetime(df_pow["ts_epoch"], unit="s", utc=True).dt.tz_convert(tz_sp).dt.tz_localize(None)
    df_pow = df_pow.drop(columns=["ts_epoch"])

    # Periodo solar: hora local 06:30-17:30 E minimo 30% dos inversores gerando
    df_pow["hm"] = df_pow["ts"].dt.hour * 100 + df_pow["ts"].dt.minute
    df_pow_solar = df_pow[(df_pow["hm"]>=630) & (df_pow["hm"]<=1730)]
    # Solar set: timestamp so entra se >= 30% dos inversores estiverem com kw > 0.05
    contagem_ts  = df_pow_solar[df_pow_solar["kw"]>0.05].groupby("ts")["asset_id"].nunique()
    min_inv      = int(len(df_inv_assets) * 0.30)
    if min_inv < 1: min_inv = 1
    solar_set    = set(contagem_ts[contagem_ts >= min_inv].index.tolist())

    dias_mes=calendar.monthrange(ano,mes)[1]
    nome_map=dict(zip(df_inv_assets["id"],df_inv_assets["name"]))
    resultados=[]; paradas=[]
    for aid in df_inv_assets["id"].tolist():
        nome=nome_map.get(aid,str(aid))
        df_i=df_pow[df_pow["asset_id"]==aid].copy()
        df_i=df_i.groupby("ts")["kw"].mean().reset_index()
        # Filtrar apenas timestamps do periodo solar
        df_i=df_i[df_i["ts"].isin(solar_set)].sort_values("ts").reset_index(drop=True)
        if df_i.empty: continue
        total_solar=len(df_i)
        df_i["off"]=df_i["kw"]<=0.05
        df_i["bloco"]=(df_i["off"]!=df_i["off"].shift()).cumsum()
        intervalos_off=0
        for bloco_id,grp in df_i[df_i["off"]].groupby("bloco"):
            if len(grp)>=1:  # parada >= 5 minutos
                intervalos_off+=len(grp)
                paradas.append({
                    "inversor":nome,
                    "inicio":grp["ts"].min().strftime("%d/%m/%Y %H:%M"),
                    "fim":(grp["ts"].max() + pd.Timedelta(minutes=5)).strftime("%d/%m/%Y %H:%M"),
                    "duracao_h":round(len(grp)*5/60,4),
                    "tipo":"Parada Parcial (sensor)"
                })
        disp=round((1-intervalos_off/total_solar)*100,2) if total_solar else 0.0
        resultados.append({"inversor":nome,"asset_id":aid,"intervalos_solar":total_solar,
                           "horas_off":round(intervalos_off*5/60,2),"disp_op_pct":disp})
    df_disp=pd.DataFrame(resultados)
    df_par=pd.DataFrame(paradas).sort_values("inicio") if paradas else pd.DataFrame()
    disp_media=round(float(df_disp["disp_op_pct"].mean()),2) if not df_disp.empty else 0.0
    return df_disp,df_par,disp_media

def resolve_poa(poa_manual, poa_banco, glob_inc, glob_hor, ghi_banco):
    """
    Cascata de resolucao do POA:
    1. POA informado manualmente pelo time
    2. POA do banco (sensor dp=42)
    3. POA estimado via fator PVsyst (GHI_banco x glob_inc/glob_hor)
    4. Sem POA (PR nao calculado)
    Retorna: (poa_valor, fonte_poa)
    """
    if poa_manual > 0:
        return poa_manual, "Manual (time)"
    if poa_banco > 0:
        return poa_banco, "Banco (sensor dp=42)"
    if ghi_banco > 0 and glob_hor > 0:
        fator = glob_inc / glob_hor
        return round(ghi_banco * fator, 2), "Estimado (GHI banco x fator PVsyst)"
    return 0.0, "Sem POA"

def calc_kpis(df_daily, dias_mes, kwp, poa, pvsyst, df_disp_op):
    if df_daily.empty: return {}
    agg_dict = {"energia_kwh":("energia_kwh","sum"),"dias_com_dado":("dia","count")}
    if "modelo" in df_daily.columns:
        agg_dict["modelo"]=("modelo","first")
    df_inv=df_daily.groupby("inversor").agg(**agg_dict).reset_index()
    df_inv["energia_kwh"]=df_inv["energia_kwh"].round(2)
    total=df_inv["energia_kwh"].sum()
    df_inv["pct"]=(df_inv["energia_kwh"]/total*100).round(1) if total else 0
    df_inv["esp_kwh_kwp"]=(df_inv["energia_kwh"]/(kwp/len(df_inv))).round(2) if (kwp and len(df_inv)) else 0
    df_inv["disp_ger_pct"]=(df_inv["dias_com_dado"]/dias_mes*100).round(1)
    if not df_disp_op.empty:
        df_inv=df_inv.merge(df_disp_op[["inversor","disp_op_pct","horas_off"]],on="inversor",how="left")
        df_inv["disp_op_pct"]=df_inv["disp_op_pct"].fillna(0.0)
        df_inv["horas_off"]=df_inv["horas_off"].fillna(0.0)
    else:
        df_inv["disp_op_pct"]=0.0; df_inv["horas_off"]=0.0
    df_inv=df_inv.sort_values("energia_kwh",ascending=False).reset_index(drop=True)
    energia_real=float(total)
    dias_com_dado=df_daily["dia"].nunique()
    cob_pct=round(dias_com_dado/dias_mes*100,1)
    disp_ger=float(df_inv["disp_ger_pct"].mean()) if len(df_inv) else 0
    # PR = Energia / (POA medido x kWp)
    pr_real=(energia_real/(poa*kwp)) if (poa>0 and kwp>0) else 0
    esp_kwp=(energia_real/kwp) if kwp else 0
    ee  =float(pvsyst.get("e_grid") or 0) if pvsyst else 0
    pr_e=float(pvsyst.get("pr") or 0) if pvsyst else 0
    p50 =float(pvsyst.get("p50") or 0) if pvsyst else 0
    p75 =float(pvsyst.get("p75") or 0) if pvsyst else 0
    glob_inc=float(pvsyst.get("glob_inc") or 0) if pvsyst else 0
    at=round(energia_real/ee*100,1) if ee else 0
    # Variacao POA medido vs PVsyst
    var_poa=round((poa-glob_inc)/glob_inc*100,1) if (poa>0 and glob_inc>0) else 0
    df_dia=df_daily.groupby("dia")["energia_kwh"].sum().reset_index()
    return {"energia_real":energia_real,"ee":ee,"at":at,"pr_real":pr_real,"pr_e":pr_e,
            "esp_kwp":esp_kwp,"disp_ger":disp_ger,"glob_inc":glob_inc,"p50":p50,"p75":p75,
            "dias_com_dado":dias_com_dado,"cob_pct":cob_pct,"df_inv":df_inv,"df_dia":df_dia,
            "var_poa":var_poa}

import json as _json

def mk_chart(type_,labels,datasets,extra=None):
    cfg={"type":type_,"data":{"labels":labels,"datasets":datasets},
         "options":{"responsive":True,"maintainAspectRatio":False,
                    "plugins":{"legend":{"position":"top","labels":{"boxWidth":10,"font":{"size":8}}}},
                    "scales":{"x":{"ticks":{"font":{"size":8}},"grid":{"display":False}},
                              "y":{"ticks":{"font":{"size":8}},"beginAtZero":True}}}}
    if extra:
        for k,v in extra.items():
            if k=="scales": cfg["options"]["scales"].update(v)
            elif k=="plugins": cfg["options"]["plugins"].update(v)
            else: cfg["options"][k]=v
    return _json.dumps(cfg,ensure_ascii=False)

def chart_inv(df_inv):
    labels=df_inv["inversor"].tolist()
    vals=[round(float(v),0) for v in df_inv["energia_kwh"]]
    media=round(float(df_inv["energia_kwh"].mean()),0)
    return mk_chart("bar",labels,[
        {"label":"Energia (kWh)","data":vals,"backgroundColor":"rgba(15,158,213,0.75)","borderWidth":0},
        {"label":"Media","data":[media]*len(labels),"type":"line","borderColor":"#E97132","borderWidth":2,"pointRadius":0,"fill":False}])

def chart_desvios(kpis,poa,pvsyst):
    ee  =float(pvsyst.get("e_grid") or 0) if pvsyst else 0
    pr_e=float(pvsyst.get("pr") or 0) if pvsyst else 0
    glob_inc=float(pvsyst.get("glob_inc") or 0) if pvsyst else 0
    er=kpis.get("energia_real",0); pr_r=kpis.get("pr_real",0); dg=kpis.get("disp_ger",0)
    devs=[round((er-ee)/ee*100,1) if ee else 0,
          round((pr_r-pr_e)/pr_e*100,1) if pr_e else 0,
          round((poa-glob_inc)/glob_inc*100,1) if (poa and glob_inc) else 0,
          round(dg-100,1)]
    cores=["rgba(231,76,60,0.8)" if d<0 else "rgba(39,174,96,0.8)" for d in devs]
    return mk_chart("bar",["Energia","PR","Irradiacao POA","Cobertura"],[
        {"label":"Desvio (%)","data":devs,"backgroundColor":cores,"borderWidth":0}],
        {"plugins":{"legend":{"display":False}}})

def chart_disp(df_daily,dias_mes,ano,mes):
    all_days=pd.date_range(str(ano)+"-"+str(mes).zfill(2)+"-01",periods=dias_mes,freq="D").date
    df_piv=df_daily.pivot_table(index="dia",columns="inversor",values="energia_kwh",aggfunc="sum")
    df_piv.index=pd.to_datetime(df_piv.index).date
    df_piv=df_piv.reindex(all_days).fillna(0)
    cores=["#0F9ED5","#E97132","#27ae60","#8e44ad","#e74c3c","#f39c12","#156082","#0E2841"]
    datasets=[{"label":col,"data":[1 if float(v)>0 else 0 for v in df_piv[col]],
               "backgroundColor":cores[i%len(cores)],"borderWidth":0,"barPercentage":0.9}
              for i,col in enumerate(df_piv.columns)]
    return mk_chart("bar",[str(d.day) for d in all_days],datasets,
        {"scales":{"x":{"stacked":True,"ticks":{"font":{"size":7}},"grid":{"display":False}},
                   "y":{"stacked":True,"max":len(df_piv.columns),
                        "title":{"display":True,"text":"Inversores","font":{"size":8}},
                        "ticks":{"font":{"size":7}}}},
         "plugins":{"legend":{"position":"bottom","labels":{"boxWidth":8,"font":{"size":7}}}}})

def chart_disp_5est(disp_dia_inv,dias_mes,ano,mes,df_daily=None):
    """Stacked bar: inversor disponivel se p26>0.5 OU energia>0."""
    if not disp_dia_inv: return "{}"
    all_invs=sorted(set(inv for dia_dict in disp_dia_inv.values() for inv in dia_dict))
    if not all_invs: return "{}"
    _en={}
    if df_daily is not None and not df_daily.empty:
        for _,r in df_daily.iterrows():
            _dd=r["dia"]; _di=int(_dd.strftime("%d")) if hasattr(_dd,"strftime") else int(str(_dd)[8:10])
            _inv=str(r["inversor"])
            if _di not in _en: _en[_di]={}
            _en[_di][_inv]=_en[_di].get(_inv,0)+float(r["energia_kwh"])
    cores=["#0F9ED5","#E97132","#27ae60","#8e44ad","#e74c3c","#f39c12","#156082","#0E2841"]
    datasets=[]
    for i,inv in enumerate(all_invs):
        data=[]
        for d in range(1,dias_mes+1):
            pct=disp_dia_inv.get(d,{}).get(inv,0)
            en=_en.get(d,{}).get(inv,0)
            data.append(1 if (pct>=50 or en>0) else 0)
        datasets.append({"label":inv,"data":data,
            "backgroundColor":cores[i%len(cores)],"borderWidth":0,"barPercentage":0.9})
    return mk_chart("bar",[str(d) for d in range(1,dias_mes+1)],datasets,
        {"scales":{"x":{"stacked":True,"ticks":{"font":{"size":7}},"grid":{"display":False}},
                   "y":{"stacked":True,"max":len(all_invs),
                        "title":{"display":True,"text":"Inversores","font":{"size":8}},
                        "ticks":{"font":{"size":7}}}},
         "plugins":{"legend":{"position":"bottom","labels":{"boxWidth":8,"font":{"size":7}}}}})

def chart_ger_dia(df_dia,dias_mes,ano,mes):
    all_days=pd.date_range(str(ano)+"-"+str(mes).zfill(2)+"-01",periods=dias_mes,freq="D").date
    df2=df_dia.copy(); df2["dia"]=pd.to_datetime(df2["dia"]).dt.date
    en_dict=dict(zip(df2["dia"],df2["energia_kwh"]))
    vals=[float(en_dict.get(d,0)) for d in all_days]
    media=round(sum(v for v in vals if v>0)/max(sum(1 for v in vals if v>0),1),0)
    return mk_chart("bar",[str(d.day) for d in all_days],[
        {"label":"Geracao (kWh)","data":vals,"backgroundColor":"rgba(15,158,213,0.7)","borderWidth":0},
        {"label":"Media","data":[media]*dias_mes,"type":"line","borderColor":"#E97132","borderWidth":2,"pointRadius":0,"fill":False}])

def chart_ger_dia_alert(df_dia,dias_mes,ano,mes,alert_dias=None):
    """Geração diária com barras de alerta em amber para dias anômalos."""
    all_days=pd.date_range(str(ano)+"-"+str(mes).zfill(2)+"-01",periods=dias_mes,freq="D").date
    df2=df_dia.copy(); df2["dia"]=pd.to_datetime(df2["dia"]).dt.date
    en_dict=dict(zip(df2["dia"],df2["energia_kwh"]))
    vals=[float(en_dict.get(d,0)) for d in all_days]
    media=round(sum(v for v in vals if v>0)/max(sum(1 for v in vals if v>0),1),0)
    alert_set=set(alert_dias or [])
    cores=[("#EF9F27" if (d.day in alert_set) else "rgba(15,158,213,0.7)") for d in all_days]
    bordas=[("#BA7517" if (d.day in alert_set) else "transparent") for d in all_days]
    bwidths=[(2 if (d.day in alert_set) else 0) for d in all_days]
    return mk_chart("bar",[str(d.day) for d in all_days],[
        {"label":"Geracao (kWh)","data":vals,"backgroundColor":cores,"borderColor":bordas,"borderWidth":bwidths},
        {"label":"Media","data":[media]*dias_mes,"type":"line","borderColor":"#E97132","borderWidth":2,"pointRadius":0,"fill":False}])

def chart_poa_dia(df_poa_dia,glob_inc_dia,dias_mes,ano,mes):
    all_days=pd.date_range(str(ano)+"-"+str(mes).zfill(2)+"-01",periods=dias_mes,freq="D").date
    irr_dict={}
    if not df_poa_dia.empty:
        df2=df_poa_dia.copy(); df2["dia"]=pd.to_datetime(df2["dia"]).dt.date
        irr_dict=dict(zip(df2["dia"],df2["kwh_m2"]))
    vals=[float(irr_dict.get(d,0)) for d in all_days]
    return mk_chart("bar",[str(d.day) for d in all_days],[
        {"label":"POA Medido (kWh/m2)","data":vals,"backgroundColor":"rgba(15,158,213,0.7)","borderWidth":0},
        {"label":"Esperado PVsyst","data":[round(glob_inc_dia,2)]*dias_mes,"type":"line",
         "borderColor":"#E97132","borderWidth":2,"pointRadius":0,"fill":False}])


CSS = '@page{size:A4 landscape;margin:0}*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,Helvetica,sans-serif;font-size:9px;color:#17324A;background:white;width:297mm;height:210mm;overflow:hidden}.capa{width:297mm;height:210mm;display:flex;flex-direction:row;background:linear-gradient(135deg,#0E2841 0%,#156082 55%,#0F9ED5 100%);page-break-after:always;break-after:page}.capa-left{flex:1.5;padding:14mm 12mm 10mm 14mm;display:flex;flex-direction:column;justify-content:space-between}.capa-right{flex:1;padding:14mm 14mm 10mm 0;display:flex;align-items:stretch}.capa-card{flex:1;background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.18);border-radius:12px;padding:14px 18px;display:flex;flex-direction:column;justify-content:center;gap:12px}.logo-area{display:flex;align-items:center;gap:8px}.brand-name{color:white;font-size:11px;font-weight:700;letter-spacing:.5px}.main-info{flex:1;display:flex;flex-direction:column;justify-content:center;padding:8mm 0 4mm}.tag-badge{display:inline-block;padding:3px 12px;border-radius:999px;background:rgba(255,255,255,.15);color:white;font-size:7.5px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;width:fit-content}.usina-nome{font-size:32px;font-weight:700;color:white;line-height:1.05;margin-bottom:4px}.periodo{font-size:15px;font-weight:400;color:#0F9ED5;margin-bottom:14px}.divider{width:36px;height:3px;background:#E97132;border-radius:2px;margin-bottom:14px}.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 20px}.meta-item label{display:block;color:rgba(255,255,255,.5);font-size:7px;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px}.meta-item p{color:white;font-size:11px;font-weight:700;line-height:1.2}.footer-capa{color:rgba(255,255,255,.3);font-size:7.5px}.kpi-main{display:flex;flex-direction:column;gap:2px}.kpi-main .klbl{color:rgba(255,255,255,.55);font-size:8px;text-transform:uppercase;letter-spacing:.8px;display:flex;align-items:center;gap:5px}.badge-isc{display:inline-block;background:#0F9ED5;color:white;font-size:7px;font-weight:700;padding:1px 6px;border-radius:8px;text-transform:uppercase}.kpi-main .kval{color:white;font-size:30px;font-weight:700;line-height:1}.kpi-main .kunt{color:rgba(255,255,255,.6);font-size:10px;margin-left:3px}.kpi-main .kref{color:rgba(255,255,255,.4);font-size:7.5px;margin-top:2px}.badges-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}.badge-kpi{background:rgba(255,255,255,.1);border-radius:6px;padding:7px 10px}.badge-kpi .bl{color:rgba(255,255,255,.55);font-size:7px;text-transform:uppercase;letter-spacing:.5px}.badge-kpi .bv{color:white;font-size:13px;font-weight:700;margin-top:2px;line-height:1}.p50-line{color:rgba(255,255,255,.35);font-size:7.5px}.pag{width:297mm;height:210mm;padding:8mm 10mm 6mm;display:flex;flex-direction:column;gap:5px;page-break-after:always;break-after:page}.pag-last{width:297mm;height:210mm;padding:8mm 10mm 6mm;display:flex;flex-direction:column;gap:5px}.hdr{display:flex;justify-content:space-between;align-items:center;padding-bottom:5px;border-bottom:2.5px solid #156082;flex-shrink:0}.tag{display:inline-block;padding:1px 7px;border-radius:999px;font-size:7.5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-right:4px}.tag.blue{background:#dff3fb;color:#0b6e96}.tag.orange{background:#fff0e7;color:#a74f22}.tag.green{background:#def5e8;color:#18734b}.tag.isc{background:#0F9ED5;color:white}.title{font-size:14px;font-weight:700;color:#0E2841;line-height:1;margin-top:2px}.subtitle{font-size:8px;color:#6B7C8F;margin-top:2px}.brand{display:flex;align-items:center;gap:6px;font-size:9px;color:#156082;font-weight:700;flex-shrink:0}.panel{background:#F5F8FB;border:1px solid #D9E3EC;border-radius:8px;padding:8px 10px;flex-shrink:0}.panel-title{font-size:9px;font-weight:700;color:#0E2841;margin-bottom:7px;display:flex;align-items:center;gap:5px}.kpi-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px}.kpi-2{display:grid;grid-template-columns:1fr 1fr;gap:6px}.kpi{background:white;border:1px solid #D9E3EC;border-radius:7px;padding:8px 9px;border-top:3px solid #ccc}.kpi.or{border-top-color:#E97132}.kpi.yw{border-top-color:#F2B134}.kpi.gn{border-top-color:#2CA66F}.kpi.bu{border-top-color:#0F9ED5}.kpi.pu{border-top-color:#7E57C2}.kpi .lbl{font-size:7px;text-transform:uppercase;letter-spacing:.5px;color:#6B7C8F;font-weight:700;margin-bottom:3px}.kpi .val{font-size:22px;font-weight:700;color:#0E2841;line-height:1}.kpi .val.sm{font-size:15px}.kpi .unit{font-size:7.5px;color:#8291A1;margin-top:2px}.kpi .ref{font-size:7px;color:#8A97A4;margin-top:5px;padding-top:4px;border-top:1px solid #ECF1F5}.col-lr{flex:1;display:grid;grid-template-columns:1.6fr 1fr;gap:6px;min-height:0}.col-11{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:6px;min-height:0}.col-l155{flex:1;display:grid;grid-template-columns:1.55fr 1fr;gap:6px;min-height:0}.col-l16{flex:1;display:grid;grid-template-columns:1.6fr 1fr;gap:6px;min-height:0}.fcol{display:flex;flex-direction:column;gap:6px;min-height:0}.chart{background:white;border:1px solid #D9E3EC;border-radius:7px;padding:7px 8px 6px;flex:1;min-height:0;display:flex;flex-direction:column}.chart-small{background:white;border:1px solid #D9E3EC;border-radius:7px;padding:7px 8px 5px;flex-shrink:0}.chart-title{font-size:8.5px;font-weight:700;color:#0E2841;margin-bottom:5px;flex-shrink:0}.chart-leg{display:flex;gap:8px;flex-wrap:wrap;margin-top:3px;flex-shrink:0}.chart-leg span{font-size:7px;color:#6B7C8F;display:flex;align-items:center;gap:3px}.ld{width:9px;height:3px;border-radius:1px;display:inline-block}.ldd{width:9px;height:0;border-top:2px dashed #E97132;display:inline-block}.callout{background:#F7FBFF;border:1px solid #D6EAF5;border-left:3px solid #0F9ED5;border-radius:7px;padding:8px 10px;flex:1;min-height:0;display:flex;flex-direction:column}.callout .ct{font-size:8.5px;font-weight:700;color:#0E2841;margin-bottom:5px;flex-shrink:0}.callout .cb{font-size:8px;color:#17324A;line-height:1.6;flex:1;overflow:hidden}.insight{background:#FFF7F0;border:1px solid #FFD6B5;border-left:3px solid #E97132;border-radius:7px;padding:8px 10px;flex:1;min-height:0;display:flex;flex-direction:column}.insight .ct{font-size:8.5px;font-weight:700;color:#0E2841;margin-bottom:5px;flex-shrink:0}.insight .cb{font-size:8px;color:#17324A;line-height:1.6;flex:1;overflow:hidden}.stat-g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px}.stat{background:white;border:1px solid #D9E3EC;border-radius:6px;padding:6px 8px;text-align:center}.stat .lbl{font-size:7px;text-transform:uppercase;color:#6B7C8F;font-weight:700}.stat .val{font-size:16px;font-weight:700;color:#0E2841;margin-top:2px;line-height:1}.stat .val.ok{color:#2CA66F}.stat .val.warn{color:#E97132}.bh{display:flex;align-items:center;gap:6px;margin-bottom:5px}.bh-lbl{font-size:7.5px;color:#17324A;font-weight:700;width:62px;flex-shrink:0}.bh-lbl.sm{width:42px}.bh-track{flex:1;height:9px;background:#EEF3F7;border-radius:4px;overflow:hidden}.bh-fill{height:100%;border-radius:4px}.bh-val{font-size:7.5px;color:#6B7C8F;width:54px;text-align:right;flex-shrink:0}.bh-val.sm{width:46px}table{width:100%;border-collapse:collapse;font-size:8px}thead tr{background:#0E2841;color:white}thead th{padding:5px 6px;text-align:left;font-weight:700;font-size:7.5px}tbody tr:nth-child(even){background:#F8FAFC}tbody tr:nth-child(odd){background:white}tbody tr.alrt{background:#FEF6F0 !important}tbody td{padding:5px 6px;border-bottom:1px solid #F1F5F9;font-size:8px}.medal{font-size:10px;margin-right:2px}.chip{display:inline-block;padding:1px 5px;border-radius:3px;font-size:7px;font-weight:700}.chip.ok{background:#def5e8;color:#18734b}.chip.warn{background:#fff3cd;color:#856404}.cval-ok{color:#2CA66F;font-weight:700}.cval-bad{color:#E45C54;font-weight:700}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px;vertical-align:middle}.dot.closed{background:#2CA66F}.dot.open{background:#E45C54}.tech-list{display:flex;flex-direction:column;gap:4px}.tech-item{background:white;border:1px solid #D9E3EC;border-radius:5px;padding:5px 7px}.tech-item .th{font-size:7px;text-transform:uppercase;color:#6B7C8F;font-weight:700;margin-bottom:2px}.tech-item .tx{font-size:9px;color:#0E2841;font-weight:700}.stat-g2{display:grid;grid-template-columns:1fr 1fr;gap:5px}.stat2{background:white;border:1px solid #D9E3EC;border-radius:6px;padding:6px 9px;text-align:center}.stat2 .lbl{font-size:7px;text-transform:uppercase;color:#6B7C8F;font-weight:700}.stat2 .val{font-size:18px;font-weight:700;color:#0E2841;margin-top:2px;line-height:1}.footer{display:flex;justify-content:space-between;font-size:7.5px;color:#8b98a5;border-top:1px solid #E7EDF2;padding-top:3px;flex-shrink:0}[contenteditable]{outline:none;cursor:text;border-radius:3px}@media screen{[contenteditable]:hover{background:rgba(15,120,200,.06)}[contenteditable]:focus{background:rgba(15,158,213,.09);box-shadow:0 0 0 1.5px rgba(15,158,213,.3)}}@media print{[contenteditable]{background:transparent !important;box-shadow:none !important}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}'
LOGO_B64 = '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'
import json as _json_mod

def _build_raw_dataset(cad, kpis, kpis_5est, df_daily, df_paradas, pvsyst,
                       tarifa, poa, fonte_poa, fonte_energia, ano, mes, disp_dia_inv):
    """Monta dict com TODOS os dados crus do relatorio. Serializado em JSON
    no HTML para permitir edicao interativa client-side."""
    import json as _json_dataset
    # Construir lookup de disp_op_pct/horas_off a partir do df_inv (que ja merged com df_disp_op)
    df_inv_kpi = kpis.get("df_inv", pd.DataFrame()) if kpis else pd.DataFrame()
    disp_op_lookup = {}
    horas_off_lookup = {}
    if not df_inv_kpi.empty:
        for _, r in df_inv_kpi.iterrows():
            disp_op_lookup[str(r["inversor"])] = float(r.get("disp_op_pct", 0) or 0)
            horas_off_lookup[str(r["inversor"])] = float(r.get("horas_off", 0) or 0)

    # Inversores: lista de {nome, modelo, energia_kwh_total, energias_diarias{dia: kwh}}
    inversores = []
    if df_daily is not None and not df_daily.empty:
        for inv_name, grp in df_daily.groupby("inversor"):
            energias = {}
            for _, r in grp.iterrows():
                d = r["dia"]
                if hasattr(d, "strftime"): k = d.strftime("%Y-%m-%d")
                else:
                    s = str(d); k = s if "-" in s else f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                energias[k] = float(r["energia_kwh"])
            modelo = ""
            if "modelo" in grp.columns:
                _m = grp["modelo"].iloc[0]
                modelo = str(_m) if _m is not None else ""
            inversores.append({
                "nome": str(inv_name),
                "modelo": modelo,
                "energia_total_kwh": round(float(grp["energia_kwh"].sum()), 2),
                "energias_diarias": energias,
                "disp_op_pct": disp_op_lookup.get(str(inv_name), 0.0),
                "horas_off": horas_off_lookup.get(str(inv_name), 0.0),
            })
    # Paradas: lista de {id, inversor, inicio, fim, duracao_h, causa, responsavel}
    paradas_list = []
    if df_paradas is not None and not df_paradas.empty:
        for i, r in df_paradas.iterrows():
            paradas_list.append({
                "id": f"p{i}",
                "inversor": str(r["inversor"]),
                "inicio": str(r.get("inicio", "")),
                "fim": str(r.get("fim", "")) if r.get("fim") is not None else "",
                "duracao_h": float(r.get("duracao_h", 0)),
                "tipo": str(r.get("tipo", "")),
                "causa": str(r.get("causa", "")) if r.get("causa") is not None else "",
                "responsavel": str(r.get("responsavel", "")) if r.get("responsavel") is not None else "",
            })
    # Disp dia inversor: {dia(int): {inv: pct}}
    disp_dia = {}
    if disp_dia_inv:
        for d, d_dict in disp_dia_inv.items():
            disp_dia[int(d)] = {str(k): float(v) for k, v in d_dict.items()}

    return {
        "plant": {
            "id": int(cad.get("id", 0)) if cad.get("id") else None,
            "name": str(cad.get("name", "")),
            "kwp": float(cad.get("nominal_power_kwp") or 0),
            "ano": int(ano), "mes": int(mes),
            "dias_mes": calendar.monthrange(int(ano), int(mes))[1],
            "fonte_energia": str(fonte_energia or ""),
        },
        "pvsyst": {
            "e_grid": float(pvsyst.get("e_grid") or 0),
            "pr": float(pvsyst.get("pr") or 0),
            "p50": float(pvsyst.get("p50") or 0),
            "p75": float(pvsyst.get("p75") or 0),
            "glob_inc": float(pvsyst.get("glob_inc") or 0),
            "glob_hor": float(pvsyst.get("glob_hor") or 0),
        },
        "inverters": inversores,
        "paradas": paradas_list,
        "disp_dia_inv": disp_dia,
        "kpis_originais": {
            "energia_real": float(kpis.get("energia_real", 0)),
            "pr_real": float(kpis.get("pr_real", 0)),
            "at": float(kpis.get("at", 0)),
            "disp_ger": float(kpis.get("disp_ger", 0)),
            "var_poa": float(kpis.get("var_poa", 0)),
            "dias_com_dado": int(kpis.get("dias_com_dado", 0)),
            "cob_pct": float(kpis.get("cob_pct", 0)),
            "esp_kwp": float(kpis.get("esp_kwp", 0)),
            "tier": int(kpis_5est.get("tier", 2)) if kpis_5est else 2,
            "pct_ger_pure": float(kpis_5est.get("pct_ger_pure", 0)) if kpis_5est else 0,
            "pct_irr": float(kpis_5est.get("pct_irr", 0)) if kpis_5est else 0,
            "pct_conc": float(kpis_5est.get("pct_conc", 0)) if kpis_5est else 0,
            "pct_om": float(kpis_5est.get("pct_om", 0)) if kpis_5est else 0,
        },
        "estado_inicial": {
            "tarifa_rs_kwh": float(tarifa or 0),
            "poa_kwh_m2": float(poa or 0),
            "poa_fonte": str(fonte_poa or ""),
        },
    }


# Vocabulario default de causas e responsaveis (usado quando nao ha customizacao)
_VOCAB_DEFAULT = {
    "causas": [
        {"id": "sob_ca",    "label": "Sobretensao CA"},
        {"id": "sub_ca",    "label": "Subtensao CA"},
        {"id": "off_rede",  "label": "OFF (rede/coletivo)"},
        {"id": "off_eq",    "label": "OFF (equipamento/trip)"},
        {"id": "desc_tot",  "label": "Desconexao total"},
        {"id": "baixa_irr", "label": "Baixa irradiacao"},
    ],
    "responsaveis": [
        {"id": "conc", "label": "Concessionaria",      "categoria": "concessionaria", "cor": "#0F9ED5"},
        {"id": "om",   "label": "Equipamento / O&M",   "categoria": "om",             "cor": "#E45C54"},
    ],
}


def gerar_html(cad,kpis,alertas,df_paradas,tarifa,obs,pvsyst,
               ano,mes,charts,tem_estacao,poa,fonte_poa,
               disp_op_media,fonte_energia,kpis_5est=None,disp_dia_inv=None,df_daily=None):
    _ensure_chartjs()
    nm=MESES[mes]; usina=str(cad.get("name","---")); acronym=str(cad.get("acronym") or cad.get("name","---")[:10])
    kwp=float(cad.get("nominal_power_kwp") or 0)
    contrato=str(cad.get("om_contract","---"))
    fim=cad.get("contract_end")
    fim_s=pd.to_datetime(fim).strftime("%d/%m/%Y") if fim and str(fim) not in ("None","nan") else "---"
    er=kpis.get("energia_real",0); ee=kpis.get("ee",0); at=kpis.get("at",0)
    pr_real=kpis.get("pr_real",0); pr_e=kpis.get("pr_e",0)
    esp_kwp=kpis.get("esp_kwp",0); dg=kpis.get("disp_ger",0)
    p50=kpis.get("p50",0); p75=kpis.get("p75",0)
    glob_inc=kpis.get("glob_inc",0); var_poa=kpis.get("var_poa",0)
    dias_com=kpis.get("dias_com_dado",0); dias_mes=calendar.monthrange(ano,mes)[1]
    df_inv=kpis.get("df_inv",pd.DataFrame()); cob_pct=kpis.get("cob_pct",0)
    receita=er*tarifa if tarifa else 0
    gerado=datetime.now().strftime("%d/%m/%Y %H:%M")

    def fmt_n(v,d=0):
        return ("{:,."+str(d)+"f}").format(v).replace(",","X").replace(".",",").replace("X",".")
    def fmt_p(v,d=1):
        return ("{:."+str(d)+"f}%").format(v).replace(".",",")

    er_s   = fmt_n(er)       if er else "---"
    ee_s   = fmt_n(ee)       if ee else "---"
    at_s   = fmt_p(at)       if ee else "---"
    pr_s   = fmt_p(pr_real*100,2) if pr_real else "---"
    pr_e_s = fmt_p(pr_e*100,2) if pr_e else "---"
    esp_s  = fmt_n(esp_kwp,2) if esp_kwp else "---"
    dg_s   = fmt_p(dg)       if dg else "---"
    dop_s  = fmt_p(disp_op_media,2) if disp_op_media else "---"
    # AEVO19: KPIs de 5 estados
    is_tier1 = kpis_5est and kpis_5est.get("tier")==1
    pct_ger_s = fmt_p(kpis_5est.get("pct_geracao",0),2) if is_tier1 else dop_s
    pct_conc_s = fmt_p(kpis_5est.get("pct_conc",0),2) if is_tier1 else "---"
    pct_om_s = fmt_p(kpis_5est.get("pct_om",0),2) if is_tier1 else "---"
    pct_com_s = fmt_p(kpis_5est.get("pct_com",0),2) if is_tier1 else "---"
    pct_irr_s = fmt_p(kpis_5est.get("pct_irr",0),2) if is_tier1 else "---"
    p50_s  = fmt_n(p50)      if p50 else "---"
    p75_s  = fmt_n(p75)      if p75 else "---"
    poa_s  = (fmt_n(poa,2)+" kWh/m²") if poa else "---"
    glinc_s= (fmt_n(glob_inc,2)+" kWh/m²") if glob_inc else "---"
    varp_s = (("{:+.1f}%").format(var_poa).replace(".",",")) if (poa and glob_inc) else "---"
    kwp_s  = fmt_n(kwp)      if kwp else "---"
    rec_s  = ("R$ "+fmt_n(receita,2)) if receita else "---"
    tar_s  = ("R$ "+fmt_n(tarifa,2)+"/kWh") if tarifa else "---"
    cob_s  = fmt_p(cob_pct)+" ("+str(dias_com)+"/"+str(dias_mes)+" dias)"
    pr_formula = (fmt_n(er)+" / ("+fmt_n(poa,2)+" x "+fmt_n(kwp)+")") if (poa and kwp) else "---"
    obs_txt = obs.replace(chr(10),"<br>") if obs else ""

    logo_l = '<img src="data:image/png;base64,'+LOGO_B64+'" style="height:36px;width:auto">'
    logo_s = '<img src="data:image/png;base64,'+LOGO_B64+'" style="height:22px;width:auto">'

    if fonte_energia=="iSolarCloud":
        fe     = '<span class="badge-isc">iSolarCloud</span>'
        fe_tag = '<span class="tag isc" style="font-size:7px;vertical-align:middle">iSolarCloud</span>'
    else:
        fe     = '<span style="background:#f39c12;color:white;font-size:7px;font-weight:700;padding:1px 6px;border-radius:8px;text-transform:uppercase;margin-left:4px">Banco AEVO</span>'
        fe_tag = ''

    def ft(pg=""):
        return ('<div class="footer"><span contenteditable="true">Aevo Solar — Relatório de Geração Mensal — '+
                nm+'/'+str(ano)+' — '+usina+'</span>'+
                ('<span contenteditable="true">'+pg+'</span>' if pg else '')+'</div>')

    medals={0:"\\U0001f947",1:"\\U0001f948",2:"\\U0001f949"}
    inv_rows=""
    med_e=float(df_inv["energia_kwh"].mean()) if len(df_inv) else 0
    mel_e=float(df_inv["energia_kwh"].max())  if len(df_inv) else 0
    for idx,(_,r) in enumerate(df_inv.iterrows()):
        dm=(float(r["energia_kwh"])-med_e)/med_e*100 if med_e else 0
        db=(float(r["energia_kwh"])-mel_e)/mel_e*100 if mel_e else 0
        medal=(medals[idx] if idx<3 else "")
        disp_inv=float(r.get("disp_op_pct",0))
        chip_cls="ok" if disp_inv>=99 else "warn"
        dm_cls="cval-ok" if dm>=-5 else "cval-bad"
        db_cls="cval-ok" if db>=-5 else "cval-bad"
        row_cls=' class="alrt"' if dm<-10 else ""
        inv_rows+=(
            "<tr"+row_cls+"><td>"+medal+"<span contenteditable='true'>"+str(r["inversor"])+"</span></td>"+
            "<td contenteditable='true'>"+str(r.get("modelo",""))+"</td>"+
            "<td style='text-align:right' contenteditable='true'>"+fmt_n(float(r["energia_kwh"]),2)+"</td>"+
            "<td style='text-align:right' contenteditable='true'>"+fmt_n(float(r.get("esp_kwh_kwp",0)),2)+"</td>"+
            "<td style='text-align:right' contenteditable='true'>"+fmt_p(float(r["pct"]))+"</td>"+
            "<td style='text-align:right' contenteditable='true'>"+fmt_p(float(r.get("disp_ger_pct",0)))+"</td>"+
            "<td style='text-align:right'><span class='chip "+chip_cls+"' contenteditable='true'>"+fmt_p(disp_inv,2)+"</span></td>"+
            "<td style='text-align:right' contenteditable='true'>"+fmt_n(float(r.get("horas_off",0)),2)+"h</td>"+
            "<td style='text-align:right' class='"+dm_cls+"' contenteditable='true'>"+("{:+.1f}%").format(dm).replace(".",",")+"</td>"+
            "<td style='text-align:right' class='"+db_cls+"' contenteditable='true'>"+("{:+.1f}%").format(db).replace(".",",")+"</td></tr>"
        )

    rank_rows=""
    if len(df_inv) and "esp_kwh_kwp" in df_inv.columns:
        max_esp=float(df_inv["esp_kwh_kwp"].max()) or 1
        for _,r in df_inv.iterrows():
            esp=float(r.get("esp_kwh_kwp",0))
            pw=int(esp/max_esp*100)
            col="#E45C54" if esp<max_esp*.85 else "#0F9ED5"
            rank_rows+=("<div class='bh'><div class='bh-lbl sm' contenteditable='true'>"+str(r["inversor"])+"</div>"+
                        "<div class='bh-track' style='height:10px'><div class='bh-fill' style='width:"+str(pw)+"%;background:"+col+"'></div></div>"+
                        "<div class='bh-val sm' contenteditable='true'>"+fmt_n(esp,1)+"</div></div>")

    # Classificar faixa horaria de uma ocorrencia
    def _faixa_horaria(inicio_str):
        """Retorna (nome_faixa, css_classe) a partir do horario de inicio."""
        try:
            parts=str(inicio_str).split(" ")
            if len(parts)>=2:
                h=int(parts[1].split(":")[0])
            else: return ("—","b-gray")
        except: return ("—","b-gray")
        if 5<=h<8:   return ("Partida","b-blue")
        if 8<=h<12:  return ("Pico M","b-amber")
        if 12<=h<17: return ("Pico T","b-teal")
        if 17<=h<19: return ("Declinio","b-green")
        return ("Fora solar","b-gray")

    badge_css={"b-blue":"background:#E6F1FB;color:#185FA5",
               "b-amber":"background:#FAEEDA;color:#854F0B",
               "b-teal":"background:#E1F5EE;color:#0F6E56",
               "b-green":"background:#E1F5EE;color:#0F6E56",
               "b-gray":"background:#F1EFE8;color:#5F5E5A"}

    has_al=len(alertas)>0; has_par=not df_paradas.empty
    al_rows=""; total_ev=0; total_h=0.0; em_aberto=0
    # Contadores de faixa para distribuicao
    faixa_par={"Partida":0,"Pico M":0,"Pico T":0,"Declinio":0,"Fora solar":0,"—":0}
    faixa_al ={"Partida":0,"Pico M":0,"Pico T":0,"Declinio":0,"Fora solar":0,"—":0}
    if has_al:
        for _,r in alertas.iterrows():
            total_ev+=1; total_h+=float(r["horas"])
            if r["status"]=="Aberto": em_aberto+=1
            c="closed" if r["status"]=="Fechado" else "open"
            fn,fc=_faixa_horaria(r["inicio"])
            faixa_al[fn]=faixa_al.get(fn,0)+1
            al_rows+=("<tr><td><span class='chip warn' contenteditable='true'>Alerta</span></td>"+
                      "<td contenteditable='true'>"+str(r["ativo"])+"</td>"+
                      "<td contenteditable='true'>"+str(r["inicio"])+"</td>"+
                      "<td contenteditable='true'>"+str(r.get("fim","---") or "---")+"</td>"+
                      "<td style='text-align:right' contenteditable='true'>"+fmt_n(float(r["horas"]),1)+" h</td>"+
                      "<td><span style='display:inline-block;font-size:7px;padding:1px 5px;border-radius:3px;font-weight:500;"+badge_css.get(fc,"")+"' contenteditable='true'>"+fn+"</span></td>"+
                      ("<td contenteditable='true'>Alerta banco</td><td contenteditable='true'>—</td>" if is_tier1 else "")+
                      "<td><span class='dot "+c+"'></span><span contenteditable='true'>"+str(r["status"])+"</span></td></tr>")
    has_causa = is_tier1 or (has_par and "causa" in df_paradas.columns)
    if has_par:
        for _,r in df_paradas.iterrows():
            total_ev+=1; total_h+=float(r["duracao_h"])
            fn,fc=_faixa_horaria(r["inicio"])
            faixa_par[fn]=faixa_par.get(fn,0)+1
            causa_html=""
            if has_causa:
                causa_html=("<td contenteditable='true'>"+str(r.get("causa","---"))+"</td>"+
                            "<td contenteditable='true'>"+str(r.get("responsavel","---"))+"</td>")
            al_rows+=("<tr><td><span class='chip warn' contenteditable='true'>Parada Parcial</span></td>"+
                      "<td contenteditable='true'>"+str(r["inversor"])+"</td>"+
                      "<td contenteditable='true'>"+str(r["inicio"])+"</td>"+
                      "<td contenteditable='true'>"+str(r["fim"])+"</td>"+
                      "<td style='text-align:right' contenteditable='true'>"+fmt_n(float(r["duracao_h"]),2)+" h</td>"+
                      "<td><span style='display:inline-block;font-size:7px;padding:1px 5px;border-radius:3px;font-weight:500;"+badge_css.get(fc,"")+"' contenteditable='true'>"+fn+"</span></td>"+
                      causa_html+
                      "<td><span class='dot closed'></span><span contenteditable='true'>Fechado</span></td></tr>")
    _ncols="9" if is_tier1 else "7"
    if not has_al and not has_par:
        al_rows="<tr><td colspan='"+_ncols+"' style='text-align:center;color:#888;padding:12px'>Nenhuma ocorrência no período</td></tr>"

    # Calcular percentuais de distribuicao por faixa
    def _dist_bars(counts):
        faixas_order=["Partida","Pico M","Pico T","Declinio"]
        faixas_lbl={"Partida":"Partida 06:30–08h","Pico M":"Pico M 08–12h","Pico T":"Pico T 12–17h","Declinio":"Declínio 17–17:30"}
        faixas_col={"Partida":"#378ADD","Pico M":"#EF9F27","Pico T":"#EF9F27","Declinio":"#1D9E75"}
        faixas_tcol={"Partida":"#185FA5","Pico M":"#854F0B","Pico T":"#854F0B","Declinio":"#0F6E56"}
        total=sum(counts.get(f,0) for f in faixas_order) or 1
        html=""
        for f in faixas_order:
            n=counts.get(f,0); pct=int(n/total*100) if total>0 else 0
            html+=("<div class='bh'><div class='bh-lbl' style='width:80px;font-size:7.5px' contenteditable='true'>"+faixas_lbl[f]+"</div>"+
                   "<div class='bh-track' style='height:10px'><div class='bh-fill' style='width:"+str(pct)+"%;background:"+faixas_col[f]+"'></div></div>"+
                   "<div class='bh-val' style='width:30px;font-size:7.5px;color:"+faixas_tcol[f]+"' contenteditable='true'>"+str(pct)+"%</div></div>")
        return html
    dist_par_html=_dist_bars(faixa_par)
    dist_al_html=_dist_bars(faixa_al)

    # ── Dados para gráficos da página 5 analítica (Tier 1) ──
    horas_por_causa={}; eventos_por_resp_faixa={}
    if has_par and has_causa:
        for _,r in df_paradas.iterrows():
            c=str(r.get("causa","?"))
            horas_por_causa[c]=horas_por_causa.get(c,0)+float(r["duracao_h"])
            resp=str(r.get("responsavel","?"))
            fn,_=_faixa_horaria(r["inicio"])
            key=(fn,resp)
            eventos_por_resp_faixa[key]=eventos_por_resp_faixa.get(key,0)+1
    # JS arrays para horas por causa
    causas_order=["Sobretensao CA","Subtensao CA","OFF (rede/coletivo)","Desconexao total","OFF (equipamento/trip)","Baixa irradiacao"]
    causas_horas_js="["+",".join([str(round(horas_por_causa.get(c,0),2)) for c in causas_order])+"]"
    # JS arrays para distribuição horária por responsável
    faixas_order_js=["Partida","Pico M","Pico T","Declinio"]
    conc_faixa_js="["+",".join([str(eventos_por_resp_faixa.get((f,"Concessionaria"),0)) for f in faixas_order_js])+"]"
    eqom_faixa_js="["+",".join([str(eventos_por_resp_faixa.get((f,"Equipamento / O&M"),0)) for f in faixas_order_js])+"]"
    # Heatmap: por inversor x dia, cor por responsável
    heatmap_data={}  # {(inv,dia): cor}
    if has_par and has_causa:
        import re as _re
        for _,r in df_paradas.iterrows():
            inv=str(r["inversor"])
            m=_re.match(r"(\d{2})/(\d{2})/\d{4}",str(r["inicio"]))
            if m: dia=int(m.group(1))
            else: continue
            resp=str(r.get("responsavel","?"))
            cor=3 if ("Equipamento" in resp or "O&M" in resp) else (2 if "Concession" in resp else 1)
            old=heatmap_data.get((inv,dia),0)
            if cor>old: heatmap_data[(inv,dia)]=cor  # mais severo prevalece
    all_inv_hm=sorted(set(k[0] for k in heatmap_data.keys())) if heatmap_data else []
    heatmap_js=json.dumps({str(k[0])+"_"+str(k[1]):v for k,v in heatmap_data.items()},ensure_ascii=False)
    heatmap_inv_js=json.dumps(all_inv_hm,ensure_ascii=False)

    # Calculate total pages (dynamic based on events and tier)
    if is_tier1:
        _al_count = al_rows.count('<tr>') if al_rows else 0
        _n_tbl_pags = max(1, (_al_count+34)//35)
        total_pags = str(5 + _n_tbl_pags)
    else:
        total_pags = "5"

    eq_counts={}
    if has_par:
        for _,r in df_paradas.iterrows(): eq_counts[r["inversor"]]=eq_counts.get(r["inversor"],0)+1
    if has_al:
        for _,r in alertas.iterrows(): eq_counts[r["ativo"]]=eq_counts.get(r["ativo"],0)+1
    max_ev_n=max(eq_counts.values()) if eq_counts else 1
    rank_ev=""
    for eq,cnt in sorted(eq_counts.items(),key=lambda x:-x[1])[:5]:
        pw=int(cnt/max_ev_n*100)
        col="#E97132" if cnt==max_ev_n else ("#F2B134" if cnt>=max_ev_n*.5 else "#D9E3EC")
        rank_ev+=("<div class='bh'><div class='bh-lbl sm' contenteditable='true'>"+str(eq)+"</div>"+
                  "<div class='bh-track' style='height:10px'><div class='bh-fill' style='width:"+str(pw)+"%;background:"+col+"'></div></div>"+
                  "<div class='bh-val sm' contenteditable='true'>"+str(cnt)+" ev.</div></div>")
    if not rank_ev:
        rank_ev="<div style='font-size:8px;color:#6B7C8F'>Nenhuma ocorrência detectada</div>"

    inv_labels_js=_json_mod.dumps([str(r["inversor"]) for _,r in df_inv.iterrows()])
    inv_data_js  =_json_mod.dumps([round(float(r["energia_kwh"]),2) for _,r in df_inv.iterrows()])
    inv_med_js   =round(float(df_inv["energia_kwh"].mean()),2) if len(df_inv) else 0
    dev_data_js  =_json_mod.dumps([
        round((er-ee)/ee*100,1) if ee else 0,
        round((pr_real-pr_e)/pr_e*100,1) if pr_e else 0,
        round((poa-glob_inc)/glob_inc*100,1) if (poa and glob_inc) else 0,
        round(dg-100,1)
    ])
    ch_disp_json=charts.get("disp","{}")
    ch_poa_json =charts.get("poa","{}") if tem_estacao else charts.get("ger_dia","{}")
    ch_poa_title="POA Diário Medido vs Esperado PVsyst (kWh/m²)" if tem_estacao else "Geração Diária Total da Usina (kWh)"

    df_dia=kpis.get("df_dia",pd.DataFrame())
    if not df_dia.empty:
        vals=[float(v) for v in df_dia["energia_kwh"]]
        d_a18=sum(1 for v in vals if v>=18000)
        d_1418=sum(1 for v in vals if 14000<=v<18000)
        d_1014=sum(1 for v in vals if 10000<=v<14000)
        d_b10=sum(1 for v in vals if v<10000)
        tot=max(len(vals),1)
        def pct_d(n): return int(n/tot*100)
    else:
        d_a18=d_1418=d_1014=d_b10=tot=0
        def pct_d(n): return 0

    # Detectar anomalias via consistência entre inversores
    anomalia_html=""
    alert_dias=[]
    if not df_dia.empty:
        _vals=sorted([float(v) for v in df_dia["energia_kwh"] if float(v)>0])
        if len(_vals)>=5:
            _mediana=_vals[len(_vals)//2]
            _spike_dias=[]; _frozen_dias=[]
            _inv_dia={}
            if df_daily is not None and not df_daily.empty:
                for _,_r in df_daily.iterrows():
                    _dd=_r["dia"]; _di2=int(_dd.strftime("%d")) if hasattr(_dd,"strftime") else int(str(_dd)[8:10])
                    _inv_n=str(_r["inversor"])
                    if _di2 not in _inv_dia: _inv_dia[_di2]={}
                    _inv_dia[_di2][_inv_n]=_inv_dia[_di2].get(_inv_n,0)+float(_r["energia_kwh"])
            for _,_r in df_dia.iterrows():
                _v=float(_r["energia_kwh"]); _d=_r["dia"]
                _ds=_d.strftime("%d/%m") if hasattr(_d,"strftime") else str(_d)[8:10]+"/"+str(_d)[5:7]
                _d_int=int(_ds[:2])
                if _v>_mediana*2.5 and _v>20000:
                    _spike_dias.append((_ds,_v)); alert_dias.append(_d_int)
                if _v<_mediana*0.10 and _inv_dia:
                    _id=_inv_dia.get(_d_int,{})
                    if _id:
                        _iv=sorted(_id.values()); _mi=_iv[len(_iv)//2] if _iv else 0
                        _nb=sum(1 for ev in _iv if ev<_mi*0.20) if _mi>0 else len(_iv)
                        if _nb/max(len(_iv),1)>0.70: pass  # >70% baixos = clima
                        elif _nb<=2 and _mi>100:
                            _nomes=[n for n,ev in _id.items() if ev<_mi*0.20]
                            _frozen_dias.append((_ds,_v,", ".join(_nomes[:3]))); alert_dias.append(_d_int)
            if _frozen_dias:
                _itens=" ".join(["<b>"+d+"</b> ("+fmt_n(v,0)+" kWh, inv: "+inv+")" for d,v,inv in _frozen_dias])
                anomalia_html+=('<div class="insight"><div class="ct">⚠️ Possível p2 congelado</div>'
                    '<div class="cb">Inversores específicos com geração quase zero enquanto os demais geraram normalmente: '+_itens+'.</div></div>')
            if _spike_dias:
                _itens=" ".join(["<b>"+d+"</b> ("+fmt_n(v,0)+" kWh)" for d,v in _spike_dias])
                anomalia_html+=('<div class="insight"><div class="ct">⚠️ Spike de energia detectado</div>'
                    '<div class="cb">Dias com geração acima de 2,5x a mediana: '+_itens+'. Possível liberação de acumulador p2 congelado.</div></div>')

    html=('<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
          '<script>'+_CHARTJS_CODE+'</script>'
          '<style>'+CSS+'</style></head><body>')

    # CAPA
    html+=('<div class="capa">'
      '<div class="capa-left">'
        '<div class="logo-area">'+logo_l+'</div>'
        '<div class="main-info">'
          '<div class="tag-badge" contenteditable="true">Relatório de Desempenho</div>'
          '<div class="usina-nome" contenteditable="true">'+usina+'</div>'
          '<div class="periodo" contenteditable="true">'+nm+' de '+str(ano)+'</div>'
          '<div class="divider"></div>'
          '<div class="meta-grid">'
            '<div class="meta-item"><label>Identificador</label><p contenteditable="true">'+acronym+'</p></div>'
            '<div class="meta-item"><label>Potência Nominal</label><p contenteditable="true">'+kwp_s+' kWp</p></div>'
            '<div class="meta-item"><label>Contrato O&amp;M</label><p contenteditable="true">'+contrato+'</p></div>'
            '<div class="meta-item"><label>Vigência</label><p contenteditable="true">'+fim_s+'</p></div>'
            '<div class="meta-item"><label>Tarifa</label><p data-kpi="tarifa" data-fmt="tar_rs">'+tar_s+'</p></div>'
            '<div class="meta-item"><label>Fonte Energia</label><p contenteditable="true">'+fonte_energia+'</p></div>'
          '</div>'
        '</div>'
        '<div class="footer-capa" contenteditable="true">Gerado em '+gerado+' — Aevo Solar — Uso interno</div>'
      '</div>'
      '<div class="capa-right"><div class="capa-card">'
        '<div class="kpi-main">'
          '<div class="klbl">Energia Real '+fe+'</div>'
          '<div><span class="kval" data-kpi="energia_real" data-fmt="n0">'+er_s+'</span><span class="kunt">kWh</span></div>'
          '<div class="kref" contenteditable="true">Esperado PVsyst: '+ee_s+' kWh</div>'
        '</div>'
        '<div class="badges-grid">'
          '<div class="badge-kpi"><div class="bl">Atingimento</div><div class="bv" data-kpi="at" data-fmt="p1">'+at_s+'</div></div>'
          '<div class="badge-kpi"><div class="bl">PR Real</div><div class="bv" data-kpi="pr_real" data-fmt="pr4">'+pr_s+'</div></div>'
          '<div class="badge-kpi"><div class="bl">Disp. Operação</div><div class="bv" data-kpi="disp_ger" data-fmt="p2">'+pct_ger_s+'</div></div>'
          '<div class="badge-kpi"><div class="bl">Cobertura</div><div class="bv" data-kpi="cob_pct" data-fmt="p1">'+cob_s+'</div></div>'
        '</div>'
        '<div class="p50-line" contenteditable="true">P50: '+p50_s+' kWh &nbsp;|&nbsp; P75: '+p75_s+' kWh</div>'
      '</div></div>'
    '</div>')

    # PAG 2
    html+=('<div class="pag">'
      '<div class="hdr"><div>'
        '<div><span class="tag blue" contenteditable="true">Desempenho</span>'
             '<span class="tag orange" contenteditable="true">Análise operacional</span></div>'
        '<div class="title" contenteditable="true">Desempenho Operacional '+fe_tag+'</div>'
        '<div class="subtitle" contenteditable="true">Resultado mensal — energia, PR, disponibilidade e contexto financeiro</div>'
      '</div><div class="brand">'+logo_s+' <span contenteditable="true">Aevo Solar</span></div></div>'
      '<div class="col-lr">'
        '<div class="fcol">'
          '<div class="panel"><div class="panel-title" contenteditable="true">Resultado Operacional</div>'
            '<div class="kpi-3">'
              '<div class="kpi or"><div class="lbl" contenteditable="true">Energia Real</div>'
                '<div class="val" data-kpi="energia_real" data-fmt="n0">'+er_s+'</div><div class="unit">kWh</div>'
                '<div class="ref" contenteditable="true">Esperado PVsyst: '+ee_s+' kWh</div></div>'
              '<div class="kpi yw"><div class="lbl" contenteditable="true">Atingimento</div>'
                '<div class="val" data-kpi="at" data-fmt="p1">'+at_s+'</div>'
                '<div class="unit">do esperado PVsyst</div>'
                '<div class="ref" contenteditable="true">P50: '+p50_s+' | P75: '+p75_s+'</div></div>'
              '<div class="kpi gn"><div class="lbl" contenteditable="true">PR Real</div>'
                '<div class="val" data-kpi="pr_real" data-fmt="pr4">'+pr_s+'</div><div class="unit">Performance Ratio</div>'
                '<div class="ref" contenteditable="true">PR esperado PVsyst: '+pr_e_s+'</div></div>'
            '</div>'
          '</div>'
          '<div class="chart">'
            '<div class="chart-title" contenteditable="true">Geração por Inversor (kWh) — '+fonte_energia+'</div>'
            '<div style="height:130px;position:relative"><canvas id="ch_inv"></canvas></div>'
          '</div>'
        '</div>'
        '<div class="fcol">'
          '<div class="panel"><div class="panel-title" contenteditable="true">Qualidade e Disponibilidade</div>'
            '<div class="kpi-2">'
              '<div class="kpi gn"><div class="lbl" contenteditable="true">Cobertura de Dados</div>'
                '<div class="val sm" data-kpi="cob_pct" data-fmt="p1">'+fmt_p(cob_pct)+'</div>'
                '<div class="unit" contenteditable="true">'+str(dias_com)+'/'+str(dias_mes)+' dias com dado</div></div>'
              '<div class="kpi bu"><div class="lbl" contenteditable="true">Disp. Geração</div>'
                '<div class="val sm" data-kpi="disp_ger" data-fmt="p2">'+pct_ger_s+'</div>'
                '<div class="unit">'+('Perdas Conc.: '+pct_conc_s+' | Eq/O&amp;M: '+pct_om_s if is_tier1 else 'Paradas ≥ 5 min')+'</div></div>'
            '</div>'
          '</div>'
          '<div class="panel"><div class="panel-title" contenteditable="true">Contexto Financeiro e Recurso</div>'
            '<div class="kpi-2">'
              '<div class="kpi pu"><div class="lbl" contenteditable="true">Receita Estimada</div>'
                '<div class="val sm" data-kpi="receita" data-fmt="rs">'+rec_s+'</div>'
                '<div class="unit"><span contenteditable="true">Tarifa:</span> <span data-kpi="tarifa" data-fmt="tar_rs">'+tar_s+'</span></div></div>'
              '<div class="kpi yw"><div class="lbl" contenteditable="true">POA Medido</div>'
                '<div class="val sm" data-kpi="poa" data-fmt="poa_kwh">'+poa_s+'</div>'
                '<div class="unit"><span contenteditable="true">Variação:</span> <span data-kpi="var_poa" data-fmt="p1">'+varp_s+'</span> <span contenteditable="true">(PVsyst: '+glinc_s+')</span></div></div>'
            '</div>'
          '</div>'
          '<div class="panel"><div class="panel-title" contenteditable="true">Leitura Técnica</div>'
            '<div class="tech-list">'
              '<div class="tech-item"><div class="th">Fórmula do PR</div>'
                '<div class="tx" data-tech="pr_formula">'+pr_formula+' = '+pr_s+'</div></div>'
              '<div class="tech-item"><div class="th">Fonte POA</div>'
                '<div class="tx" data-tech="fonte_poa">'+fonte_poa+'</div></div>'
            '</div>'
          '</div>'
          '<div class="chart-small">'
            '<div class="chart-title" contenteditable="true">Desvios vs Esperado PVsyst (%)</div>'
            '<div style="height:60px;position:relative"><canvas id="ch_dev"></canvas></div>'
          '</div>'
          '<div class="callout">'
            '<div class="ct" contenteditable="true">Análise automática · Desempenho</div>'
            '<div class="cb" data-analysis="page1" contenteditable="true" spellcheck="false">Aguardando dados...</div>'
          '</div>'
        '</div>'
      '</div>'+ft("2/"+total_pags)+'</div>')

    # PAG 3
    html+=('<div class="pag">'
      '<div class="hdr"><div>'
        '<div><span class="tag blue" contenteditable="true">Análise diária</span>'
             '<span class="tag green" contenteditable="true">Disponibilidade + Irradiação</span></div>'
        '<div class="title" contenteditable="true">Análise Diária</div>'
        '<div class="subtitle" contenteditable="true">Comportamento dia a dia — disponibilidade por inversor e recurso solar</div>'
      '</div><div class="brand">'+logo_s+' <span contenteditable="true">Aevo Solar</span></div></div>'
      '<div class="col-11">'
        '<div class="fcol">'
          '<div class="chart">'
            '<div class="chart-title" contenteditable="true">Disponibilidade de Geração por Dia</div>'
            '<div style="flex:1;min-height:0;position:relative"><canvas id="ch_disp"></canvas></div>'
            '<div class="chart-leg">'
              '<span><span class="ld" style="background:#0F9ED5"></span>INV01</span>'
              '<span><span class="ld" style="background:#E97132"></span>INV02</span>'
              '<span><span class="ld" style="background:#2CA66F"></span>INV03</span>'
              '<span><span class="ld" style="background:#7E57C2"></span>INV04</span>'
              '<span><span class="ld" style="background:#E45C54"></span>INV05</span>'
              '<span><span class="ld" style="background:#F2B134"></span>INV06</span>'
              '<span><span class="ld" style="background:#156082"></span>INV07</span>'
              '<span><span class="ld" style="background:#0E2841"></span>INV08</span>'
            '</div>'
          '</div>'
          '<div class="chart">'
            '<div class="chart-title" contenteditable="true">'+ch_poa_title+'</div>'
            '<div style="flex:1;min-height:0;position:relative"><canvas id="ch_poa"></canvas></div>'
            '<div class="chart-leg">'
              '<span><span class="ld" style="background:rgba(15,158,213,.7)"></span>'
                '<span contenteditable="true">Medido</span></span>'
              '<span><span class="ldd"></span><span contenteditable="true">PVsyst</span></span>'
            '</div>'
          '</div>'
        '</div>'
        '<div class="fcol">'
          '<div class="panel"><div class="panel-title" contenteditable="true">Resumo do Período</div>'
            '<div class="stat-g3">'
              '<div class="stat"><div class="lbl">Cobertura</div>'
                '<div class="val ok" contenteditable="true">'+fmt_p(cob_pct)+'</div></div>'
              '<div class="stat"><div class="lbl">POA Total</div>'
                '<div class="val" data-kpi="poa" data-fmt="poa_kwh">'+poa_s+'</div></div>'
              '<div class="stat"><div class="lbl">Var. vs PVsyst</div>'
                '<div class="val warn" data-kpi="var_poa" data-fmt="p1_signed">'+varp_s+'</div></div>'
            '</div>'
          '</div>'
          '<div class="panel"><div class="panel-title" contenteditable="true">Distribuição Diária de Geração</div>'
            '<div class="bh"><div class="bh-lbl" contenteditable="true">Acima 18k</div>'
              '<div class="bh-track"><div class="bh-fill" style="width:'+str(pct_d(d_a18))+'%;background:#2CA66F"></div></div>'
              '<div class="bh-val" contenteditable="true">'+str(d_a18)+' dias ('+str(pct_d(d_a18))+'%)</div></div>'
            '<div class="bh"><div class="bh-lbl" contenteditable="true">14k – 18k</div>'
              '<div class="bh-track"><div class="bh-fill" style="width:'+str(pct_d(d_1418))+'%;background:#0F9ED5"></div></div>'
              '<div class="bh-val" contenteditable="true">'+str(d_1418)+' dias ('+str(pct_d(d_1418))+'%)</div></div>'
            '<div class="bh"><div class="bh-lbl" contenteditable="true">10k – 14k</div>'
              '<div class="bh-track"><div class="bh-fill" style="width:'+str(pct_d(d_1014))+'%;background:#F2B134"></div></div>'
              '<div class="bh-val" contenteditable="true">'+str(d_1014)+' dias ('+str(pct_d(d_1014))+'%)</div></div>'
            '<div class="bh"><div class="bh-lbl" contenteditable="true">Abaixo 10k</div>'
              '<div class="bh-track"><div class="bh-fill" style="width:'+str(pct_d(d_b10))+'%;background:#E45C54"></div></div>'
              '<div class="bh-val" contenteditable="true">'+str(d_b10)+' dias ('+str(pct_d(d_b10))+'%)</div></div>'
          '</div>'
          +anomalia_html+
          '<div class="callout"><div class="ct" contenteditable="true">Análise automática · Geração diária</div>'
            '<div class="cb" data-analysis="page2" contenteditable="true" spellcheck="false">Aguardando dados...</div>'
          '</div>'
        '</div>'
      '</div>'+ft("3/"+total_pags)+'</div>')

    # PAG 4
    html+=('<div class="pag">'
      '<div class="hdr"><div>'
        '<div><span class="tag blue" contenteditable="true">Equipamentos</span>'
             '<span class="tag orange" contenteditable="true">Ranking de desempenho</span></div>'
        '<div class="title" contenteditable="true">Análise por Equipamento '+fe_tag+'</div>'
        '<div class="subtitle" contenteditable="true">Geração, eficiência, disponibilidade e desvios — '+nm+'/'+str(ano)+'</div>'
      '</div><div class="brand">'+logo_s+' <span contenteditable="true">Aevo Solar</span></div></div>'
      '<div class="col-l155">'
        '<div class="fcol">'
          '<div class="panel" style="flex:1">'
            '<div class="panel-title" contenteditable="true">Desempenho Individual dos Inversores</div>'
            '<table><thead><tr>'
              '<th contenteditable="true">Inversor</th>'
              '<th contenteditable="true">Modelo</th>'
              '<th style="text-align:right" contenteditable="true">Energia (kWh)</th>'
              '<th style="text-align:right" contenteditable="true">kWh/kWp</th>'
              '<th style="text-align:right" contenteditable="true">% Total</th>'
              '<th style="text-align:right" contenteditable="true">Cob. Dados</th>'
              '<th style="text-align:right" contenteditable="true">Disp. Op.</th>'
              '<th style="text-align:right" contenteditable="true">Hrs Off</th>'
              '<th style="text-align:right" contenteditable="true">Desv. Média</th>'
              '<th style="text-align:right" contenteditable="true">Desv. Melhor</th>'
            '</tr></thead><tbody data-tbl="inversores">'+inv_rows+'</tbody></table>'
          '</div>'
        '</div>'
        '<div class="fcol">'
          '<div class="panel">'
            '<div class="panel-title" contenteditable="true">Ranking — Energia Específica (kWh/kWp)</div>'
            +rank_rows+
            '<div style="font-size:7px;color:#6B7C8F;margin-top:4px" contenteditable="true">Vermelho: desvio &gt;15% vs melhor do grupo</div>'
          '</div>'
          '<div class="insight"><div class="ct" contenteditable="true">Análise automática · Equipamentos</div>'
            '<div class="cb" data-analysis="page3" contenteditable="true" spellcheck="false">Aguardando dados...</div>'
          '</div>'
        '</div>'
      '</div>'+ft("4/"+total_pags)+'</div>')

    # PAG 5 — Analytics (Tier 1) ou original (Tier 2)
    if is_tier1:
        _p5g=kpis_5est.get("pct_geracao",0); _p5c=kpis_5est.get("pct_conc",0)
        _p5o=kpis_5est.get("pct_om",0); _p5m=kpis_5est.get("pct_com",0)
        # Barras horas por causa
        _max_h=max(horas_por_causa.values()) if horas_por_causa else 1
        _hpc=""
        for _cn,_clr,_tc in [("Sobretensao CA","#0F9ED5","#0b6e96"),("Subtensao CA","#7E57C2","#534AB7"),("OFF (rede/coletivo)","#378ADD","#185FA5"),("Desconexao total","#E45C54","#A32D2D"),("OFF (equipamento/trip)","#E45C54","#A32D2D"),("Baixa irradiacao","#A8D8B9","#4A8C6B")]:
            _hv=horas_por_causa.get(_cn,0)
            _pw=int(_hv/_max_h*100) if _max_h>0 else 0
            _hpc+=("<div class='bh'><div class='bh-lbl' style='width:76px;font-size:7px'>"+_cn+"</div>"+"<div class='bh-track' style='height:9px'><div class='bh-fill' style='width:"+str(_pw)+"%;background:"+_clr+"'></div></div>"+"<div class='bh-val' style='width:44px;font-size:7px;color:"+_tc+"'>"+fmt_n(_hv,2)+" h</div></div>")
        html+=('<div class="pag">'
          '<div class="hdr"><div>'
            '<div><span class="tag orange">Ocorrências</span>'
                 '<span class="tag green">'+str(total_ev)+' eventos</span></div>'
            '<div class="title">Análise de Disponibilidade e Ocorrências</div>'
            '<div class="subtitle">Classificação de causa raiz — '+nm+'/'+str(ano)+'</div>'
          '</div><div class="brand">'+logo_s+' <span>Aevo Solar</span></div></div>'
          '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;flex-shrink:0">'
            '<div class="kpi gn"><div class="lbl">Disp. Geração</div><div class="val sm" style="color:#2CA66F" data-kpi="disp_ger" data-fmt="p2">'+pct_ger_s+'</div></div>'
            '<div class="kpi bu"><div class="lbl">Perdas Concess.</div><div class="val sm" style="color:#0F9ED5" data-kpi="pct_conc" data-fmt="p2">'+pct_conc_s+'</div></div>'
            '<div class="kpi" style="border-top-color:#E45C54"><div class="lbl">Perdas Eq./O&amp;M</div><div class="val sm" style="color:#E45C54" data-kpi="pct_om" data-fmt="p2">'+pct_om_s+'</div></div>'
            ''
            '<div class="kpi or"><div class="lbl">Total Eventos</div><div class="val sm" style="color:#E97132" data-kpi="total_ev" data-fmt="n0">'+str(total_ev)+'</div></div>'
            '<div class="kpi gn"><div class="lbl">Fechados</div><div class="val sm" style="color:#2CA66F">'+str(total_ev-em_aberto)+'</div></div>'
            '<div class="kpi"><div class="lbl">Em Aberto</div><div class="val sm">'+str(em_aberto)+'</div></div>'
            '<div class="kpi" style="border-top-color:#0E2841"><div class="lbl">Total Horas OFF</div><div class="val sm" data-kpi="total_h_off" data-fmt="h2">'+fmt_n(total_h,2)+' h</div></div>'
          '</div>'
          '<div style="flex:1;display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:5px;min-height:0">'
            '<div class="chart"><div class="chart-title">Distribuição de responsabilidade</div><div style="flex:1;position:relative;min-height:0"><canvas id="ch_donut"></canvas></div>'
              '<div class="chart-leg"><span><span class="ld" style="background:#2CA66F"></span>Geração '+pct_ger_s+'</span>'
              '<span><span class="ld" style="background:#A8D8B9"></span>Irrad. '+pct_irr_s+'</span>'
              '<span><span class="ld" style="background:#0F9ED5"></span>Concess. '+pct_conc_s+'</span>'
              '<span><span class="ld" style="background:#E45C54"></span>Eq/O&amp;M '+pct_om_s+'</span>'
              '</div></div>'
            '<div class="chart"><div class="chart-title">Horas OFF por causa</div>'
              '<div data-section="horas-causa" style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:2px 0">'+_hpc+'</div>'
              '<div class="chart-leg"><span><span class="ld" style="background:#0F9ED5"></span>Concessionária</span>'
              '<span><span class="ld" style="background:#E45C54"></span>Equip./O&amp;M</span>'
              '</div></div>'
            '<div class="chart"><div class="chart-title">Equipamentos com mais eventos</div>'
              '<div data-section="rank-equipamentos" style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:2px 0">'+rank_ev+'</div></div>'
            '<div class="chart"><div class="chart-title">Distribuição horária por responsável</div>'
              '<div style="flex:1;position:relative;min-height:0"><canvas id="ch_hora5"></canvas></div>'
              '<div class="chart-leg"><span><span class="ld" style="background:#0F9ED5"></span>Concessionária</span>'
              '<span><span class="ld" style="background:#E45C54"></span>Equip./O&amp;M</span>'
              '</div></div>'
            '<div class="chart" style="grid-column:span 2"><div class="chart-title">Mapa de eventos — Inversor × Dia do mês</div>'
              '<div style="flex:1;position:relative;min-height:0"><canvas id="ch_heat5"></canvas></div>'
              '<div class="chart-leg"><span><span class="ld" style="background:#D6F5E3"></span>OK</span>'
              '<span><span class="ld" style="background:#0F9ED5"></span>Concessionária</span>'
              '<span><span class="ld" style="background:#E45C54"></span>Equip./O&amp;M</span>'
              '</div></div>'
          '</div>'+ft("5/"+total_pags)+'</div>')
    # PAG 5 Tier 2 (original sem analytics)
    else:
        html+=('<div class="pag">'
          '<div class="hdr"><div>'
            '<div><span class="tag orange">Ocorrências</span>'
                 '<span class="tag green">'+str(total_ev)+' eventos</span></div>'
            '<div class="title">Ocorrências Operacionais</div>'
            '<div class="subtitle">Paradas parciais e alertas — '+nm+'/'+str(ano)+'</div>'
          '</div><div class="brand">'+logo_s+' <span>Aevo Solar</span></div></div>'
          '<div class="col-l16">'
            '<div class="fcol"><div class="panel" style="flex:1">'
              '<div class="panel-title">Registro de Ocorrências (sensor AC — paradas ≥ 5 min)</div>'
              '<table><thead><tr>'
                '<th>Categoria</th><th>Equipamento</th><th>Início</th><th>Fim</th>'
                '<th style="text-align:right">Duração</th><th>Faixa</th><th>Status</th>'
              '</tr></thead><tbody data-tbl="ocorrencias">'+al_rows+'</tbody></table></div></div>'
            '<div class="fcol">'
              '<div class="panel"><div class="panel-title">Resumo do Período</div>'
                '<div class="stat-g2">'
                  '<div class="stat2"><div class="lbl">Total eventos</div><div class="val" style="color:#E97132">'+str(total_ev)+'</div></div>'
                  '<div class="stat2"><div class="lbl">Fechados</div><div class="val" style="color:#2CA66F">'+str(total_ev-em_aberto)+'</div></div>'
                  '<div class="stat2"><div class="lbl">Em aberto</div><div class="val" style="color:#6B7C8F">'+str(em_aberto)+'</div></div>'
                  '<div class="stat2"><div class="lbl">Total horas off</div><div class="val">'+fmt_n(total_h,2)+' h</div></div>'
                '</div></div>'
              '<div class="panel"><div class="panel-title">Equipamentos com mais eventos</div>'+rank_ev+'</div>'
              '<div class="panel"><div class="panel-title">Distribuição horária das ocorrências</div>'
                '<div style="font-size:7.5px;font-weight:700;color:#555;margin-bottom:4px">Paradas parciais</div>'+dist_par_html+
                '<div style="font-size:7.5px;font-weight:700;color:#555;margin:6px 0 4px;padding-top:5px;border-top:1px solid #ECF1F5">Alertas</div>'+dist_al_html+'</div>'
              '<div class="callout"><div class="ct">Análise automática · Ocorrências</div>'
                '<div class="cb" data-analysis="page5" contenteditable="true" spellcheck="false">Aguardando dados...</div></div>'
            '</div>'
          '</div>'+ft("5/"+total_pags)+'</div>')
    # PAG 6 — Tabela de Ocorrências (Tier 1) ou skip (Tier 2)
    if is_tier1:
        # Split al_rows into pages of ~35 events
        al_row_list = al_rows.split('</tr>')
        al_row_list = [r+'</tr>' for r in al_row_list if '<tr>' in r]
        ROWS_PER_PAGE = 35
        n_table_pages = max(1, (len(al_row_list)+ROWS_PER_PAGE-1)//ROWS_PER_PAGE)
        total_pags = str(5 + n_table_pages)
        tbl_hdr = ('<table><thead><tr>'
            '<th>Categoria</th><th>Equipamento</th><th>Início</th><th>Fim</th>'
            '<th style="text-align:right">Duração</th><th>Faixa</th>'
            '<th>Causa</th><th>Responsável</th><th>Status</th>'
            '</tr></thead><tbody data-tbl="ocorrencias">')
        for tp in range(n_table_pages):
            chunk = al_row_list[tp*ROWS_PER_PAGE:(tp+1)*ROWS_PER_PAGE]
            pg_num = str(6+tp)
            is_last_table = (tp == n_table_pages-1)
            pag_cls = "pag-last" if is_last_table else "pag"
            side_panel = ""
            if tp == 0:
                side_panel = ('<div class="fcol">'
                  '<div class="panel"><div class="panel-title">Resumo do Período</div>'
                    '<div class="stat-g2">'
                      '<div class="stat2"><div class="lbl">Total eventos</div><div class="val" style="color:#E97132">'+str(total_ev)+'</div></div>'
                      '<div class="stat2"><div class="lbl">Fechados</div><div class="val" style="color:#2CA66F">'+str(total_ev-em_aberto)+'</div></div>'
                      '<div class="stat2"><div class="lbl">Em aberto</div><div class="val" style="color:#6B7C8F">'+str(em_aberto)+'</div></div>'
                      '<div class="stat2"><div class="lbl">Total horas off</div><div class="val">'+fmt_n(total_h,2)+' h</div></div>'
                    '</div></div>'
                  '<div class="callout"><div class="ct" contenteditable="true">Análise automática · Tabela de eventos</div>'
                    '<div class="cb" data-analysis="page6" contenteditable="true" spellcheck="false">Aguardando dados...</div></div>'
                '</div>')
            cont_lbl = " (cont.)" if tp > 0 else ""
            layout = "col-l16" if side_panel else "fcol"
            html+=('<div class="'+pag_cls+'">'
              '<div class="hdr"><div>'
                '<div><span class="tag blue">Registro</span>'
                     '<span class="tag orange">'+str(total_ev)+' eventos</span></div>'
                '<div class="title">Registro de Ocorrências'+cont_lbl+'</div>'
                '<div class="subtitle">Paradas parciais e alertas — '+nm+'/'+str(ano)+'</div>'
              '</div><div class="brand">'+logo_s+' <span>Aevo Solar</span></div></div>'
              '<div class="'+layout+'">'
                '<div class="fcol"><div class="panel" style="flex:1;overflow:hidden">'
                  '<div class="panel-title">Registro de Ocorrências (sensor AC — paradas ≥ 5 min)'+cont_lbl+'</div>'
                  +tbl_hdr+''.join(chunk)+'</tbody></table></div></div>'
                +side_panel+
              '</div>'+ft(pg_num+"/"+total_pags)+'</div>')


    if obs:
        html+=('<div class="pag-last">'
          '<div class="hdr"><div>'
            '<div class="title" contenteditable="true">Observações Técnicas</div>'
            '<div class="subtitle" contenteditable="true">'+nm+'/'+str(ano)+' — '+usina+'</div>'
          '</div><div class="brand">'+logo_s+'</div></div>'
          '<div class="callout" style="flex:1">'
            '<div class="cb" contenteditable="true">'+obs_txt+'</div>'
          '</div>'+ft()+'</div>')

    # ── Dataset cru + vocabulario (para edicao client-side) ──
    _raw_dataset = _build_raw_dataset(cad, kpis, kpis_5est, df_daily, df_paradas,
                                       pvsyst, tarifa, poa, fonte_poa, fonte_energia,
                                       ano, mes, disp_dia_inv)
    _raw_json = _json_mod.dumps(_raw_dataset, ensure_ascii=False)
    _vocab_json = _json_mod.dumps(_VOCAB_DEFAULT, ensure_ascii=False)
    try:
        from _dinamico import render_dinamico_css, render_dinamico_drawer_html, render_dinamico_js
        _dyn_css = render_dinamico_css()
        _dyn_drawer = render_dinamico_drawer_html()
        _dyn_js = render_dinamico_js()
    except Exception:
        _dyn_css = ""; _dyn_drawer = ""; _dyn_js = ""
    html += ('<style>' + _dyn_css + '</style>' + _dyn_drawer +
             '<script id="__raw_data__" type="application/json">' + _raw_json + '</script>'
             '<script id="__vocab_default__" type="application/json">' + _vocab_json + '</script>'
             '<script>'
             'window.__RAW_DATA = JSON.parse(document.getElementById("__raw_data__").textContent);'
             'window.__VOCAB_DEFAULT = JSON.parse(document.getElementById("__vocab_default__").textContent);'
             'window.__STATE = {'
             '  tarifa_rs_kwh: window.__RAW_DATA.estado_inicial.tarifa_rs_kwh,'
             '  poa_kwh_m2: window.__RAW_DATA.estado_inicial.poa_kwh_m2,'
             '  inversores_excluidos: [],'
             '  paradas_editadas: {},'
             '  vocab: JSON.parse(JSON.stringify(window.__VOCAB_DEFAULT)),'
             '  usina_overrides: {}'
             '};'
             '</script>'
             '<script>' + _dyn_js + '</script>')

    # Scripts Chart.js
    html+=('<script>window.addEventListener("load",function(){'
      'Chart.defaults.devicePixelRatio=2;'
      'var D='+inv_data_js+',M='+str(inv_med_js)+',L='+inv_labels_js+';'
      'var c1=document.getElementById("ch_inv");'
      'if(c1){c1.style.height=c1.parentElement.offsetHeight+"px";'
      'new Chart(c1,{type:"bar",data:{labels:L,datasets:['
        '{label:"Energia (kWh)",data:D,'
         'backgroundColor:D.map(function(v){return v<M*.85?"rgba(228,92,84,.82)":"rgba(15,158,213,.78)"}),'
         'borderWidth:0},'
        '{label:"Média",data:Array(L.length).fill(Math.round(M)),'
         'type:"line",borderColor:"#E97132",borderWidth:1.5,pointRadius:0,fill:false,tension:0}'
      ']},options:{responsive:true,maintainAspectRatio:false,'
        'plugins:{legend:{position:"top",labels:{boxWidth:8,font:{size:7},padding:5}}},'
        'scales:{x:{ticks:{font:{size:7.5}},grid:{display:false}},'
                'y:{ticks:{font:{size:7},callback:function(v){return v>=1000?(v/1000).toFixed(0)+"k":""+v}},'
                   'beginAtZero:true,grid:{color:"rgba(0,0,0,.04)"}}}}});}'
      'var devD='+dev_data_js+';'
      'var c2=document.getElementById("ch_dev");'
      'if(c2){c2.style.height="60px";'
      'new Chart(c2,{type:"bar",'
        'data:{labels:["Energia","PR","Irradiação POA","Cobertura"],'
          'datasets:[{data:devD,'
            'backgroundColor:devD.map(function(v){return v<0?"rgba(228,92,84,.82)":"rgba(44,166,111,.82)"}),'
            'borderWidth:0}]},'
        'options:{responsive:true,maintainAspectRatio:false,'
          'plugins:{legend:{display:false}},'
          'scales:{x:{ticks:{font:{size:7}},grid:{display:false}},'
                  'y:{ticks:{font:{size:7}},grid:{color:"rgba(0,0,0,.04)"}}}}});}'
      'var c3=document.getElementById("ch_disp");'
      'if(c3){c3.style.height=c3.parentElement.offsetHeight+"px";new Chart(c3,'+ch_disp_json+');}'
      'var c4=document.getElementById("ch_poa");'
      'if(c4){c4.style.height=c4.parentElement.offsetHeight+"px";new Chart(c4,'+ch_poa_json+');}'
      'var c5d=document.getElementById("ch_donut");'
      'if(c5d){c5d.style.height=c5d.parentElement.offsetHeight+"px";new Chart(c5d,{type:"doughnut",'
        'data:{labels:["Geração","Baixa Irrad.","Concessionária","Equip./O&M"],'
        'datasets:[{data:['+str(kpis_5est.get("pct_ger_pure",99) if kpis_5est else 99)+','
          +str(kpis_5est.get("pct_irr",0) if kpis_5est else 0)+','
          +str(kpis_5est.get("pct_conc",0) if kpis_5est else 0)+','
          +str(kpis_5est.get("pct_om",0) if kpis_5est else 0)+'],'
        'backgroundColor:["#2CA66F","#A8D8B9","#0F9ED5","#E45C54"],borderWidth:1,borderColor:"#fff"}]},'
        'options:{responsive:true,maintainAspectRatio:false,cutout:"62%",plugins:{legend:{display:false}}},'
        'plugins:[{id:"ct",afterDraw:function(ch){var w=ch.width,h=ch.height,cx=ch.ctx;cx.save();'
          'cx.textAlign="center";cx.textBaseline="middle";cx.font="bold 18px Arial";cx.fillStyle="#2CA66F";'
          'cx.fillText("'+pct_ger_s+'",w/2,h/2-5);cx.font="bold 7px Arial";cx.fillStyle="#6B7C8F";'
          'cx.fillText("DISPONÍVEL",w/2,h/2+10);cx.restore();}}]});}'
      'var c5h=document.getElementById("ch_hora5");'
      'if(c5h){c5h.style.height=c5h.parentElement.offsetHeight+"px";new Chart(c5h,{type:"bar",'
        'data:{labels:["Partida 06-08h","Pico M 08-12h","Pico T 12-17h","Declínio 17-17:30"],'
        'datasets:[{label:"Concessionária",data:'+conc_faixa_js+',backgroundColor:"#0F9ED5"},'
          '{label:"Equip./O&M",data:'+eqom_faixa_js+',backgroundColor:"#E45C54"},'
          ']},'
        'options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},'
          'scales:{x:{stacked:true,ticks:{font:{size:7}},grid:{display:false}},'
          'y:{stacked:true,ticks:{font:{size:7}},grid:{color:"rgba(0,0,0,.04)"}}}}});}'
      'var c5hm=document.getElementById("ch_heat5");'
      'function _drawHeat(){var rect=c5hm.parentElement.getBoundingClientRect();'
        'if(rect.width<10||rect.height<10){requestAnimationFrame(_drawHeat);return;}'
        'var _hd='+heatmap_js+',_hi='+heatmap_inv_js+',_dm='+str(dias_mes)+';'
        'var cx=c5hm.getContext("2d");var W=rect.width,H=rect.height;'
        'c5hm.width=W*2;c5hm.height=H*2;c5hm.style.width=W+"px";c5hm.style.height=H+"px";cx.scale(2,2);'
        'var pL=36,pR=4,pT=12,pB=4,cw=(W-pL-pR)/_dm,ch2=(H-pT-pB)/Math.max(_hi.length,1);'
        'var cm={0:"#D6F5E3",2:"#0F9ED5",3:"#E45C54"};'
        'cx.font="bold 6px Arial";cx.fillStyle="#6B7C8F";cx.textAlign="center";'
        'for(var d=0;d<_dm;d++){cx.fillText(""+(d+1),pL+d*cw+cw/2,pT-3);}'
        'cx.textAlign="right";cx.textBaseline="middle";cx.font="bold 6px Arial";'
        'for(var i=0;i<_hi.length;i++){cx.fillStyle="#17324A";cx.fillText(_hi[i].replace("Inverter","Inv"),pL-2,pT+i*ch2+ch2/2);'
          'for(var d=0;d<_dm;d++){var k=_hi[i]+"_"+(d+1);var t=_hd[k]||0;cx.fillStyle=cm[t];'
            'cx.fillRect(pL+d*cw+0.5,pT+i*ch2+0.5,cw-1,ch2-1);}}'
        'requestAnimationFrame(function(){window.__report_ready=true;});}'
      'if(c5hm){requestAnimationFrame(_drawHeat);}else{requestAnimationFrame(function(){window.__report_ready=true;});}'
    '});</script></body></html>')

    import re as _re2; html=_re2.sub(r"\\u([0-9a-fA-F]{4})",lambda m:chr(int(m.group(1),16)),html)
    return html

def _render_pdf_with_page(page, html_str):
    """Dado um Page do Playwright, escreve HTML em tmp e gera PDF, retornando bytes."""
    with tempfile.NamedTemporaryFile(suffix=".html",delete=False,mode="w",encoding="utf-8") as f:
        f.write(html_str); tmp_html=f.name
    tmp_pdf=tmp_html.replace(".html",".pdf")
    try:
        page.goto("file://"+tmp_html, wait_until="networkidle")
        try:
            page.wait_for_function("window.__report_ready===true", timeout=30000)
        except Exception:
            page.wait_for_timeout(6000)
        page.wait_for_timeout(300)
        page.pdf(path=tmp_pdf, format="A4", landscape=True,
                 margin={"top":"0","bottom":"0","left":"0","right":"0"},
                 print_background=True, prefer_css_page_size=True)
        with open(tmp_pdf,"rb") as f: return f.read()
    finally:
        if os.path.exists(tmp_html): os.unlink(tmp_html)
        if os.path.exists(tmp_pdf):  os.unlink(tmp_pdf)

def html_para_pdf(html_str):
    """Gera PDF de UM html. Usa playwright.sync_api (sem event loop async)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        try: st.error("Playwright nao instalado: "+str(e))
        except Exception: pass
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_viewport_size({"width":1123,"height":794})
            try:
                return _render_pdf_with_page(page, html_str)
            finally:
                browser.close()
    except Exception as e:
        try: st.error("Erro Playwright: "+str(e))
        except Exception: pass
        return None

def htmls_para_pdfs_batch(htmls, progress_cb=None):
    """Gera PDFs para uma lista de htmls reusando 1 browser. progress_cb(i, n, label) opcional.
    Retorna dict {idx: pdf_bytes_or_None}."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        try: st.error("Playwright nao instalado: "+str(e))
        except Exception: pass
        return {i: None for i in range(len(htmls))}
    out = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_viewport_size({"width":1123,"height":794})
            try:
                for i, item in enumerate(htmls):
                    label = item[0] if isinstance(item, tuple) else str(i)
                    html_str = item[1] if isinstance(item, tuple) else item
                    if progress_cb:
                        try: progress_cb(i, len(htmls), label)
                        except Exception: pass
                    try:
                        out[i] = _render_pdf_with_page(page, html_str)
                    except Exception as e:
                        out[i] = None
                        try: st.warning("PDF falhou para "+str(label)+": "+str(e))
                        except Exception: pass
            finally:
                browser.close()
    except Exception as e:
        try: st.error("Erro Playwright (batch): "+str(e))
        except Exception: pass
    return out


# ── Supabase (cache persistente populado pelo ETL) ───────────────────────
_SB_CONN_KW = None
def _sb_load_env():
    """Carrega credenciais Supabase (st.secrets > env vars > .env)."""
    global _SB_CONN_KW
    if _SB_CONN_KW is not None: return _SB_CONN_KW
    host = _env_module.get("SUPABASE_HOST")
    password = _env_module.get("SUPABASE_PASSWORD")
    if not host or not password:
        _SB_CONN_KW = {}
        return _SB_CONN_KW
    ref = host.split(".")[1]
    region = _env_module.get("SUPABASE_REGION", "us-east-1")
    _SB_CONN_KW = dict(
        host=f"aws-1-{region}.pooler.supabase.com", port=5432,
        dbname=_env_module.get("SUPABASE_DB","postgres"),
        user=f"postgres.{ref}", password=password,
        sslmode="require", connect_timeout=10,
    )
    return _SB_CONN_KW

def _sb_connect():
    kw = _sb_load_env()
    if not kw: return None
    try: return psycopg2.connect(**kw)
    except Exception: return None


def coletar_do_supabase(pid, ano, mes):
    """Le dados de reports.* (Supabase). Retorna dict no mesmo formato de
    coletar_dados_usina, ou None se nao houver dados ainda."""
    conn = _sb_connect()
    if conn is None: return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT energia_real_kwh, energia_esperada_kwh, atingimento_pct,
                       pr_real, pr_esperado, poa_kwh_m2, poa_fonte,
                       disp_geracao_pct, disp_operacao_pct, cobertura_dias, dias_com_dado,
                       tier, pct_ger_pure, pct_irr, pct_conc, pct_om,
                       total_eventos, total_horas_off, em_aberto, is_closed
                FROM reports.kpis_mensal
                WHERE plant_id=%s AND ano=%s AND mes=%s
            """, (pid, ano, mes))
            row = cur.fetchone()
            if not row:
                conn.close(); return None
            (er, ee, at, pr_r, pr_e, poa, poa_fonte, disp_g, disp_o, cob, ddd,
             tier, pct_g, pct_i, pct_c, pct_o, tot_ev, tot_h, em_ab, is_closed) = row
            cur.execute("""
                SELECT dia, inversor, modelo, energia_kwh
                FROM reports.energy_daily
                WHERE plant_id=%s AND dia >= make_date(%s,%s,1)
                  AND dia <  make_date(%s,%s,1) + INTERVAL '1 month'
                ORDER BY dia, inversor
            """, (pid, ano, mes, ano, mes))
            ed_rows = cur.fetchall()
            cur.execute("""
                SELECT inversor, inicio, fim, duracao_h, tipo, causa, responsavel
                FROM reports.paradas
                WHERE plant_id=%s AND ano=%s AND mes=%s
                ORDER BY inicio
            """, (pid, ano, mes))
            par_rows = cur.fetchall()
            cur.execute("""
                SELECT dia, inversor, disp_pct
                FROM reports.disp_dia_inversor
                WHERE plant_id=%s AND ano=%s AND mes=%s
            """, (pid, ano, mes))
            disp_rows = cur.fetchall()
        conn.close()
    except Exception:
        try: conn.close()
        except: pass
        return None

    # Cad e pvsyst do AEVO (fonte de verdade)
    df_cad = sql("SELECT name,nominal_power_kwp,om_contract,contract_end FROM public.plant_plant WHERE id="+str(pid))
    if df_cad.empty: return None
    cad = df_cad.iloc[0].to_dict()
    kwp = float(cad.get("nominal_power_kwp") or 0)
    df_pv = load_pvsyst(pid, ano, mes)
    pvsyst = df_pv.iloc[0].to_dict() if not df_pv.empty else {}

    # Reconstruir DataFrames
    df_daily = pd.DataFrame([{"dia": r[0], "inversor": r[1], "modelo": r[2],
                               "energia_kwh": float(r[3])} for r in ed_rows])
    if df_daily.empty: return None  # ainda sem dados — usa fallback
    df_paradas = pd.DataFrame([{"inversor": r[0],
                                 "inicio": r[1].strftime("%d/%m/%Y %H:%M") if r[1] else "",
                                 "fim": r[2].strftime("%d/%m/%Y %H:%M") if r[2] else "",
                                 "duracao_h": float(r[3]), "tipo": r[4],
                                 "causa": r[5] or "", "responsavel": r[6] or ""}
                                for r in par_rows]) if par_rows else pd.DataFrame()
    disp_dia_inv = {}
    for dia, inv, pct in disp_rows:
        disp_dia_inv.setdefault(int(dia), {})[str(inv)] = float(pct)

    # kpis e kpis_5est reconstruidos a partir de kpis_mensal
    dias_mes = calendar.monthrange(ano, mes)[1]
    # Reconstroi df_inv via groupby
    df_inv = df_daily.groupby("inversor").agg(
        energia_kwh=("energia_kwh","sum"), dias_com_dado=("dia","count")
    ).reset_index()
    df_inv["energia_kwh"] = df_inv["energia_kwh"].round(2)
    total_en = float(df_inv["energia_kwh"].sum())
    df_inv["pct"] = (df_inv["energia_kwh"]/total_en*100).round(1) if total_en else 0
    df_inv["esp_kwh_kwp"] = (df_inv["energia_kwh"]/(kwp/len(df_inv))).round(2) if (kwp and len(df_inv)) else 0
    df_inv["disp_ger_pct"] = (df_inv["dias_com_dado"]/dias_mes*100).round(1)
    # Reconstroi horas_off e disp_op_pct a partir das paradas (Supabase)
    horas_off_lookup = {}
    if not df_paradas.empty:
        for _, r in df_paradas.iterrows():
            inv = str(r["inversor"])
            horas_off_lookup[inv] = horas_off_lookup.get(inv, 0.0) + float(r.get("duracao_h", 0))
    HORAS_SOLARES_POR_DIA = 11.5  # mesmo intervalo do isc_5estados_mensal
    horas_solares_inv = dias_mes * HORAS_SOLARES_POR_DIA
    df_inv["horas_off"] = df_inv["inversor"].apply(
        lambda nm: round(horas_off_lookup.get(str(nm), 0.0), 2))
    df_inv["disp_op_pct"] = df_inv["horas_off"].apply(
        lambda h: round((1 - h/horas_solares_inv)*100, 2) if horas_solares_inv > 0 else 0.0)
    df_inv = df_inv.sort_values("energia_kwh", ascending=False).reset_index(drop=True)
    df_dia = df_daily.groupby("dia")["energia_kwh"].sum().reset_index()

    kpis = {
        "energia_real": float(er or 0), "ee": float(ee or 0), "at": float(at or 0),
        "pr_real": float(pr_r or 0), "pr_e": float(pr_e or 0),
        "esp_kwp": (float(er or 0)/kwp) if kwp else 0,
        "disp_ger": float(disp_g or 0),
        "glob_inc": float(pvsyst.get("glob_inc") or 0),
        "p50": float(pvsyst.get("p50") or 0), "p75": float(pvsyst.get("p75") or 0),
        "dias_com_dado": int(ddd or 0), "cob_pct": float(cob or 0),
        "df_inv": df_inv, "df_dia": df_dia,
        "var_poa": (round((float(poa or 0)-float(pvsyst.get("glob_inc") or 0))/float(pvsyst.get("glob_inc") or 1)*100, 1)
                    if (poa and pvsyst.get("glob_inc")) else 0),
    }
    kpis_5est = None
    if tier == 1:
        kpis_5est = {
            "pct_geracao": float(pct_g or 0) if pct_g is not None else float(disp_g or 0),
            "pct_ger_pure": float(pct_g or 0) if pct_g is not None else 99.0,
            "pct_irr": float(pct_i or 0), "pct_conc": float(pct_c or 0),
            "pct_om": float(pct_o or 0), "pct_com": 0.0, "tier": 1,
        }
    df_al = pd.DataFrame()  # alertas continua do banco AEVO se necessario
    df_poa_dia = pd.DataFrame()  # painel nao depende disso para HTML basico
    tem_estacao = False  # marca como sem estacao no caso supabase (sem dados POA por dia ainda)

    return {
        "cad": cad, "kwp": kwp, "pvsyst": pvsyst,
        "ps_id_isc": ISC_MAP.get(pid), "tem_estacao": tem_estacao,
        "df_al": df_al, "df_daily": df_daily, "df_paradas": df_paradas,
        "df_disp_op": pd.DataFrame(), "df_poa_dia": df_poa_dia,
        "disp_op_media": float(disp_o or 0), "disp_dia_inv": disp_dia_inv,
        "kpis": kpis, "kpis_5est": kpis_5est,
        "poa": float(poa or 0), "fonte_poa": poa_fonte or "n/a",
        "fonte_energia": "BD AEVO",
        "notes": ["lido do supabase"],
        "_from_supabase": True,
    }


def coletar_dados_usina(pid, ano, mes, poa_manual=0.0, pv_overrides=None):
    """Coleta TODOS os dados para uma usina+periodo, sem gerar HTML.
    Retorna dict com cad, kpis, df_daily, df_paradas, df_disp_op, disp_dia_inv,
    kpis_5est, pvsyst, poa, fonte_poa, fonte_energia, df_al, df_poa_dia, status, notes."""
    if pv_overrides is None: pv_overrides = {}
    notes=[]
    df_cad = sql("SELECT name,nominal_power_kwp,om_contract,contract_end FROM public.plant_plant WHERE id="+str(pid))
    if df_cad.empty:
        return {"error": "usina id="+str(pid)+" nao encontrada"}
    cad = df_cad.iloc[0].to_dict()
    kwp = float(cad.get("nominal_power_kwp") or 0)
    df_pv = load_pvsyst(pid, ano, mes)
    pvsyst = df_pv.iloc[0].to_dict() if not df_pv.empty else {}
    for k,v in pv_overrides.items():
        if (not pvsyst.get(k)) and v: pvsyst[k] = v

    ps_id_isc = ISC_MAP.get(pid)
    df_al = pd.DataFrame() if ps_id_isc else load_alertas(pid, ano, mes)
    fonte_energia = "Banco AEVO"; df_daily = pd.DataFrame(); ghost_pks = set(); token = None
    if ps_id_isc:
        token = isc_login()
        if token:
            _c_en = _cache_load(ps_id_isc, ano, mes, "energia") if _mes_fechado(ano, mes) else None
            if _c_en:
                df_daily, _msg, ghost_pks = _c_en; notes.append("energia: cache")
            else:
                df_daily, _msg, ghost_pks = isc_energia_mensal(ps_id_isc, ano, mes, token)
                if not df_daily.empty and _mes_fechado(ano, mes):
                    _cache_save(ps_id_isc, ano, mes, "energia", (df_daily, _msg, ghost_pks))
            if not df_daily.empty:
                fonte_energia = "iSolarCloud"
            else:
                notes.append("ISC sem dados ("+_msg+"), fallback banco")
    if df_daily.empty:
        df_daily = load_inverter_daily_banco(pid, ano, mes)
    if df_daily.empty:
        return {"error": "sem dados de geracao para o periodo", "cad": cad, "notes": notes}

    glob_inc = float(pvsyst.get("glob_inc") or 0)
    glob_hor = float(pvsyst.get("glob_hor") or 0)
    poa_banco, ghi_banco = load_poa_banco(pid, ano, mes)
    poa, fonte_poa = resolve_poa(poa_manual, poa_banco, glob_inc, glob_hor, ghi_banco)
    tem_estacao = len(get_ws_ids(pid)) > 0
    df_poa_dia = load_poa_diaria(pid, ano, mes) if tem_estacao else pd.DataFrame()
    kpis_5est = None; disp_dia_inv = None; df_disp_op = pd.DataFrame(); df_paradas = pd.DataFrame(); disp_op_media = 0.0
    if ps_id_isc and token:
        _c_5e = _cache_load(ps_id_isc, ano, mes, "5estados") if _mes_fechado(ano, mes) else None
        if _c_5e:
            df_disp_op, df_paradas, disp_op_media, kpis_5est, disp_dia_inv = _c_5e
            notes.append("5est: cache")
        else:
            df_disp_op, df_paradas, disp_op_media, kpis_5est, disp_dia_inv = isc_5estados_mensal(
                ps_id_isc, ano, mes, token, excluir_pks=tuple(sorted(ghost_pks)) if ghost_pks else None)
            if _mes_fechado(ano, mes):
                _cache_save(ps_id_isc, ano, mes, "5estados",
                            (df_disp_op, df_paradas, disp_op_media, kpis_5est, disp_dia_inv))
    else:
        df_disp_op, df_paradas, disp_op_media = load_disp_operacao(pid, ano, mes)

    dias_mes = calendar.monthrange(ano, mes)[1]
    kpis = calc_kpis(df_daily, dias_mes, kwp, poa, pvsyst, df_disp_op)

    return {
        "cad": cad, "kwp": kwp, "pvsyst": pvsyst,
        "ps_id_isc": ps_id_isc, "tem_estacao": tem_estacao,
        "df_al": df_al, "df_daily": df_daily, "df_paradas": df_paradas,
        "df_disp_op": df_disp_op, "df_poa_dia": df_poa_dia,
        "disp_op_media": disp_op_media, "disp_dia_inv": disp_dia_inv,
        "kpis": kpis, "kpis_5est": kpis_5est,
        "poa": poa, "fonte_poa": fonte_poa,
        "fonte_energia": fonte_energia,
        "notes": notes,
    }


def gerar_relatorio_html(pid, ano, mes, poa_manual=0.0, tarifa_input=0.0, obs_input="",
                         pv_overrides=None, silent=True, prefer_supabase=True):
    """Pipeline completo single-shot — sem efeitos colaterais de UI quando silent=True.
    Por padrao tenta ler do Supabase primeiro (rapido, ~1s); cai para API ISC se nao tiver.
    Retorna (html, filename, status_str)."""
    data = None
    if prefer_supabase and poa_manual == 0.0 and not pv_overrides:
        # so usa cache supabase se nao tem overrides (POA manual, PVsyst manual)
        try: data = coletar_do_supabase(pid, ano, mes)
        except Exception: data = None
    if data is None:
        data = coletar_dados_usina(pid, ano, mes, poa_manual, pv_overrides)
    if "error" in data:
        return None, None, "ERRO: "+data["error"]
    cad = data["cad"]; kpis = data["kpis"]; kpis_5est = data["kpis_5est"]
    df_daily = data["df_daily"]; df_paradas = data["df_paradas"]; df_al = data["df_al"]
    df_poa_dia = data["df_poa_dia"]; pvsyst = data["pvsyst"]
    poa = data["poa"]; fonte_poa = data["fonte_poa"]; fonte_energia = data["fonte_energia"]
    disp_op_media = data["disp_op_media"]; disp_dia_inv = data["disp_dia_inv"]
    tem_estacao = data["tem_estacao"]; notes = data["notes"]
    glob_inc = float(pvsyst.get("glob_inc") or 0)
    dias_mes = calendar.monthrange(ano, mes)[1]
    glob_inc_dia = glob_inc/dias_mes if (glob_inc and dias_mes) else 0

    alert_dias = []
    df_dia_tmp = kpis.get("df_dia", pd.DataFrame())
    if not df_dia_tmp.empty and not df_daily.empty:
        _vals_a = sorted([float(v) for v in df_dia_tmp["energia_kwh"] if float(v) > 0])
        if len(_vals_a) >= 5:
            _med_a = _vals_a[len(_vals_a)//2]
            _inv_dia_a = {}
            for _, _r_a in df_daily.iterrows():
                _dd_a = _r_a["dia"]; _di_a = int(_dd_a.strftime("%d")) if hasattr(_dd_a, "strftime") else int(str(_dd_a)[8:10])
                _in_a = str(_r_a["inversor"])
                if _di_a not in _inv_dia_a: _inv_dia_a[_di_a] = {}
                _inv_dia_a[_di_a][_in_a] = _inv_dia_a[_di_a].get(_in_a, 0) + float(_r_a["energia_kwh"])
            for _, _r_a in df_dia_tmp.iterrows():
                _v_a = float(_r_a["energia_kwh"]); _d_a = _r_a["dia"]
                _di = int(_d_a.strftime("%d")) if hasattr(_d_a, "strftime") else int(str(_d_a)[8:10])
                if _v_a > _med_a*2.5 and _v_a > 20000: alert_dias.append(_di)
                if _v_a < _med_a*0.10:
                    _id_a = _inv_dia_a.get(_di, {})
                    if _id_a:
                        _iv = sorted(_id_a.values()); _mi = _iv[len(_iv)//2] if _iv else 0
                        _nb = sum(1 for ev in _iv if ev < _mi*0.20) if _mi > 0 else len(_iv)
                        if _nb/max(len(_iv), 1) <= 0.70 and _nb <= 2 and _mi > 100: alert_dias.append(_di)

    if disp_dia_inv:
        ch_disp = chart_disp_5est(disp_dia_inv, dias_mes, ano, mes, df_daily)
    else:
        ch_disp = chart_disp(df_daily, dias_mes, ano, mes)
    charts = {
        "inv":     chart_inv(kpis.get("df_inv", pd.DataFrame())),
        "desvios": chart_desvios(kpis, poa, pvsyst),
        "disp":    ch_disp,
        "ger_dia": chart_ger_dia_alert(kpis.get("df_dia", pd.DataFrame()), dias_mes, ano, mes, alert_dias) if alert_dias else chart_ger_dia(kpis.get("df_dia", pd.DataFrame()), dias_mes, ano, mes),
        "poa":     chart_poa_dia(df_poa_dia, glob_inc_dia, dias_mes, ano, mes),
    }
    html = gerar_html(cad, kpis, df_al, df_paradas, tarifa_input, obs_input, pvsyst,
                      ano, mes, charts, tem_estacao, poa, fonte_poa, disp_op_media,
                      fonte_energia, kpis_5est, disp_dia_inv, df_daily)
    nm_curto = str(cad.get("acronym") or cad.get("name", "UFV")).replace(" ", "_")[:15]
    filename = "relatorio_"+nm_curto+"_"+str(ano)+"_"+str(mes).zfill(2)+".html"
    status = "OK | fonte: "+fonte_energia+(" | "+", ".join(notes) if notes else "")
    return html, filename, status


def gerar_relatorio_executivo_html(pid, ano, mes, poa_manual=0.0, tarifa_input=0.0,
                                     pv_overrides=None, prefer_supabase=True,
                                     incluir_drawer=True):
    """Versao EXECUTIVA do relatorio — formato A4 retrato similar ao modelo PDF cliente.

    Args:
      pid, ano, mes: identificadores da usina/periodo
      poa_manual, tarifa_input, pv_overrides: overrides opcionais
      prefer_supabase: tenta cache Supabase antes de coletar da API
      incluir_drawer: se True, embute o sistema dinamico de edicao (drawer + JS)

    Returns: (html, filename, status_str)
    """
    import _executivo as _exec_mod
    import json as _json_mod_exec

    data = None
    if prefer_supabase and poa_manual == 0.0 and not pv_overrides:
        try: data = coletar_do_supabase(pid, ano, mes)
        except Exception: data = None
    if data is None:
        data = coletar_dados_usina(pid, ano, mes, poa_manual, pv_overrides)
    if "error" in data:
        return None, None, "ERRO: " + data["error"]

    cad = data["cad"]
    fonte_energia = data.get("fonte_energia", "")
    notes = data.get("notes", []) or []
    tarifa = tarifa_input or 0.0
    poa = data.get("poa", 0)
    fonte_poa = data.get("fonte_poa", "")

    # CSS executivo + (opcional) CSS dinamico do drawer
    css = _exec_mod.render_executivo_css()
    body_exec = _exec_mod.render_executivo_html(data, ano, mes, logo_b64=LOGO_B64)

    head = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f'<title>Relatório Mensal — {cad.get("name", "UFV")} — {mes:02d}/{ano}</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
        '<style>' + css + '</style>'
        '</head>'
    )

    # Sistema dinamico opcional (drawer + JS reativo)
    drawer_block = ""
    if incluir_drawer:
        try:
            _raw_dataset = _build_raw_dataset(
                cad, data["kpis"], data.get("kpis_5est"), data["df_daily"],
                data["df_paradas"], data["pvsyst"], tarifa, poa,
                fonte_poa, fonte_energia, ano, mes, data.get("disp_dia_inv"))
            _raw_json = _json_mod_exec.dumps(_raw_dataset, ensure_ascii=False)
            _vocab_json = _json_mod_exec.dumps(_VOCAB_DEFAULT, ensure_ascii=False)
            from _dinamico import (render_dinamico_css, render_dinamico_drawer_html,
                                     render_dinamico_js)
            _dyn_css = render_dinamico_css()
            _dyn_drawer = render_dinamico_drawer_html()
            _dyn_js = render_dinamico_js()
            drawer_block = (
                '<style>' + _dyn_css + '</style>' + _dyn_drawer +
                '<script id="__raw_data__" type="application/json">' + _raw_json + '</script>'
                '<script id="__vocab_default__" type="application/json">' + _vocab_json + '</script>'
                '<script>'
                'window.__RAW_DATA = JSON.parse(document.getElementById("__raw_data__").textContent);'
                'window.__VOCAB_DEFAULT = JSON.parse(document.getElementById("__vocab_default__").textContent);'
                'window.__STATE = {'
                '  tarifa_rs_kwh: window.__RAW_DATA.estado_inicial.tarifa_rs_kwh,'
                '  poa_kwh_m2: window.__RAW_DATA.estado_inicial.poa_kwh_m2,'
                '  inversores_excluidos: [],'
                '  paradas_editadas: {},'
                '  vocab: JSON.parse(JSON.stringify(window.__VOCAB_DEFAULT)),'
                '  usina_overrides: {}'
                '};'
                '</script>'
                '<script>' + _dyn_js + '</script>'
            )
        except Exception as e:
            print(f"  [executivo] drawer dinamico falhou: {e}")
            drawer_block = ""

    html = head + body_exec + drawer_block + '</html>'
    nm_curto = str(cad.get("acronym") or cad.get("name", "UFV")).replace(" ", "_")[:15]
    filename = "relatorio_exec_" + nm_curto + "_" + str(ano) + "_" + str(mes).zfill(2) + ".html"
    status = "OK | fonte: " + fonte_energia + (" | " + ", ".join(notes) if notes else "")
    return html, filename, status

# â\x94\x80â\x94\x80 Streamlit â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80â\x94\x80
st.set_page_config(page_title="Relatorios OM - Aevo Solar", page_icon="☀️", layout="wide")

# ── Auth (Supabase reports.users + bcrypt) ─────────────────────────────
try:
    import auth as _auth_module
    _auth_user = _auth_module.ensure_login(st)
except ImportError:
    _auth_user = None  # auth desabilitado se modulo ausente (uso local)

col1,col2=st.columns([1,5])
with col1: st.image("data:image/png;base64,"+LOGO_B64, width=130)
with col2:
    st.markdown("## Gerador de Relatorios Mensais — AEVO19")
    st.markdown("**O&M — Usinas Fotovoltaicas — Aevo Solar**")
    if _auth_user:
        st.caption("Logado como **"+_auth_user.get("nome","")+"** ("+_auth_user.get("username","")+", "+_auth_user.get("role","")+")")
st.divider()

# ── Modo Em Lote ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _batch_load_listas():
    orgs   = sql("SELECT id,name FROM public.organization_organization WHERE id IN (SELECT DISTINCT organization_id FROM public.plant_plant WHERE is_active=TRUE AND is_parent=FALSE AND organization_id IS NOT NULL) ORDER BY name")
    plants = sql("SELECT id,name,organization_id FROM public.plant_plant WHERE is_active=TRUE AND is_parent=FALSE ORDER BY name")
    return orgs, plants

with st.expander("🚀 Geracao em Lote — multiplas usinas", expanded=False):
    _orgs_b, _plants_b = _batch_load_listas()
    cb1, cb2, cb3 = st.columns([2,1,1])
    with cb1:
        cliente_b = st.selectbox("Cliente (filtro)", ["Todos"]+_orgs_b["name"].tolist(), key="batch_cli")
    with cb2:
        ano_b = st.selectbox("Ano", [2026,2025,2024], key="batch_ano")
    with cb3:
        mes_b = st.selectbox("Mes", list(range(1,13)), format_func=lambda m:MESES[m], index=1, key="batch_mes")

    if cliente_b == "Todos":
        _plants_f_b = _plants_b
    else:
        _oid_b = _orgs_b[_orgs_b["name"]==cliente_b]["id"].values[0]
        _plants_f_b = _plants_b[_plants_b["organization_id"]==_oid_b]
    _opts_b = {r["name"]: int(r["id"]) for _,r in _plants_f_b.iterrows()}

    usinas_sel = st.multiselect("Usinas (selecione varias)", list(_opts_b.keys()), key="batch_usinas")

    if usinas_sel:
        st.caption("Preencha POA e Tarifa por usina (deixe 0 para usar PVsyst/banco). Observacoes opcionais.")
        df_batch = pd.DataFrame([
            {"Usina": u, "POA (kWh/m2)": 0.0, "Tarifa (R$/kWh)": 0.0, "Observacoes": ""}
            for u in usinas_sel
        ])
        edited = st.data_editor(
            df_batch, use_container_width=True, hide_index=True, key="batch_editor",
            column_config={
                "Usina": st.column_config.TextColumn(disabled=True),
                "POA (kWh/m2)": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.2f"),
                "Tarifa (R$/kWh)": st.column_config.NumberColumn(min_value=0.0, step=0.001, format="%.4f"),
                "Observacoes": st.column_config.TextColumn(width="large"),
            }
        )

        gen_pdf_b = st.checkbox("Tambem gerar PDF (1 browser reutilizado para todas)", value=False, key="batch_pdf")
        if st.button("Gerar relatorios em lote", type="primary", use_container_width=True, key="batch_run"):
            import io as _io, zipfile as _zip
            results = []
            htmls_geradas = []  # lista de (usina, html, filename)
            prog = st.progress(0.0, text="Etapa 1/2: gerando HTMLs...")
            n = len(edited)
            for i, row in edited.iterrows():
                nm = row["Usina"]; pid_b = _opts_b[nm]
                poa_b = float(row["POA (kWh/m2)"] or 0)
                tarifa_b = float(row["Tarifa (R$/kWh)"] or 0)
                obs_b = str(row["Observacoes"] or "")
                prog.progress((i)/max(n,1), text="HTML ("+str(i+1)+"/"+str(n)+") "+nm)
                try:
                    html_b, fn_b, status_b = gerar_relatorio_html(
                        pid_b, int(ano_b), int(mes_b), poa_b, tarifa_b, obs_b)
                    if html_b:
                        htmls_geradas.append((nm, html_b, fn_b))
                        results.append([nm, "OK", status_b, fn_b])
                    else:
                        results.append([nm, "ERRO", status_b, ""])
                except Exception as e:
                    results.append([nm, "ERRO", str(e), ""])
            prog.progress(0.5 if gen_pdf_b else 1.0, text="HTMLs prontos.")

            pdfs_map = {}
            if gen_pdf_b and htmls_geradas:
                def _cb(i, total, label):
                    prog.progress(0.5 + 0.5*((i)/max(total,1)),
                                  text="PDF ("+str(i+1)+"/"+str(total)+") "+label)
                pdfs_map = htmls_para_pdfs_batch(
                    [(nm, html_b) for nm, html_b, _ in htmls_geradas], progress_cb=_cb)
                prog.progress(1.0, text="Concluido")

            # Empacota ZIP
            zip_buf = _io.BytesIO()
            with _zip.ZipFile(zip_buf, "w", _zip.ZIP_DEFLATED) as zf:
                for idx, (nm, html_b, fn_b) in enumerate(htmls_geradas):
                    zf.writestr(fn_b, html_b.encode("utf-8"))
                    pdf_bytes = pdfs_map.get(idx)
                    if pdf_bytes:
                        zf.writestr(fn_b.replace(".html",".pdf"), pdf_bytes)
            zip_buf.seek(0)
            res_df = pd.DataFrame(results, columns=["Usina","Status","Detalhe","Arquivo"])
            st.dataframe(res_df, use_container_width=True, hide_index=True)
            n_ok = sum(1 for r in results if r[1]=="OK")
            zip_name = "relatorios_lote_"+str(ano_b)+"_"+str(mes_b).zfill(2)+".zip"
            st.success("Concluido: "+str(n_ok)+"/"+str(n)+" usinas processadas com sucesso.")
            st.download_button("Baixar ZIP com todos os relatorios",
                               data=zip_buf.getvalue(), file_name=zip_name,
                               mime="application/zip", use_container_width=True, type="primary",
                               key="batch_dl_zip")
    else:
        st.info("Selecione ao menos uma usina para preencher POA/Tarifa.")

st.divider()

with st.sidebar:
    if _auth_user:
        st.markdown(f"**{_auth_user.get('nome','')}**")
        st.caption(_auth_user.get("email",""))
        if st.button("Sair", use_container_width=True, key="btn_logout"):
            _auth_module.logout(st)
        st.divider()
    st.markdown("### Parametros")
    @st.cache_data(ttl=300)
    def load_listas():
        orgs  =sql("SELECT id,name FROM public.organization_organization WHERE id IN (SELECT DISTINCT organization_id FROM public.plant_plant WHERE is_active=TRUE AND is_parent=FALSE AND organization_id IS NOT NULL) ORDER BY name")
        plants=sql("SELECT id,name,organization_id FROM public.plant_plant WHERE is_active=TRUE AND is_parent=FALSE ORDER BY name")
        return orgs,plants
    orgs,plants=load_listas()
    clientes=["Todos"]+orgs["name"].tolist()
    cliente_sel=st.selectbox("Cliente",clientes)
    if cliente_sel=="Todos": plants_f=plants
    else:
        oid=orgs[orgs["name"]==cliente_sel]["id"].values[0]
        plants_f=plants[plants["organization_id"]==oid]
    opts={r["name"]:r["id"] for _,r in plants_f.iterrows()}
    if not opts: st.warning("Nenhuma usina encontrada."); st.stop()
    sel=st.selectbox("Usina",list(opts.keys()))
    pid=opts[sel]
    ano=st.selectbox("Ano",[2026,2025,2024])
    mes=st.selectbox("Mes",list(range(1,13)),format_func=lambda m:MESES[m],index=1)
    ps_id_isc=ISC_MAP.get(pid)
    if ps_id_isc:
        st.success("Energia: iSolarCloud (direto do inversor)")
    else:
        st.info("Energia: Banco AEVO")
    st.divider()
    st.markdown("### Irradiacao")
    st.caption("POA = Plano Inclinado (calculado pelo time a partir da estacao solarimetrica)")
    poa_manual=st.number_input("POA medido (kWh/m2)",min_value=0.0,value=0.0,step=0.1,format="%.2f",
                               help="Valor calculado pelo time via Python + dados da estacao. Se vazio, busca do banco ou estima via PVsyst.")
    st.divider()
    st.markdown("### PVsyst (manual)")
    st.caption("Preencha apenas se os dados PVsyst nao estiverem cadastrados no banco AEVO.")
    pv_egrid_manual=st.number_input("E_grid esperado (kWh)",min_value=0.0,value=0.0,step=100.0,format="%.0f")
    pv_pr_manual=st.number_input("PR esperado",min_value=0.0,value=0.0,step=0.001,format="%.4f")
    pv_globinc_manual=st.number_input("Glob Inc (kWh/m2)",min_value=0.0,value=0.0,step=1.0,format="%.2f")
    pv_p50_manual=st.number_input("P50 (kWh)",min_value=0.0,value=0.0,step=100.0,format="%.0f")
    pv_p75_manual=st.number_input("P75 (kWh)",min_value=0.0,value=0.0,step=100.0,format="%.0f")
    st.divider()
    st.markdown("### Outros")
    tarifa_input=st.number_input("Tarifa R$/kWh",min_value=0.0,value=0.0,step=0.001,format="%.4f")
    obs_input=st.text_area("Observacoes tecnicas",height=80)
    run=st.button("Carregar dados",use_container_width=True,type="primary")
    st.divider()
    if os.path.exists(_CACHE_DIR):
        _n_cache=len([f for f in os.listdir(_CACHE_DIR) if f.endswith(".pkl")])
        _sz_cache=sum(os.path.getsize(os.path.join(_CACHE_DIR,f)) for f in os.listdir(_CACHE_DIR) if f.endswith(".pkl"))
        st.caption("Cache: %d arquivos (%.1f MB)"%(_n_cache,_sz_cache/1024/1024))
        if st.button("Limpar cache",use_container_width=True):
            import shutil; shutil.rmtree(_CACHE_DIR,ignore_errors=True)
            st.success("Cache limpo!"); st.rerun()

# Inicializar session_state
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = None
if "html_cache" not in st.session_state:
    st.session_state.html_cache = None

if run:
    st.session_state.pdf_bytes = None  # Resetar PDF ao carregar novos dados
    st.session_state.html_cache = None
    ps_id_isc=ISC_MAP.get(pid)

    # ── Tentativa rapida: ler do Supabase (se nao ha overrides manuais) ──
    _from_sb = None
    _no_overrides = (poa_manual==0 and pv_egrid_manual==0 and pv_pr_manual==0
                     and pv_globinc_manual==0 and pv_p50_manual==0 and pv_p75_manual==0)
    if _no_overrides:
        with st.spinner("Verificando cache no Supabase..."):
            try: _from_sb = coletar_do_supabase(pid, ano, mes)
            except Exception: _from_sb = None

    if _from_sb:
        cad = _from_sb["cad"]; kwp = _from_sb["kwp"]
        pvsyst = _from_sb["pvsyst"]; df_al = _from_sb["df_al"]
        df_daily = _from_sb["df_daily"]; df_paradas = _from_sb["df_paradas"]
        df_disp_op = _from_sb["df_disp_op"]; df_poa_dia = _from_sb["df_poa_dia"]
        disp_op_media = _from_sb["disp_op_media"]; disp_dia_inv = _from_sb["disp_dia_inv"]
        kpis = _from_sb["kpis"]; kpis_5est = _from_sb["kpis_5est"]
        poa = _from_sb["poa"]; fonte_poa = _from_sb["fonte_poa"]
        fonte_energia = _from_sb["fonte_energia"]
        tem_estacao = _from_sb["tem_estacao"]
        token = None; ghost_pks = set()
        glob_inc = float(pvsyst.get("glob_inc") or 0)
        st.success("⚡ Lido do Supabase em segundos (cache ETL)")
        # Pular pipeline ISC — ir direto para calculo de alert_dias e charts

    if _from_sb is None:
        with st.spinner("Buscando dados cadastrais..."):
            df_cad =sql("SELECT name,nominal_power_kwp,om_contract,contract_end FROM public.plant_plant WHERE id="+str(pid))
            cad    =df_cad.iloc[0].to_dict() if not df_cad.empty else {}
            kwp    =float(cad.get("nominal_power_kwp") or 0)
            df_pv  =load_pvsyst(pid,ano,mes)
            pvsyst =df_pv.iloc[0].to_dict() if not df_pv.empty else {}
            if not pvsyst.get("e_grid") and pv_egrid_manual>0:
                pvsyst["e_grid"]=pv_egrid_manual
                st.caption("PVsyst E_grid: manual (%.0f kWh)" % pv_egrid_manual)
            if not pvsyst.get("pr") and pv_pr_manual>0: pvsyst["pr"]=pv_pr_manual
            if not pvsyst.get("glob_inc") and pv_globinc_manual>0: pvsyst["glob_inc"]=pv_globinc_manual
            if not pvsyst.get("p50") and pv_p50_manual>0: pvsyst["p50"]=pv_p50_manual
            if not pvsyst.get("p75") and pv_p75_manual>0: pvsyst["p75"]=pv_p75_manual
            if not pvsyst: st.warning("PVsyst nao encontrado. Preencha no sidebar.")
            df_al  =pd.DataFrame() if ps_id_isc else load_alertas(pid,ano,mes)

        # ── Energia (iSolarCloud ou banco) ──
        fonte_energia="Banco AEVO"; df_daily=pd.DataFrame(); ghost_pks=set()
        if ps_id_isc:
            with st.spinner("Conectando ao iSolarCloud..."):
                token=isc_login()
            if token:
                _c_en=_cache_load(ps_id_isc,ano,mes,"energia") if _mes_fechado(ano,mes) else None
                if _c_en:
                    df_daily,msg,ghost_pks=_c_en
                    st.caption("⚡ Energia: cache disco")
                else:
                    df_daily,msg,ghost_pks=isc_energia_mensal(ps_id_isc,ano,mes,token)
                    if not df_daily.empty and _mes_fechado(ano,mes):
                        _cache_save(ps_id_isc,ano,mes,"energia",(df_daily,msg,ghost_pks))
                if not df_daily.empty:
                    fonte_energia="iSolarCloud"
                    st.success("iSolarCloud: {:,.0f} kWh total".format(df_daily["energia_kwh"].sum()))
                else:
                    st.warning("iSolarCloud sem dados ("+msg+"). Usando banco AEVO.")
            else:
                st.warning("Falha no login iSolarCloud. Usando banco AEVO.")
        if df_daily.empty:
            with st.spinner("Buscando energia do banco..."):
                df_daily=load_inverter_daily_banco(pid,ano,mes)

        if df_daily.empty:
            st.error("Sem dados de geracao para o periodo."); st.stop()

        # ── POA — cascata de resolucao ──
        with st.spinner("Buscando POA e disponibilidade operacional..."):
            glob_inc=float(pvsyst.get("glob_inc") or 0)
            glob_hor=float(pvsyst.get("glob_hor") or 0)
            poa_banco,ghi_banco=load_poa_banco(pid,ano,mes)
            poa,fonte_poa=resolve_poa(poa_manual,poa_banco,glob_inc,glob_hor,ghi_banco)
            tem_estacao=len(get_ws_ids(pid))>0
            df_poa_dia=load_poa_diaria(pid,ano,mes) if tem_estacao else pd.DataFrame()
            kpis_5est=None; disp_dia_inv=None
            if ps_id_isc and token:
                _c_5e=_cache_load(ps_id_isc,ano,mes,"5estados") if _mes_fechado(ano,mes) else None
                if _c_5e:
                    df_disp_op,df_paradas,disp_op_media,kpis_5est,disp_dia_inv=_c_5e
                    st.caption("⚡ 5 estados: cache disco")
                else:
                    df_disp_op,df_paradas,disp_op_media,kpis_5est,disp_dia_inv=isc_5estados_mensal(ps_id_isc,ano,mes,token,excluir_pks=tuple(sorted(ghost_pks)) if ghost_pks else None)
                    if _mes_fechado(ano,mes):
                        _cache_save(ps_id_isc,ano,mes,"5estados",(df_disp_op,df_paradas,disp_op_media,kpis_5est,disp_dia_inv))
            else:
                df_disp_op,df_paradas,disp_op_media=load_disp_operacao(pid,ano,mes)

        dias_mes=calendar.monthrange(ano,mes)[1]
        kpis=calc_kpis(df_daily,dias_mes,kwp,poa,pvsyst,df_disp_op)
        glob_inc_dia=glob_inc/dias_mes if (glob_inc and dias_mes) else 0

    else:
        # Caminho Supabase: variaveis ja populadas, so calcular dias_mes e glob_inc_dia
        dias_mes=calendar.monthrange(ano,mes)[1]
        glob_inc_dia=glob_inc/dias_mes if (glob_inc and dias_mes) else 0

    # Compute alert_dias via inverter consistency
    alert_dias=[]
    df_dia_tmp=kpis.get("df_dia",pd.DataFrame())
    if not df_dia_tmp.empty and not df_daily.empty:
        _vals_a=sorted([float(v) for v in df_dia_tmp["energia_kwh"] if float(v)>0])
        if len(_vals_a)>=5:
            _med_a=_vals_a[len(_vals_a)//2]
            _inv_dia_a={}
            for _,_r_a in df_daily.iterrows():
                _dd_a=_r_a["dia"]; _di_a=int(_dd_a.strftime("%d")) if hasattr(_dd_a,"strftime") else int(str(_dd_a)[8:10])
                _in_a=str(_r_a["inversor"])
                if _di_a not in _inv_dia_a: _inv_dia_a[_di_a]={}
                _inv_dia_a[_di_a][_in_a]=_inv_dia_a[_di_a].get(_in_a,0)+float(_r_a["energia_kwh"])
            for _,_r_a in df_dia_tmp.iterrows():
                _v_a=float(_r_a["energia_kwh"]); _d_a=_r_a["dia"]
                _di=int(_d_a.strftime("%d")) if hasattr(_d_a,"strftime") else int(str(_d_a)[8:10])
                if _v_a>_med_a*2.5 and _v_a>20000: alert_dias.append(_di)
                if _v_a<_med_a*0.10:
                    _id_a=_inv_dia_a.get(_di,{})
                    if _id_a:
                        _iv=sorted(_id_a.values()); _mi=_iv[len(_iv)//2] if _iv else 0
                        _nb=sum(1 for ev in _iv if ev<_mi*0.20) if _mi>0 else len(_iv)
                        if _nb/max(len(_iv),1)<=0.70 and _nb<=2 and _mi>100: alert_dias.append(_di)

    # Use p26-based chart for Tier 1, energy-based for Tier 2
    if disp_dia_inv:
        ch_disp=chart_disp_5est(disp_dia_inv,dias_mes,ano,mes,df_daily)
    else:
        ch_disp=chart_disp(df_daily,dias_mes,ano,mes)

    charts={
        "inv":     chart_inv(kpis.get("df_inv",pd.DataFrame())),
        "desvios": chart_desvios(kpis,poa,pvsyst),
        "disp":    ch_disp,
        "ger_dia": chart_ger_dia_alert(kpis.get("df_dia",pd.DataFrame()),dias_mes,ano,mes,alert_dias) if alert_dias else chart_ger_dia(kpis.get("df_dia",pd.DataFrame()),dias_mes,ano,mes),
        "poa":     chart_poa_dia(df_poa_dia,glob_inc_dia,dias_mes,ano,mes),
    }

    er=kpis.get("energia_real",0); at=kpis.get("at",0)
    pr_real=kpis.get("pr_real",0); dg=kpis.get("disp_ger",0)
    receita=er*tarifa_input if tarifa_input else 0
    df_inv=kpis.get("df_inv",pd.DataFrame())
    var_poa=kpis.get("var_poa",0)

    badge="ð\x9f\x9f¢ iSolarCloud" if fonte_energia=="iSolarCloud" else "ð\x9f\x9f¡ Banco AEVO"
    st.success(str(cad.get("name",""))+" — "+MESES[mes]+"/"+str(ano)+" | Fonte: "+badge)

    # Info POA
    if poa>0:
        st.info("POA: %.2f kWh/m2 (%s) | Esperado PVsyst: %.2f kWh/m2 | Variacao: %+.1f%%" % (poa,fonte_poa,glob_inc,var_poa))
    else:
        st.warning("Sem POA disponivel — PR nao calculado. Informe o POA manualmente.")

    st.markdown("#### Indicadores de Desempenho")
    if kpis_5est and kpis_5est.get("tier")==1:
        c1,c2,c3,c4,c5,c6=st.columns(6)
        c1.metric("Energia Real "+badge,"{:,.0f} kWh".format(er),"%.1f%% do esperado"%at)
        c2.metric("PR Real",("%.4f"%pr_real if pr_real else "---"),("Esp: %.3f"%kpis.get("pr_e",0) if kpis.get("pr_e") else ""))
        c3.metric("POA Medido",("%.2f kWh/m2"%poa if poa else "---"),("%+.1f%% vs PVsyst"%var_poa if poa else None))
        c4.metric("Disp. Geracao","%.2f%%"%kpis_5est.get("pct_geracao",0))
        c5.metric("Perdas Concess.","%.2f%%"%kpis_5est.get("pct_conc",0))
        c6.metric("Perdas Eq/O&M","%.2f%%"%kpis_5est.get("pct_om",0))

    else:
        c1,c2,c3,c4,c5,c6=st.columns(6)
        c1.metric("Energia Real "+badge,"{:,.0f} kWh".format(er),"%.1f%% do esperado"%at)
        c2.metric("PR Real",("%.4f"%pr_real if pr_real else "---"),("Esp: %.3f"%kpis.get("pr_e",0) if kpis.get("pr_e") else ""))
        c3.metric("POA Medido",("%.2f kWh/m2"%poa if poa else "---"),("%+.1f%% vs PVsyst"%var_poa if poa else None))
        c4.metric("Disp. Operacao","%.2f%%"%disp_op_media if disp_op_media else "---")
        c5.metric("Cobertura Dados","%.1f%%"%dg)
        c6.metric("Receita Est.","R$ {:,.2f}".format(receita) if receita else "---")

    t1,t2,t3,t4=st.tabs(["Inversores","Paradas Detectadas","Alertas","Preview"])
    with t1:
        st.caption("Fonte: "+fonte_energia)
        cols_show=["inversor","energia_kwh","esp_kwh_kwp","pct","disp_ger_pct","disp_op_pct","horas_off"]
        if kpis_5est and kpis_5est.get("tier")==1:
            cols_show+=["pct_conc","pct_om"]
        cols_show=[c for c in cols_show if c in df_inv.columns]
        st.dataframe(df_inv[cols_show].rename(columns={
            "inversor":"Inversor","energia_kwh":"Energia (kWh)","esp_kwh_kwp":"Esp. kWh/kWp",
            "pct":"% Total","disp_ger_pct":"Cob. Dados %","disp_op_pct":"Disp. Op. %","horas_off":"Horas Off"}),
            use_container_width=True,hide_index=True)
    with t2:
        if df_paradas.empty: st.info("Nenhuma parada parcial detectada.")
        else: st.dataframe(df_paradas,use_container_width=True,hide_index=True)
    with t3:
        if df_al.empty: st.info("Nenhuma ocorrencia no banco.")
        else: st.dataframe(df_al,use_container_width=True,hide_index=True)
    with t4:
        html=gerar_html(cad,kpis,df_al,df_paradas,tarifa_input,obs_input,pvsyst,
                        ano,mes,charts,tem_estacao,poa,fonte_poa,disp_op_media,fonte_energia,kpis_5est,disp_dia_inv,df_daily)
        st.components.v1.html(html,height=700,scrolling=True)

    st.divider()
    # ── Seletor de tipo de relatorio (DESTACADO) ────────────────────────────
    st.markdown("### 📄 Gerar relatório")
    col_mode, col_info = st.columns([2, 1])
    with col_mode:
        modo_rel = st.radio(
            "**Escolha o formato do relatório:**",
            ["Detalhado (operacional)", "✨ Executivo (A4 retrato — modelo cliente)"],
            horizontal=False, key="modo_relatorio",
            help="Detalhado: layout operacional com todos os gráficos. "
                 "Executivo: layout A4 retrato no estilo do PDF modelo (capa + sumário + sobre AEVO + disclaimer + tabela comparativa + tabela diária + análise de ocorrências)."
        )
    with col_info:
        if modo_rel.startswith("✨"):
            st.success("✨ **Modo Executivo**\n\n9 páginas A4 retrato\nideal para impressão e envio ao cliente")
        else:
            st.info("📊 **Modo Detalhado**\n\nLayout operacional completo\nlandscape com gráficos")
    # Normaliza valor (remove emoji do prefixo p/ check)
    if "Executivo" in modo_rel: modo_rel = "Executivo (A4 retrato)"
    if modo_rel.startswith("Executivo"):
        # Reusa data ja calculado, chama o renderer executivo direto
        try:
            import _executivo as _exec_mod
            import json as _jsonmod_inline
            data_pkg = {
                "cad": cad, "kpis": kpis, "kpis_5est": kpis_5est,
                "df_daily": df_daily, "df_paradas": df_paradas, "df_al": df_al,
                "df_poa_dia": df_poa_dia, "pvsyst": pvsyst, "poa": poa,
                "fonte_poa": fonte_poa, "fonte_energia": fonte_energia,
                "disp_op_media": disp_op_media, "disp_dia_inv": disp_dia_inv,
            }
            css = _exec_mod.render_executivo_css()
            body = _exec_mod.render_executivo_html(data_pkg, ano, mes, logo_b64=LOGO_B64)
            # Drawer dinamico opcional
            try:
                _raw_dataset = _build_raw_dataset(
                    cad, kpis, kpis_5est, df_daily, df_paradas, pvsyst,
                    tarifa_input, poa, fonte_poa, fonte_energia, ano, mes, disp_dia_inv)
                _raw_json = _jsonmod_inline.dumps(_raw_dataset, ensure_ascii=False)
                _vocab_json = _jsonmod_inline.dumps(_VOCAB_DEFAULT, ensure_ascii=False)
                from _dinamico import (render_dinamico_css, render_dinamico_drawer_html,
                                          render_dinamico_js)
                drawer_block = (
                    '<style>' + render_dinamico_css() + '</style>' +
                    render_dinamico_drawer_html() +
                    '<script id="__raw_data__" type="application/json">' + _raw_json + '</script>'
                    '<script id="__vocab_default__" type="application/json">' + _vocab_json + '</script>'
                    '<script>'
                    'window.__RAW_DATA = JSON.parse(document.getElementById("__raw_data__").textContent);'
                    'window.__VOCAB_DEFAULT = JSON.parse(document.getElementById("__vocab_default__").textContent);'
                    'window.__STATE = {'
                    '  tarifa_rs_kwh: window.__RAW_DATA.estado_inicial.tarifa_rs_kwh,'
                    '  poa_kwh_m2: window.__RAW_DATA.estado_inicial.poa_kwh_m2,'
                    '  inversores_excluidos: [],'
                    '  paradas_editadas: {},'
                    '  vocab: JSON.parse(JSON.stringify(window.__VOCAB_DEFAULT)),'
                    '  usina_overrides: {}'
                    '};'
                    '</script>'
                    '<script>' + render_dinamico_js() + '</script>'
                )
            except Exception as _e_dyn:
                print("[executivo] drawer falhou:", _e_dyn); drawer_block = ""
            head_exec = (
                '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                f'<title>Relatorio Mensal — {cad.get("name", "UFV")} — {mes:02d}/{ano}</title>'
                '<link rel="preconnect" href="https://fonts.googleapis.com">'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
                '<style>' + css + '</style></head>'
            )
            html = head_exec + body + drawer_block + '</html>'
            filename = "relatorio_exec_" + str(cad.get("acronym") or cad.get("name","UFV")).replace(" ","_")[:15] + "_" + str(ano) + "_" + str(mes).zfill(2) + ".html"
        except Exception as e_exec:
            st.error(f"Falha ao gerar relatorio executivo: {e_exec}")
            html = gerar_html(cad, kpis, df_al, df_paradas, tarifa_input, obs_input, pvsyst,
                              ano, mes, charts, tem_estacao, poa, fonte_poa, disp_op_media,
                              fonte_energia, kpis_5est, disp_dia_inv, df_daily)
            filename = "relatorio_" + str(cad.get("acronym") or cad.get("name","UFV")).replace(" ","_")[:15] + "_" + str(ano) + "_" + str(mes).zfill(2) + ".html"
    else:
        html = gerar_html(cad, kpis, df_al, df_paradas, tarifa_input, obs_input, pvsyst,
                          ano, mes, charts, tem_estacao, poa, fonte_poa, disp_op_media,
                          fonte_energia, kpis_5est, disp_dia_inv, df_daily)
        filename = "relatorio_" + str(cad.get("acronym") or cad.get("name","UFV")).replace(" ","_")[:15] + "_" + str(ano) + "_" + str(mes).zfill(2) + ".html"

    st.session_state.html_cache = html
    st.session_state.pdf_filename = filename
    col_html,col_pdf=st.columns(2)
    with col_html:
        st.download_button("⬇️ Baixar HTML",data=html.encode("utf-8"),
                           file_name=filename,mime="text/html",use_container_width=True)
    with col_pdf:
        if st.button("📋 Gerar PDF",use_container_width=True,type="primary"):
            with st.spinner("Gerando PDF via Playwright... ~5s"):
                st.session_state.pdf_bytes=html_para_pdf(html)
                st.session_state.pdf_filename=filename.replace(".html",".pdf")
else:
    st.info("Selecione cliente, usina, ano e mes e clique em Carregar dados.")

# Bloco de download PDF — fora do if run para persistir entre reruns
if st.session_state.get("pdf_bytes"):
    st.divider()
    st.download_button(
        "⬇️ Baixar PDF gerado",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_filename or "relatorio.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
        key="dl_pdf_persistente"
    )
    st.success("PDF pronto! Clique acima para baixar.")
    if st.button("ð\x9f\x97\x91ï¸\x8f Limpar PDF", key="clear_pdf"):
        st.session_state.pdf_bytes = None
        st.rerun()

# Bloco de download HTML — disponivel tambem quando html_cache existe e run nao foi clicado
if st.session_state.get("html_cache") and not run:
    col1,col2=st.columns(2)
    with col1:
        st.download_button("⬇️ Baixar HTML novamente",
            data=st.session_state.html_cache.encode("utf-8"),
            file_name=st.session_state.pdf_filename.replace(".pdf",".html") if st.session_state.pdf_filename else "relatorio.html",
            mime="text/html",use_container_width=True,key="dl_html_cache")
    with col2:
        if st.button("📋 Gerar PDF",use_container_width=True,type="primary",key="gerar_pdf_cache"):
            with st.spinner("Gerando PDF... ~5s"):
                st.session_state.pdf_bytes=html_para_pdf(st.session_state.html_cache)
            st.rerun()
