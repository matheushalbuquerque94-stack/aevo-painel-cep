"""Painel de Portfolio AEVO19 — leitura direta do Supabase."""
import os, sys, calendar
from datetime import datetime
import streamlit as st
import pandas as pd
import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Auth — mesma do app principal
try:
    import auth as _auth
    _user = _auth.ensure_login(st)
except ImportError:
    _user = None

st.set_page_config(page_title="Painel Portfolio — AEVO19", page_icon="📊", layout="wide")


# ── Conexao Supabase ─────────────────────────────────────────────────────
@st.cache_resource
def _sb_conn():
    """Conexao reutilizada com Supabase (pooler)."""
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1); env[k.strip()] = v.strip()
    for k in ("SUPABASE_HOST","SUPABASE_PASSWORD","SUPABASE_REGION","SUPABASE_DB"):
        if k not in env and os.environ.get(k): env[k] = os.environ[k]
    if "SUPABASE_HOST" not in env:
        st.error("SUPABASE_HOST nao definido."); st.stop()
    ref = env["SUPABASE_HOST"].split(".")[1]
    region = env.get("SUPABASE_REGION", "us-east-1")
    return psycopg2.connect(
        host=f"aws-1-{region}.pooler.supabase.com", port=5432,
        dbname=env.get("SUPABASE_DB","postgres"),
        user=f"postgres.{ref}", password=env["SUPABASE_PASSWORD"],
        sslmode="require", connect_timeout=15
    )

@st.cache_resource
def _aevo_conn():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1); env[k.strip()] = v.strip()
    for k in ("AEVO_HOST","AEVO_PORT","AEVO_DB","AEVO_USER","AEVO_PASSWORD"):
        if k not in env and os.environ.get(k): env[k] = os.environ[k]
    if "AEVO_HOST" not in env:
        st.error("AEVO_HOST nao definido."); st.stop()
    return psycopg2.connect(
        host=env["AEVO_HOST"], port=int(env.get("AEVO_PORT", "18796")),
        dbname=env.get("AEVO_DB","railway"),
        user=env["AEVO_USER"], password=env["AEVO_PASSWORD"]
    )


