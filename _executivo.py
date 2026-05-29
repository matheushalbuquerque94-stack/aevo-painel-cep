"""Template de Relatorio Mensal de Performance — formato executivo A4 retrato.

Baseado no modelo PDF do cliente (LaTeX-style limpo).
Estrutura:
  1. Capa
  2. Sumario (TOC)
  3. Sobre a AEVO Solar
  4. Informacoes Importantes + Disclaimer
  5. Resumo (1 linha portfolio = 1 usina)
  6. Detalhe usina — Resumo + Ocorrencias
  7. Detalhe usina — Tabela diaria comparativa
  8. (Tier 1) Analise de disponibilidade — KPIs ocorrencias
  9. (Tier 1) Tabela de ocorrencias

Mantem TODOS os data-attributes do sistema dinamico (data-kpi, data-tbl, data-fmt)
para que o drawer continue funcionando — apenas troca o layout/CSS.
"""
import calendar
from datetime import datetime

MESES_PT = ["", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _fmt_n(v, dec=0):
    """Formata numero estilo BR: 1.234.567,89"""
    try: v = float(v)
    except: return "0"
    if v == 0: return "0,00" if dec > 0 else "0"
    s = f"{abs(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" + s) if v < 0 else s


def _fmt_p(v, dec=2):
    """Formata percentual: 72,36"""
    try: return _fmt_n(float(v), dec)
    except: return "0,00"


def _fmt_signed_pct(v, dec=2):
    """Formata variacao percentual com sinal: -12,90%"""
    try:
        v = float(v)
        s = _fmt_n(v, dec)
        if v > 0 and not s.startswith("+"): s = "+" + s
        return s + "%"
    except: return "0,00%"