@st.cache_data(ttl=300)
def carregar_kpis_portfolio(ano, mes):
    """KPIs mensais do Supabase + nome/lat/long/kwp do AEVO."""
    sb = _sb_conn()
    aevo = _aevo_conn()
    df_k = pd.read_sql(f"""
        SELECT plant_id, energia_real_kwh, energia_esperada_kwh, atingimento_pct,
               pr_real, pr_esperado, poa_kwh_m2, disp_geracao_pct, disp_operacao_pct,
               tier, pct_irr, pct_conc, pct_om,
               total_eventos, total_horas_off, em_aberto, is_closed, fetched_at
        FROM reports.kpis_mensal
        WHERE ano={ano} AND mes={mes}
    """, sb)
    if df_k.empty:
        return pd.DataFrame()
    ids = ",".join(str(int(x)) for x in df_k["plant_id"].unique())
    df_p = pd.read_sql(f"""
        SELECT id AS plant_id, name, nominal_power_kwp,
               latitude, longitude, organization_id, operation_start_year
        FROM public.plant_plant WHERE id IN ({ids})
    """, aevo)
    df_o = pd.read_sql(f"""
        SELECT id AS organization_id, name AS cliente
        FROM public.organization_organization
    """, aevo)
    df = df_k.merge(df_p, on="plant_id", how="left").merge(df_o, on="organization_id", how="left")
    df["energia_real_kwh"] = df["energia_real_kwh"].astype(float)
    df["atingimento_pct"] = df["atingimento_pct"].astype(float)
    df["disp_geracao_pct"] = df["disp_geracao_pct"].astype(float)
    df["pr_real"] = df["pr_real"].astype(float)
    df["nominal_power_kwp"] = df["nominal_power_kwp"].astype(float)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def carregar_serie_historica(plant_ids, meses_back=12):
    """Series mensais dos ultimos N meses para as plantas selecionadas."""
    sb = _sb_conn()
    ids_str = ",".join(str(int(x)) for x in plant_ids)
    df = pd.read_sql(f"""
        SELECT plant_id, ano, mes, energia_real_kwh, atingimento_pct,
               pr_real, disp_geracao_pct, total_eventos, total_horas_off
        FROM reports.kpis_mensal
        WHERE plant_id IN ({ids_str})
        ORDER BY ano DESC, mes DESC
    """, sb)
    if df.empty: return df
    df["periodo"] = df["ano"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
    return df.sort_values(["plant_id","ano","mes"])


@st.cache_data(ttl=300)
def meses_disponiveis():
    """Quais (ano, mes) tem dados no Supabase."""
    sb = _sb_conn()
    df = pd.read_sql("""
        SELECT DISTINCT ano, mes FROM reports.kpis_mensal
        ORDER BY ano DESC, mes DESC
    """, sb)
    return df


# ──────────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────────
st.title("📊 Painel de Portfolio — AEVO19")
st.caption("Visao agregada de todas as usinas com dados no Supabase. Atualizado pelo ETL diario (~02:00 BRT).")

# Filtro mes/ano
df_meses = meses_disponiveis()
if df_meses.empty:
    st.warning("Sem dados no Supabase ainda. Rode o ETL para popular.")
    st.stop()

col_filt1, col_filt2, col_filt3 = st.columns([1,1,3])
with col_filt1:
    anos = sorted(df_meses["ano"].unique(), reverse=True)
    ano_sel = st.selectbox("Ano", anos, index=0)
with col_filt2:
    meses_do_ano = sorted(df_meses[df_meses["ano"]==ano_sel]["mes"].unique(), reverse=True)
    mes_sel = st.selectbox("Mes", meses_do_ano,
                            format_func=lambda m: ["","Jan","Fev","Mar","Abr","Mai","Jun",
                                                   "Jul","Ago","Set","Out","Nov","Dez"][m],
                            index=0)

df = carregar_kpis_portfolio(int(ano_sel), int(mes_sel))
if df.empty:
    st.warning(f"Sem dados para {mes_sel}/{ano_sel}.")
    st.stop()

with col_filt3:
    clientes = ["Todos"] + sorted([c for c in df["cliente"].dropna().unique()])
    cliente_sel = st.selectbox("Cliente", clientes)
if cliente_sel != "Todos":
    df = df[df["cliente"] == cliente_sel]

st.divider()

# ── KPIs do portfolio ─────────────────────────────────────────────────────
total_usinas = len(df)
total_energia_mwh = df["energia_real_kwh"].sum() / 1000
total_kwp = df["nominal_power_kwp"].sum()
at_medio = df["atingimento_pct"].mean()
disp_medio = df["disp_geracao_pct"].mean()
pr_medio = df[df["pr_real"]>0]["pr_real"].mean() if (df["pr_real"]>0).any() else 0
problemas = df[(df["atingimento_pct"]<90) | (df["disp_geracao_pct"]<95)]

st.markdown("### Visao Geral")
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Usinas no painel", total_usinas)
c2.metric("Potencia DC total", f"{total_kwp/1000:.1f} MWp")
c3.metric("Energia gerada", f"{total_energia_mwh:,.0f} MWh".replace(",","."))
c4.metric("Atingimento medio", f"{at_medio:.1f}%",
          f"{at_medio-100:+.1f}pp" if at_medio else None)
c5.metric("Disp. Geracao", f"{disp_medio:.2f}%")
c6.metric("Usinas em alerta", len(problemas),
          f"{len(problemas)/max(total_usinas,1)*100:.0f}% do portfolio" if total_usinas else None)

st.divider()

# ── Mapa + ranking lado a lado ────────────────────────────────────────────
col_map, col_rank = st.columns([2,1])

with col_map:
    st.markdown("### Mapa de Usinas")
    df_map = df.dropna(subset=["latitude","longitude"]).copy()
    if df_map.empty:
        st.info("Nenhuma usina tem latitude/longitude cadastrada.")
    else:
        # Cor por atingimento: verde >=95%, amarelo 85-95%, vermelho <85%
        def _color(at):
            if at >= 95: return [44,166,111,200]
            if at >= 85: return [242,177,52,200]
            return [228,92,84,220]
        df_map["color"] = df_map["atingimento_pct"].apply(_color)
        df_map["size"] = (df_map["nominal_power_kwp"].fillna(1000) / 30).clip(lower=8, upper=80)

        import pydeck as pdk
        view_state = pdk.ViewState(
            latitude=float(df_map["latitude"].mean()),
            longitude=float(df_map["longitude"].mean()),
            zoom=3.5,
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_map,
            get_position=["longitude","latitude"],
            get_color="color",
            get_radius="size",
            radius_units="pixels",
            pickable=True,
        )
        tooltip = {"html": "<b>{name}</b><br/>Atingimento: {atingimento_pct}%<br/>"
                            "Disp: {disp_geracao_pct}%<br/>{nominal_power_kwp} kWp"}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state,
                                  tooltip=tooltip, map_style="light"))

with col_rank:
    st.markdown("### Top 10 — Energia gerada")
    top_en = df.sort_values("energia_real_kwh", ascending=False).head(10)[
        ["name","energia_real_kwh","atingimento_pct"]
    ].rename(columns={"name":"Usina","energia_real_kwh":"kWh","atingimento_pct":"AT %"})
    top_en["kWh"] = top_en["kWh"].astype(int)
    st.dataframe(top_en, hide_index=True, use_container_width=True)

st.divider()

# ── Atingimento vs Esperado (bar chart) ──────────────────────────────────
st.markdown("### Atingimento por usina")
df_sorted = df.sort_values("atingimento_pct", ascending=True)
df_sorted["color"] = df_sorted["atingimento_pct"].apply(
    lambda at: "Bom (>=95%)" if at>=95 else "Atencao (85-95%)" if at>=85 else "Alerta (<85%)"
)
import plotly.express as px
fig = px.bar(df_sorted, x="atingimento_pct", y="name",
             color="color", orientation="h",
             color_discrete_map={"Bom (>=95%)":"#2CA66F",
                                  "Atencao (85-95%)":"#F2B134",
                                  "Alerta (<85%)":"#E45C54"},
             labels={"atingimento_pct":"Atingimento (%)","name":""},
             height=max(400, 22*len(df_sorted)))
fig.add_vline(x=100, line_dash="dash", line_color="#0E2841", line_width=1)
fig.update_layout(legend_title="", margin=dict(l=0,r=0,t=20,b=0))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Disponibilidade x PR (scatter) ────────────────────────────────────────
col_scatter, col_problemas = st.columns([2,1])
with col_scatter:
    st.markdown("### Disponibilidade × Atingimento")
    df_s = df.copy()
    fig2 = px.scatter(df_s, x="disp_geracao_pct", y="atingimento_pct",
                      size="nominal_power_kwp", color="cliente",
                      hover_name="name",
                      labels={"disp_geracao_pct":"Disp. Geracao (%)",
                              "atingimento_pct":"Atingimento (%)"},
                      height=420)
    fig2.add_hline(y=100, line_dash="dash", line_color="#0E2841", line_width=1)
    fig2.add_hline(y=85, line_dash="dot", line_color="#E45C54", line_width=1)
    fig2.add_vline(x=95, line_dash="dot", line_color="#E45C54", line_width=1)
    fig2.update_layout(margin=dict(l=0,r=0,t=20,b=0))
    st.plotly_chart(fig2, use_container_width=True)