def render_executivo_css():
    """CSS para layout A4 retrato — print-ready."""
    return """
    @page { size: A4 portrait; margin: 0; }
    @media print {
      body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .pag-exec { page-break-after: always; }
      .pag-exec:last-child { page-break-after: auto; }
    }
    body.exec {
      margin: 0; padding: 0; background: #E5E7EB;
      font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
      color: #1F2937;
    }
    .pag-exec {
      width: 210mm; height: 297mm;
      padding: 18mm 20mm 22mm 20mm;
      margin: 0 auto 10mm auto;
      background: white;
      box-sizing: border-box;
      position: relative;
      overflow: hidden;
      page-break-after: always;
    }
    /* ── Header (logo AEVO esquerda + logo cliente direita) ── */
    .ex-hdr {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 14mm; padding-bottom: 4mm;
    }
    .ex-hdr .ex-logo-aevo { height: 12mm; }
    .ex-hdr .ex-logo-cli { height: 12mm; opacity: 0.85; }
    .ex-hdr .ex-logo-cli-text {
      font-size: 13pt; font-weight: 700; color: #2A4365;
      letter-spacing: -.01em;
    }
    /* ── Footer (numero pagina centralizado) ── */
    .ex-ftr {
      position: absolute; bottom: 10mm; left: 20mm; right: 20mm;
      text-align: center; font-size: 9pt; color: #6B7280;
      border-top: .5pt solid #D1D5DB; padding-top: 3mm;
    }
    .ex-ftr-num { font-weight: 600; color: #1F2937; }

    /* ── Tipografia ── */
    .ex-h1 {
      font-size: 22pt; font-weight: 700; color: #111827;
      margin: 0 0 6mm 0; letter-spacing: -.02em;
    }
    .ex-h2 {
      font-size: 15pt; font-weight: 600; color: #1F2937;
      margin: 8mm 0 4mm 0; letter-spacing: -.01em;
    }
    .ex-h3 {
      font-size: 11pt; font-weight: 600; color: #374151;
      margin: 6mm 0 3mm 0;
    }
    .ex-body {
      font-size: 10.5pt; line-height: 1.55; color: #374151;
      text-align: justify; margin-bottom: 4mm;
    }
    .ex-body p { margin: 0 0 3mm 0; }
    .ex-list {
      font-size: 10pt; line-height: 1.55; color: #374151;
      margin: 3mm 0 3mm 6mm; padding-left: 5mm;
    }
    .ex-list li { margin-bottom: 2mm; }

    /* ── Tabela padrao executiva (header azul escuro + zebra) ── */
    .ex-tbl {
      width: 100%; border-collapse: collapse; font-size: 9pt;
      margin: 4mm 0; font-variant-numeric: tabular-nums;
    }
    .ex-tbl thead th {
      background: #0E2841; color: #F1F5F9; font-weight: 600;
      padding: 6px 8px; text-align: left; font-size: 9pt;
      border-bottom: 1pt solid #1E3A5F;
    }
    .ex-tbl thead th.num { text-align: right; }
    .ex-tbl tbody td {
      padding: 5px 8px; border-bottom: .25pt solid #CBD5E1;
      color: #1E3A5F; font-weight: 500;
    }
    .ex-tbl tbody td.num { text-align: right; font-feature-settings: "tnum"; }
    .ex-tbl tbody tr:nth-child(odd)  td { background: #DBE5F1; }
    .ex-tbl tbody tr:nth-child(even) td { background: #C6D5E8; }
    .ex-tbl tbody tr.total td {
      background: #0E2841 !important; color: white !important;
      font-weight: 700; border-top: 1pt solid #1E3A5F;
    }
    .ex-tbl-cap {
      text-align: center; font-size: 9pt; color: #6B7280;
      margin: 2mm 0 6mm 0; font-style: italic;
    }
    .ex-tbl-cap b { color: #1F2937; font-weight: 600; font-style: normal; }

    /* ── Variantes especiais ── */
    .ex-tbl-comp tbody tr.desvio-row td {
      background: #1E3A5F !important; color: white !important;
      font-weight: 600;
    }
    .ex-tbl-comp td.cat {
      font-weight: 600; color: #0E2841;
    }

    /* ── Capa ── */
    .ex-capa {
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      height: 100%; text-align: center;
    }
    .ex-capa .ex-capa-logo { height: 35mm; margin-bottom: 10mm; }
    .ex-capa .ex-capa-titulo {
      font-size: 26pt; font-weight: 600; color: #111827;
      margin: 4mm 0; letter-spacing: -.02em;
    }
    .ex-capa .ex-capa-cliente {
      font-size: 16pt; color: #4B5563; margin: 2mm 0;
    }
    .ex-capa .ex-capa-periodo {
      font-size: 14pt; color: #6B7280; margin: 2mm 0;
    }

    /* ── Sumario ── */
    .ex-toc { margin-top: 6mm; }
    .ex-toc-item {
      display: flex; justify-content: space-between;
      align-items: baseline; padding: 3mm 0;
      font-size: 10.5pt; color: #374151;
      border-bottom: .25pt dotted #9CA3AF;
    }
    .ex-toc-item.sub { font-size: 9.5pt; color: #6B7280; padding-left: 8mm; }
    .ex-toc-item .num { font-weight: 700; color: #0E2841; min-width: 8mm; }
    .ex-toc-item .titulo { flex: 1; }
    .ex-toc-item .pg { font-weight: 600; color: #0E2841; }

    /* ── Observacoes/callout ── */
    .ex-obs {
      background: #F8FAFC; border-left: 3pt solid #0E2841;
      padding: 4mm 5mm; margin: 4mm 0;
      font-size: 10pt; color: #374151;
    }
    .ex-obs b { color: #0E2841; }

    /* ── KPI grid para pagina Tier 1 ── */
    .ex-kpi-grid {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 4mm; margin: 4mm 0;
    }
    .ex-kpi-card {
      background: white; border: .5pt solid #CBD5E1;
      border-top: 2.5pt solid #0E2841;
      padding: 4mm; text-align: center;
    }
    .ex-kpi-card.green { border-top-color: #059669; }
    .ex-kpi-card.blue  { border-top-color: #0369A1; }
    .ex-kpi-card.red   { border-top-color: #DC2626; }
    .ex-kpi-card.orange{ border-top-color: #EA580C; }
    .ex-kpi-card .lbl {
      font-size: 8pt; color: #6B7280; text-transform: uppercase;
      letter-spacing: .04em; margin-bottom: 2mm;
    }
    .ex-kpi-card .val {
      font-size: 16pt; font-weight: 700; color: #0E2841;
      font-feature-settings: "tnum";
    }
    .ex-kpi-card.green .val { color: #059669; }
    .ex-kpi-card.blue  .val { color: #0369A1; }
    .ex-kpi-card.red   .val { color: #DC2626; }
    .ex-kpi-card.orange .val { color: #EA580C; }
    """


# ── PAGINA 1: CAPA ────────────────────────────────────────────────────────
def render_capa(cliente_nome, ano, mes, logo_b64=""):
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-capa-logo">' if logo_b64 else ""
    mes_nome = MESES_PT[mes] if 1 <= mes <= 12 else f"M{mes:02d}"
    return f"""
    <div class="pag-exec">
      <div class="ex-capa">
        {logo_html}
        <div class="ex-capa-titulo">Relatório Mensal de Performance</div>
        <div class="ex-capa-cliente" contenteditable="true">{cliente_nome}</div>
        <div class="ex-capa-periodo">{mes_nome} de {ano}</div>
      </div>
    </div>
    """


# ── PAGINA 2: SUMARIO ─────────────────────────────────────────────────────
def render_sumario(cliente_nome, logo_b64=""):
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h1">Sumário</div>
      <div class="ex-toc">
        <div class="ex-toc-item"><span class="num">1</span><span class="titulo">Sobre a AEVO Solar</span><span class="pg">3</span></div>
        <div class="ex-toc-item sub"><span class="num">1.1</span><span class="titulo">Informações Importantes</span><span class="pg">4</span></div>
        <div class="ex-toc-item sub"><span class="num">1.1.1</span><span class="titulo">Disclaimer</span><span class="pg">4</span></div>
        <div class="ex-toc-item"><span class="num">2</span><span class="titulo">Resumo</span><span class="pg">5</span></div>
        <div class="ex-toc-item"><span class="num">3</span><span class="titulo">{cliente_nome}</span><span class="pg">6</span></div>
        <div class="ex-toc-item sub"><span class="num">3.1</span><span class="titulo">Comparativo geral</span><span class="pg">6</span></div>
        <div class="ex-toc-item sub"><span class="num">3.2</span><span class="titulo">Geração diária</span><span class="pg">7</span></div>
        <div class="ex-toc-item sub"><span class="num">3.3</span><span class="titulo">Análise de ocorrências</span><span class="pg">8</span></div>
      </div>
      <div class="ex-ftr"><span class="ex-ftr-num">2</span></div>
    </div>
    """


# ── PAGINAS 3-4: SOBRE AEVO + DISCLAIMER ─────────────────────────────────
def render_sobre_aevo(cliente_nome, logo_b64=""):
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h2">1 &nbsp; Sobre a AEVO Solar</div>
      <div class="ex-body">
        <p>Nossa empresa e coligados oferecem soluções turn-key para serviços associados
        a projetos de geração de energia solar fotovoltaica e térmica. Prestamos consultoria
        e coordenamos as seguintes etapas de implantação dos projetos: estudos preliminares,
        análise de viabilidade, captação, aporte de recursos, seleção de fornecedores,
        elaboração de projeto básico e executivo, instalação, comissionamento, monitoramento
        e manutenção.</p>

        <p>A semente nasceu há vinte anos atrás e estamos aqui evoluindo e nos adaptando
        para inspirar e aplicar tecnologias solares exponenciais para enfrentar alguns dos
        grandes desafios da humanidade — da energia, água, comida e abrigo ao meio ambiente,
        saúde e educação, entre outros — a economia solar é um dos pilares para avançarmos
        com prosperidade em seu conceito distribuído, descentralizado e descarbonizado.</p>

        <p>E em nossa AEVOlução nos próximos dez anos, aumentaremos nossas capacidades,
        alcance e impacto através de nosso ecossistema de parceiros em expansão, tomando
        o pensamento exponencial e insights sobre o futuro da energia solar compartilhável
        e democrático, acessíveis a qualquer pessoa, em qualquer lugar e catalisando
        conexões para garantir que um futuro melhor se torne realidade.</p>

        <p>Nossa empresa foi premiada em 2024 com o <b>Selo PV nas modalidades O&amp;M e
        EPC</b> para o mercado brasileiro. Esta honraria foi concedida pela EuPD Research,
        um instituto alemão independente de pesquisa de mercado, que avalia o reconhecimento
        das marcas de empresas de energia solar e sua penetração no mercado.</p>
      </div>
      <div class="ex-ftr"><span class="ex-ftr-num">3</span></div>
    </div>
    """