with col_problemas:
    st.markdown("### Atencao Operacional")
    df_p = df.sort_values("disp_geracao_pct").head(5)[
        ["name","disp_geracao_pct","total_horas_off","total_eventos"]
    ].rename(columns={"name":"Usina","disp_geracao_pct":"Disp%",
                       "total_horas_off":"Horas OFF","total_eventos":"Eventos"})
    df_p["Disp%"] = df_p["Disp%"].round(2)
    df_p["Horas OFF"] = df_p["Horas OFF"].astype(float).round(1)
    st.dataframe(df_p, hide_index=True, use_container_width=True)
    st.caption("5 usinas com menor disponibilidade")

st.divider()

# ── Serie historica ───────────────────────────────────────────────────────
st.markdown("### Serie Historica — 12 meses")
serie = carregar_serie_historica(df["plant_id"].tolist(), 12)
if not serie.empty:
    # Tipo de metrica selecionavel
    metricas = {
        "Energia (MWh)": ("energia_real_kwh", lambda v: v/1000),
        "Atingimento (%)": ("atingimento_pct", lambda v: v),
        "Disp. Geracao (%)": ("disp_geracao_pct", lambda v: v),
        "PR Real": ("pr_real", lambda v: v),
        "Horas OFF": ("total_horas_off", lambda v: v),
    }
    col_m, col_agg = st.columns([2,1])
    with col_m: metric_sel = st.selectbox("Metrica", list(metricas.keys()), key="metric")
    with col_agg: agg = st.selectbox("Visao", ["Por usina","Media do portfolio","Soma"], key="agg")
    col, fn = metricas[metric_sel]
    serie_p = serie.copy()
    serie_p["val"] = serie_p[col].astype(float).apply(fn)
    serie_p = serie_p.merge(df[["plant_id","name","cliente"]], on="plant_id", how="left")

    if agg == "Por usina":
        # mostra todas
        fig3 = px.line(serie_p, x="periodo", y="val", color="name",
                       labels={"val":metric_sel,"periodo":""}, height=460)
        fig3.update_layout(showlegend=(len(df)<=20), margin=dict(l=0,r=0,t=20,b=0))
    elif agg == "Media do portfolio":
        gp = serie_p.groupby("periodo")["val"].mean().reset_index()
        fig3 = px.line(gp, x="periodo", y="val",
                       labels={"val":metric_sel+" (media)","periodo":""}, height=420)
        fig3.update_traces(line=dict(color="#0F9ED5", width=3))
        fig3.update_layout(margin=dict(l=0,r=0,t=20,b=0))
    else:  # Soma
        gp = serie_p.groupby("periodo")["val"].sum().reset_index()
        fig3 = px.bar(gp, x="periodo", y="val",
                      labels={"val":metric_sel+" (soma)","periodo":""}, height=420)
        fig3.update_traces(marker_color="#0F9ED5")
        fig3.update_layout(margin=dict(l=0,r=0,t=20,b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Sem historico para os filtros atuais. Rode o ETL para meses anteriores.")

st.divider()

# ── Tabela detalhada ─────────────────────────────────────────────────────
with st.expander("Tabela completa do portfolio"):
    cols_show = ["name","cliente","nominal_power_kwp","energia_real_kwh","atingimento_pct",
                 "pr_real","disp_geracao_pct","total_eventos","total_horas_off","tier","is_closed"]
    df_tab = df[cols_show].rename(columns={
        "name":"Usina","cliente":"Cliente","nominal_power_kwp":"kWp",
        "energia_real_kwh":"Energia kWh","atingimento_pct":"AT %",
        "pr_real":"PR","disp_geracao_pct":"Disp%",
        "total_eventos":"Eventos","total_horas_off":"H OFF",
        "tier":"Tier","is_closed":"Fechado",
    }).sort_values("Energia kWh", ascending=False)
    st.dataframe(df_tab, hide_index=True, use_container_width=True, height=400)
    st.download_button("Baixar CSV",
                       data=df_tab.to_csv(index=False).encode("utf-8"),
                       file_name=f"portfolio_{ano_sel}_{mes_sel:02d}.csv",
                       mime="text/csv")

st.caption(f"Dados de {len(df)} usinas | atualizado em {df['fetched_at'].max()}")