def render_disclaimer(cliente_nome, logo_b64=""):
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h2">1.1 &nbsp; Informações Importantes</div>
      <div class="ex-body">
        <p>As informações contidas neste documento são de uso exclusivo do cliente para os
        propósitos para os quais foi preparado. A AEVO Solar não assume nem aceita nenhuma
        responsabilidade de quaisquer terceiros que venham a ter contato e possam se basear
        neste documento.</p>

        <p>Todos os direitos reservados. Nenhum item ou elemento do presente documento
        poderá ser eliminado, reproduzido, eletronicamente armazenado ou transmitido de
        nenhuma forma sem a permissão por escrito da AEVO Solar.</p>
      </div>

      <div class="ex-h3">1.1.1 &nbsp; Disclaimer</div>
      <div class="ex-body">
        <p>O presente documento foi elaborado com o propósito exclusivo de fornecer
        informações técnicas específicas e não deve, em hipótese alguma, ser considerado
        ou utilizado como laudo pericial ou parecer jurídico. As informações nele contidas
        são estritamente indicativas e se destinam ao contexto para o qual foram emitidas,
        não sendo apropriadas para fundamentar litígios, processos judiciais ou
        procedimentos de natureza legal, salvo mediante consulta prévia e expressa de
        profissionais qualificados. Ademais, este documento contém informações de caráter
        confidencial e de propriedade exclusiva, cuja reprodução, distribuição ou
        divulgação a terceiros estão expressamente vedadas sem a devida autorização por
        escrito da parte emitente. Qualquer uso inadequado ou divulgação não autorizada
        poderá ensejar a adoção de medidas legais cabíveis.</p>
      </div>
      <div class="ex-ftr"><span class="ex-ftr-num">4</span></div>
    </div>
    """


# ── PAGINA 5: RESUMO PORTFOLIO ───────────────────────────────────────────
def render_resumo(cliente_nome, plant_name, ano, mes, kpis, pvsyst,
                  fonte_energia="", logo_b64=""):
    """Resumo executivo — 1 linha 'portfolio' = a usina única."""
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    er = float(kpis.get("energia_real", 0) or 0)
    poa = float(kpis.get("poa", 0) or 0)
    pr_real = float(kpis.get("pr_real", 0) or 0)
    kwp = float(kpis.get("kwp", 0) or 0)
    # Fallback: se POA nao veio do banco, usa PVsyst glob_inc
    if poa == 0:
        poa = float(pvsyst.get("glob_inc") or 0)
    # Fallback: se PR nao veio do banco, calcula com energia/(kwp*POA)
    if pr_real == 0 and kwp > 0 and poa > 0:
        pr_real = (er / kwp) / poa * 100
    # PR pode estar em escala 0-1 ou 0-100; normaliza para %
    if pr_real > 0 and pr_real < 2: pr_real = pr_real * 100
    # Sanity: PR > 120% = POA invalido (incompleto). Marca como inconsistente.
    pr_real_s = _fmt_p(pr_real, 2) if 0 < pr_real <= 120 else "—"
    # POA invalido tambem
    poa_s = _fmt_n(poa, 2) if poa >= 50 else "—"  # < 50 kWh/m² no mes = invalido
    p50 = float(pvsyst.get("p50") or 0)
    p75 = float(pvsyst.get("p75") or 0)
    desv_p50 = ((er - p50) / p50 * 100) if p50 else 0
    desv_p90 = ((er - p75) / p75 * 100) if p75 else 0

    obs = ""
    if fonte_energia and "Huawei" in fonte_energia:
        obs = f"<li>Os dados de geração foram obtidos através do portal FusionSolar da Huawei.</li>"
    elif fonte_energia and "iSolar" in fonte_energia:
        obs = f"<li>Os dados de geração foram obtidos através do portal iSolarCloud da Sungrow.</li>"
    elif fonte_energia and "Banco" in fonte_energia:
        obs = f"<li>Os dados de geração foram obtidos através do banco de dados AEVO.</li>"

    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h2">2 &nbsp; Resumo</div>
      <div class="ex-body">
        <p>Este documento apresenta a análise comparativa do desempenho operacional do
        portfólio fotovoltaico no período de <b>{mes:02d}/{ano}</b>, com ênfase nos
        parâmetros técnicos fundamentais: geração energética, irradiação e
        <i>Performance Ratio</i>.</p>
      </div>

      <table class="ex-tbl" data-tbl="resumo-portfolio">
        <thead>
          <tr>
            <th>USINA</th>
            <th class="num">GERAÇÃO – INV (kWh)</th>
            <th class="num">IRRADIAÇÃO (kWh/m²)</th>
            <th class="num">PR (%)</th>
            <th class="num">DESVIO P50 (%)</th>
            <th class="num">DESVIO P90 (%)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{plant_name}</td>
            <td class="num" data-kpi="energia_real" data-fmt="n2">{_fmt_n(er, 2)}</td>
            <td class="num" data-kpi="poa" data-fmt="n2">{poa_s}</td>
            <td class="num" data-kpi="pr_real" data-fmt="p2">{pr_real_s}</td>
            <td class="num">{_fmt_signed_pct(desv_p50, 2) if p50 else "—"}</td>
            <td class="num">{_fmt_signed_pct(desv_p90, 2) if p75 else "—"}</td>
          </tr>
        </tbody>
      </table>
      <div class="ex-tbl-cap"><b>Tabela 1:</b> Resumo por usina — Geração, Irradiação, PR e desvios P50/P90</div>

      <div class="ex-h3">Observações</div>
      <ul class="ex-list">
        {obs}
        <li>Os desvios P50/P90 referem-se às projeções PVsyst do projeto original.</li>
      </ul>
      <div class="ex-ftr"><span class="ex-ftr-num">5</span></div>
    </div>
    """


# ── PAGINA 6: DETALHE USINA — RESUMO + OCORRENCIAS ───────────────────────
def render_usina_resumo(cliente_nome, plant_name, ano, mes,
                         kpis, pvsyst, disp_op_media, df_paradas,
                         fonte_energia="", logo_b64=""):
    """Pagina de cabecalho da usina: tabela comparativa PVSYST vs MEDIDO."""
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    er = float(kpis.get("energia_real", 0) or 0)
    poa_med = float(kpis.get("poa", 0) or 0)
    pr_real = float(kpis.get("pr_real", 0) or 0)
    kwp = float(kpis.get("kwp", 0) or 0)

    e_grid_pv = float(pvsyst.get("e_grid") or 0)
    poa_pv = float(pvsyst.get("glob_inc") or 0)
    pr_pv = float(pvsyst.get("pr") or 0)
    disp_pv = 99.0

    # Fallback POA/PR se nao vieram do banco
    if poa_med == 0: poa_med = poa_pv
    if pr_real == 0 and kwp > 0 and poa_med > 0:
        pr_real = (er / kwp) / poa_med * 100
    if pr_real > 0 and pr_real < 2: pr_real = pr_real * 100
    if pr_pv > 0 and pr_pv < 2: pr_pv = pr_pv * 100
    # Sanity: PR > 120% ou POA < 50 kWh/m² no mes = inconsistente
    poa_med_valid = poa_med >= 50
    pr_real_valid = 0 < pr_real <= 120
    poa_med_s = _fmt_n(poa_med, 2) if poa_med_valid else "—"
    pr_real_s = _fmt_n(pr_real, 2) if pr_real_valid else "—"

    def _desv(med, pv):
        if not pv: return 0
        return (med - pv) / pv * 100

    desv_ger = _desv(er, e_grid_pv)
    desv_disp = _desv(disp_op_media, disp_pv)
    desv_poa = _desv(poa_med, poa_pv)
    desv_pr = _desv(pr_real, pr_pv)

    n_paradas = len(df_paradas) if df_paradas is not None and not df_paradas.empty else 0
    obs_oc = (f"Foram registradas <b data-kpi='total_ev' data-fmt='n0'>{n_paradas}</b> "
              f"ocorrências operacionais no período. Detalhamento nas próximas páginas.")
    if n_paradas == 0:
        obs_oc = "Não foram registradas ocorrências significativas no período."

    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h2">3 &nbsp; {plant_name}</div>
      <div class="ex-h3">Resumo</div>
      <div class="ex-body">
        <p>O desempenho operacional da Usina <b>{plant_name}</b> no período de
        <b>{mes:02d}/{ano}</b> apresentou os seguintes resultados principais, conforme
        detalhado na Tabela 2:</p>
      </div>

      <table class="ex-tbl ex-tbl-comp" data-tbl="comp-pvsyst">
        <thead>
          <tr>
            <th>CATEGORIA</th>
            <th class="num">GERAÇÃO (kWh)</th>
            <th class="num">DISPONIBILIDADE OPERAÇÃO (%)</th>
            <th class="num">IRRADIAÇÃO (kWh/m²)</th>
            <th class="num">PR (%)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="cat">PVSYST</td>
            <td class="num">{_fmt_n(e_grid_pv, 2)}</td>
            <td class="num">{_fmt_n(disp_pv, 2)}</td>
            <td class="num">{_fmt_n(poa_pv, 2)}</td>
            <td class="num">{_fmt_n(pr_pv, 2)}</td>
          </tr>
          <tr>
            <td class="cat">MEDIDO</td>
            <td class="num" data-kpi="energia_real" data-fmt="n2">{_fmt_n(er, 2)}</td>
            <td class="num" data-kpi="disp_ger" data-fmt="p2">{_fmt_n(disp_op_media, 2)}</td>
            <td class="num" data-kpi="poa" data-fmt="n2">{poa_med_s}</td>
            <td class="num" data-kpi="pr_real" data-fmt="p2">{pr_real_s}</td>
          </tr>
          <tr class="desvio-row">
            <td class="cat">DESVIO</td>
            <td class="num">{_fmt_signed_pct(desv_ger, 2) if e_grid_pv else "—"}</td>
            <td class="num">{_fmt_signed_pct(desv_disp, 2)}</td>
            <td class="num">{_fmt_signed_pct(desv_poa, 2) if (poa_med_valid and poa_pv) else "—"}</td>
            <td class="num">{_fmt_signed_pct(desv_pr, 2) if (pr_real_valid and pr_pv) else "—"}</td>
          </tr>
        </tbody>
      </table>
      <div class="ex-tbl-cap"><b>Tabela 2:</b> Comparativo geral — Geração, Disponibilidade, Irradiação e PR</div>

      <div class="ex-h3">Ocorrências</div>
      <div class="ex-obs">{obs_oc}</div>

      <div class="ex-body">
        <p>A tabela na próxima página apresenta a comparação diária entre os valores
        previstos (PVsyst) e medidos para a usina {plant_name}.</p>
      </div>
      <div class="ex-ftr"><span class="ex-ftr-num">6</span></div>
    </div>
    """


# ── PAGINA 7: TABELA DIARIA ──────────────────────────────────────────────
def render_usina_tabela_diaria(cliente_nome, plant_name, ano, mes,
                                df_daily, pvsyst, kpis, df_poa_dia=None,
                                logo_b64=""):
    """Tabela 31 dias: Geração Prev/Med, Irradiação Prev/Med, PR Prev/Med."""
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    dias_mes = calendar.monthrange(ano, mes)[1]
    e_grid_pv = float(pvsyst.get("e_grid") or 0)
    poa_pv = float(pvsyst.get("glob_inc") or 0)
    pr_pv = float(pvsyst.get("pr") or 0)
    pr_pv = pr_pv * 100 if pr_pv < 2 else pr_pv

    # Distribui PVsyst em valores diarios (uniforme)
    e_prev_dia = e_grid_pv / dias_mes if dias_mes else 0
    poa_prev_dia = poa_pv / dias_mes if dias_mes else 0

    # Agrega df_daily por dia
    energia_por_dia = {}
    if df_daily is not None and not df_daily.empty:
        for _, r in df_daily.iterrows():
            d = r["dia"]
            if hasattr(d, "strftime"): dia_str = d.strftime("%Y-%m-%d")
            else:
                s = str(d); dia_str = s if "-" in s else f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            try: dia_n = int(dia_str[8:10])
            except: continue
            energia_por_dia[dia_n] = energia_por_dia.get(dia_n, 0) + float(r["energia_kwh"])

    # POA diaria (se disponivel)
    poa_por_dia = {}
    if df_poa_dia is not None and hasattr(df_poa_dia, "empty") and not df_poa_dia.empty:
        for _, r in df_poa_dia.iterrows():
            try:
                d = r.get("dia") or r.get("dt")
                if hasattr(d, "day"): dia_n = d.day
                else: dia_n = int(str(d)[8:10])
                poa_val = float(r.get("poa", r.get("poa_kwh_m2", 0)) or 0)
                poa_por_dia[dia_n] = poa_val
            except: continue

    # kWp do plant (passado via kpis["kwp"] pelo caller)
    kwp = float(kpis.get("kwp", 0) or 0)

    # Calcular PR diario: PR = (Energia/kWp) / POA * 100
    rows_html = ""
    total_med_e = 0; total_med_poa = 0
    tem_poa_diaria = bool(poa_por_dia)
    for d in range(1, dias_mes + 1):
        e_med = energia_por_dia.get(d, 0)
        # POA: usa real se tiver, senao deixa zero (NAO faz fallback p/ pvsyst)
        poa_med = poa_por_dia.get(d, 0)
        if kwp > 0 and poa_med > 0:
            pr_med = (e_med / kwp) / poa_med * 100
        else: pr_med = 0
        total_med_e += e_med
        total_med_poa += poa_med
        # Exibir "—" quando nao tem dado real
        poa_med_s = _fmt_n(poa_med, 2) if poa_med > 0 else "—"
        pr_med_s = _fmt_n(pr_med, 2) if pr_med > 0 else "—"
        rows_html += (
            f"<tr>"
            f"<td>{d:02d}/{mes:02d}/{ano}</td>"
            f"<td class='num'>{_fmt_n(e_prev_dia, 2)}</td>"
            f"<td class='num'>{_fmt_n(poa_prev_dia, 2)}</td>"
            f"<td class='num'>{_fmt_n(pr_pv, 2)}</td>"
            f"<td class='num'>{_fmt_n(e_med, 2)}</td>"
            f"<td class='num'>{poa_med_s}</td>"
            f"<td class='num'>{pr_med_s}</td>"
            f"</tr>"
        )
    # Linha total
    pr_total_med = float(kpis.get("pr_real", 0) or 0)
    # Fallback: se PR nao veio do banco, calcula com totais
    if pr_total_med == 0 and kwp > 0 and total_med_poa > 0:
        pr_total_med = (total_med_e / kwp) / total_med_poa * 100
    if pr_total_med > 0 and pr_total_med < 2: pr_total_med *= 100
    # Se nao temos POA medido real, exibe "—" no total POA medido tambem
    poa_total_med_s = _fmt_n(total_med_poa, 2) if tem_poa_diaria else "—"
    pr_total_med_s = _fmt_n(pr_total_med, 2) if pr_total_med > 0 else "—"
    pr_pv_norm = pr_pv * 100 if pr_pv < 2 else pr_pv
    rows_html += (
        f"<tr class='total'>"
        f"<td>TOTAL</td>"
        f"<td class='num'>{_fmt_n(e_grid_pv, 2)}</td>"
        f"<td class='num'>{_fmt_n(poa_pv, 2)}</td>"
        f"<td class='num'>{_fmt_n(pr_pv_norm, 2)}</td>"
        f"<td class='num' data-kpi='energia_real' data-fmt='n2'>{_fmt_n(total_med_e, 2)}</td>"
        f"<td class='num' data-kpi='poa' data-fmt='n2'>{poa_total_med_s}</td>"
        f"<td class='num' data-kpi='pr_real' data-fmt='p2'>{pr_total_med_s}</td>"
        f"</tr>"
    )

    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h3">3.2 &nbsp; Geração diária</div>
      <table class="ex-tbl" data-tbl="diaria-comp" style="font-size:7.5pt">
        <thead>
          <tr>
            <th>DATA</th>
            <th class="num">GERAÇÃO PREVISTA (kWh)</th>
            <th class="num">IRRADIAÇÃO PREVISTA (kWh/m²)</th>
            <th class="num">PR PREVISTA (%)</th>
            <th class="num">GERAÇÃO MEDIDA (kWh)</th>
            <th class="num">IRRADIAÇÃO MEDIDA (kWh/m²)</th>
            <th class="num">PR MEDIDA (%)</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="ex-tbl-cap"><b>Tabela 3:</b> Comparação diária entre geração prevista e medida — {MESES_PT[mes]}/{ano}</div>
      <div class="ex-ftr"><span class="ex-ftr-num">7</span></div>
    </div>
    """


# ── PAGINA 8: ANALISE OCORRENCIAS (Tier 1) ───────────────────────────────
def render_analise_ocorrencias(cliente_nome, plant_name, ano, mes,
                                kpis_5est, df_paradas, df_al=None, logo_b64=""):
    """Pagina executiva da analise de ocorrencias com KPIs de causa."""
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    pct_ger = float(kpis_5est.get("pct_geracao", 0)) if kpis_5est else 0
    pct_conc = float(kpis_5est.get("pct_conc", 0)) if kpis_5est else 0
    pct_om = float(kpis_5est.get("pct_om", 0)) if kpis_5est else 0
    pct_irr = float(kpis_5est.get("pct_irr", 0)) if kpis_5est else 0
    n_par = len(df_paradas) if df_paradas is not None and not df_paradas.empty else 0
    n_al  = len(df_al) if df_al is not None and not df_al.empty else 0
    total_ev = n_par + n_al
    total_h = float(df_paradas["duracao_h"].sum()) if (df_paradas is not None and not df_paradas.empty) else 0

    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h3">3.3 &nbsp; Análise de disponibilidade e ocorrências</div>
      <div class="ex-body">
        <p>Classificação automática das ocorrências por causa raiz, conforme o sistema
        de cinco estados (Geração / Irradiação / Concessionária / Equipamento &amp; O&amp;M).</p>
      </div>

      <div class="ex-kpi-grid">
        <div class="ex-kpi-card green">
          <div class="lbl">Disp. Geração</div>
          <div class="val" data-kpi="disp_ger" data-fmt="p2">{_fmt_p(pct_ger, 2)}%</div>
        </div>
        <div class="ex-kpi-card blue">
          <div class="lbl">Perdas Concess.</div>
          <div class="val" data-kpi="pct_conc" data-fmt="p2">{_fmt_p(pct_conc, 2)}%</div>
        </div>
        <div class="ex-kpi-card red">
          <div class="lbl">Perdas Eq./O&amp;M</div>
          <div class="val" data-kpi="pct_om" data-fmt="p2">{_fmt_p(pct_om, 2)}%</div>
        </div>
        <div class="ex-kpi-card">
          <div class="lbl">Perdas Irradiação</div>
          <div class="val">{_fmt_p(pct_irr, 2)}%</div>
        </div>
        <div class="ex-kpi-card orange">
          <div class="lbl">Total Eventos</div>
          <div class="val" data-kpi="total_ev" data-fmt="n0">{total_ev}</div>
        </div>
        <div class="ex-kpi-card green">
          <div class="lbl">Fechados</div>
          <div class="val">{total_ev - 0}</div>
        </div>
        <div class="ex-kpi-card">
          <div class="lbl">Em aberto</div>
          <div class="val">0</div>
        </div>
        <div class="ex-kpi-card">
          <div class="lbl">Total Horas OFF</div>
          <div class="val" data-kpi="total_h_off" data-fmt="h2">{_fmt_n(total_h, 1)} h</div>
        </div>
      </div>

      <div class="ex-obs">
        <b>Metodologia:</b> os percentuais somam 100% e representam a distribuição
        temporal do mês entre estados operacionais. Disp. Geração indica o tempo em
        que a planta gerou normalmente; demais categorias são distribuídas conforme
        a causa raiz das paradas detectadas via alarmes do portal de monitoramento.
      </div>
      <div class="ex-ftr"><span class="ex-ftr-num">8</span></div>
    </div>
    """


# ── PAGINA 9+: TABELA DE OCORRENCIAS ─────────────────────────────────────
def render_tabela_ocorrencias(cliente_nome, plant_name, ano, mes,
                               df_paradas, logo_b64=""):
    """Tabela detalhada de paradas/alarmes."""
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="ex-logo-aevo">' if logo_b64 else ""
    cli = f'<div class="ex-logo-cli-text">{cliente_nome}</div>'
    rows_html = ""
    if df_paradas is not None and not df_paradas.empty:
        for i, r in df_paradas.iterrows():
            rows_html += (
                f"<tr>"
                f"<td>{r.get('tipo', 'Alarme')}</td>"
                f"<td>{r.get('inversor', '')}</td>"
                f"<td>{r.get('inicio', '')}</td>"
                f"<td>{r.get('fim', '')}</td>"
                f"<td class='num'>{_fmt_n(r.get('duracao_h', 0), 2)} h</td>"
                f"<td>{r.get('causa', '')}</td>"
                f"<td>{r.get('responsavel', '')}</td>"
                f"</tr>"
            )
    else:
        rows_html = "<tr><td colspan='7' style='text-align:center;color:#9CA3AF;padding:10mm'>Nenhuma ocorrência registrada</td></tr>"

    return f"""
    <div class="pag-exec">
      <div class="ex-hdr">{logo_html}{cli}</div>
      <div class="ex-h3">3.4 &nbsp; Registro de ocorrências</div>
      <table class="ex-tbl" data-tbl="ocorrencias" style="font-size:7.5pt">
        <thead>
          <tr>
            <th>TIPO</th>
            <th>EQUIPAMENTO</th>
            <th>INÍCIO</th>
            <th>FIM</th>
            <th class="num">DURAÇÃO</th>
            <th>CAUSA</th>
            <th>RESPONSÁVEL</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div class="ex-tbl-cap"><b>Tabela 4:</b> Registro detalhado de ocorrências — {MESES_PT[mes]}/{ano}</div>
      <div class="ex-ftr"><span class="ex-ftr-num">9</span></div>
    </div>
    """


# ── FUNCAO PRINCIPAL ─────────────────────────────────────────────────────
def render_executivo_html(data, ano, mes, logo_b64=""):
    """Gera HTML completo do relatorio executivo.

    Args:
      data: dict de coletar_dados_usina ou coletar_do_supabase
      ano, mes: periodo
      logo_b64: logo AEVO em base64 (sem prefix)

    Returns:
      str HTML (sem <html><head><body>; eh adicionado externamente em app.py)
    """
    cad = data.get("cad", {})
    plant_name = str(cad.get("name", "Usina"))
    cliente_nome = plant_name  # por enquanto sem campo cliente separado
    kpis = data.get("kpis", {}) or {}
    pvsyst = data.get("pvsyst", {}) or {}
    kpis_5est = data.get("kpis_5est")
    disp_op_media = float(data.get("disp_op_media", 0) or 0)
    df_daily = data.get("df_daily")
    df_paradas = data.get("df_paradas")
    df_al = data.get("df_al")
    df_poa_dia = data.get("df_poa_dia")
    fonte_energia = data.get("fonte_energia", "")

    # Junta KPIs + kwp p/ uso interno
    kpis = dict(kpis)
    kpis["kwp"] = float(cad.get("nominal_power_kwp") or 0)
    kpis["poa"] = float(data.get("poa", kpis.get("poa", 0)) or 0)

    html = "<body class='exec'>"
    html += render_capa(cliente_nome, ano, mes, logo_b64)
    html += render_sumario(cliente_nome, logo_b64)
    html += render_sobre_aevo(cliente_nome, logo_b64)
    html += render_disclaimer(cliente_nome, logo_b64)
    html += render_resumo(cliente_nome, plant_name, ano, mes, kpis, pvsyst,
                          fonte_energia=fonte_energia, logo_b64=logo_b64)
    html += render_usina_resumo(cliente_nome, plant_name, ano, mes,
                                 kpis, pvsyst, disp_op_media, df_paradas,
                                 fonte_energia=fonte_energia, logo_b64=logo_b64)
    html += render_usina_tabela_diaria(cliente_nome, plant_name, ano, mes,
                                        df_daily, pvsyst, kpis, df_poa_dia=df_poa_dia,
                                        logo_b64=logo_b64)
    # Tier 1: analise + tabela ocorrencias
    if kpis_5est and (kpis_5est.get("tier") == 1):
        html += render_analise_ocorrencias(cliente_nome, plant_name, ano, mes,
                                             kpis_5est, df_paradas, df_al=df_al,
                                             logo_b64=logo_b64)
        html += render_tabela_ocorrencias(cliente_nome, plant_name, ano, mes,
                                            df_paradas, logo_b64=logo_b64)
    html += "</body>"
    return html
