"""Codigo CSS+HTML+JavaScript injetado nos HTMLs para tornar o relatorio dinamico.

Estrutura:
1. CSS — estilo do drawer e edicoes inline
2. HTML — drawer com 4 abas + botao flutuante
3. JS_CALC — funcoes puras de calculo (espelha calc_kpis Python)
4. JS_UTILS — formatadores e helpers
5. JS_REDRAW — atualiza DOM apos mudanca no STATE (KPIs, tabelas, charts, heatmap)
6. JS_DRAWER — UI do drawer (abrir/fechar, navegacao entre abas)
7. JS_TABS — uma funcao por aba (Inversores, Tarifa/POA, Ocorrencias, Parametrizacao)
8. JS_EXPORT — exportar HTML modificado e imprimir/PDF
9. JS_INIT — bootstrap
"""

# ──────────────────────────────────────────────────────────────────────────
# 1. CSS — drawer + overrides
# ──────────────────────────────────────────────────────────────────────────
CSS = r"""
/* Permite rolagem em tela (mantem layout A4 ao imprimir) */
@media screen {
  html, body { overflow-y: auto !important; height: auto !important; }
  body { padding-bottom: 80px; /* espaco pro FAB nao tampar conteudo */ }
}

/* Botao flutuante */
.dyn-fab {
  position: fixed; bottom: 22px; right: 22px; z-index: 9998;
  background: #E97132; color: white; border: none; border-radius: 28px;
  padding: 10px 18px; font: 600 12px Arial; cursor: pointer;
  box-shadow: 0 6px 18px rgba(0,0,0,.22); display: flex; gap: 6px; align-items: center;
}
.dyn-fab:hover { background: #d05a1b; }
.dyn-fab span { font-size: 16px; }

/* Drawer lateral direito */
.dyn-drawer-bg {
  position: fixed; inset: 0; background: rgba(14,40,65,.35); z-index: 9999;
  display: none; align-items: stretch; justify-content: flex-end;
}
.dyn-drawer-bg.open { display: flex; }
.dyn-drawer {
  background: white; width: 520px; max-width: 95vw; height: 100vh;
  display: flex; flex-direction: column; box-shadow: -8px 0 28px rgba(0,0,0,.18);
  font-family: Arial, sans-serif; color: #17324A;
}
.dyn-drawer-head {
  background: #0E2841; color: white; padding: 12px 18px; display: flex;
  justify-content: space-between; align-items: center;
}
.dyn-drawer-head .ttl { font-size: 15px; font-weight: 700; }
.dyn-drawer-head .close {
  background: transparent; border: none; color: white; font-size: 20px;
  cursor: pointer; line-height: 1; padding: 0 6px;
}
.dyn-tabs {
  display: flex; background: #F5F8FB; border-bottom: 1px solid #D9E3EC;
}
.dyn-tab {
  flex: 1; padding: 10px 6px; border: none; background: transparent;
  font: 600 11px Arial; color: #6B7C8F; cursor: pointer;
  border-bottom: 3px solid transparent;
}
.dyn-tab.active { color: #0F9ED5; border-bottom-color: #0F9ED5; background: white; }
.dyn-body { flex: 1; overflow-y: auto; padding: 16px 18px; }

/* Conteudo das abas */
.dyn-row {
  display: flex; align-items: center; gap: 10px; padding: 8px 0;
  border-bottom: 1px solid #ECF1F5;
}
.dyn-row:last-child { border-bottom: none; }
.dyn-label { flex: 1; font-size: 13px; }
.dyn-sub { font-size: 11px; color: #6B7C8F; }
.dyn-input {
  width: 100%; padding: 7px 10px; border: 1px solid #D9E3EC; border-radius: 5px;
  font: 13px Arial; color: #17324A; box-sizing: border-box;
}
.dyn-input:focus { outline: none; border-color: #0F9ED5; }
.dyn-btn {
  padding: 8px 14px; border-radius: 5px; border: none; font: 600 12px Arial;
  cursor: pointer; background: #0F9ED5; color: white;
}
.dyn-btn:hover { background: #0b6e96; }
.dyn-btn.secondary { background: #F5F8FB; color: #17324A; border: 1px solid #D9E3EC; }
.dyn-btn.danger { background: #E45C54; color: white; }
.dyn-btn.tiny { padding: 4px 8px; font-size: 11px; }
.dyn-foot {
  padding: 12px 18px; background: #F5F8FB; border-top: 1px solid #D9E3EC;
  display: flex; gap: 10px; justify-content: space-between;
}

/* Tabela de ocorrencias editavel */
.dyn-tbl { width: 100%; font: 11px Arial; border-collapse: collapse; }
.dyn-tbl thead th { background: #0E2841; color: white; padding: 6px; text-align: left; font-size: 10px; }
.dyn-tbl tbody td { padding: 4px 6px; border-bottom: 1px solid #ECF1F5; font-size: 11px; }
.dyn-tbl select, .dyn-tbl input { padding: 3px 5px; font: 11px Arial; border: 1px solid #D9E3EC; border-radius: 3px; }

/* Aviso/feedback no drawer */
.dyn-feedback {
  background: #FFF7F0; border-left: 3px solid #E97132; padding: 8px 12px;
  border-radius: 4px; font-size: 12px; margin-bottom: 12px;
}
.dyn-feedback.error { background: #FEEAE8; border-color: #E45C54; }
.dyn-feedback.ok { background: #E1F5EE; border-color: #2CA66F; }

/* Esconde drawer ao imprimir */
@media print {
  .dyn-fab, .dyn-drawer-bg { display: none !important; }
}
"""


# ──────────────────────────────────────────────────────────────────────────
# 2. HTML do drawer (string injetada no <body>)
# ──────────────────────────────────────────────────────────────────────────
DRAWER_HTML = """
<button class="dyn-fab" onclick="window.__UI.abrir()">
  <span>📝</span> Editar relatorio
</button>
<div id="dyn-drawer-bg" class="dyn-drawer-bg" onclick="if(event.target===this)window.__UI.fechar()">
  <div class="dyn-drawer">
    <div class="dyn-drawer-head">
      <div class="ttl">Editar relatorio</div>
      <button class="close" onclick="window.__UI.fechar()">×</button>
    </div>
    <div class="dyn-tabs">
      <button class="dyn-tab" data-tab="inversores" onclick="window.__UI.tab('inversores')">🔌 Inversores</button>
      <button class="dyn-tab" data-tab="tarifa" onclick="window.__UI.tab('tarifa')">💰 Tarifa &amp; POA</button>
      <button class="dyn-tab" data-tab="ocorrencias" onclick="window.__UI.tab('ocorrencias')">🚨 Ocorrencias</button>
      <button class="dyn-tab" data-tab="param" onclick="window.__UI.tab('param')">⚙ Parametrizacao</button>
    </div>
    <div id="dyn-body" class="dyn-body"></div>
    <div class="dyn-foot">
      <div>
        <button class="dyn-btn secondary" onclick="window.__UI.resetar()">↺ Resetar tudo</button>
      </div>
      <div style="display:flex;gap:8px">
        <button class="dyn-btn secondary" onclick="window.__UI.exportarHTML()">⬇ HTML</button>
        <button class="dyn-btn" onclick="window.print()">🖨 PDF</button>
      </div>
    </div>
  </div>
</div>
"""


# ──────────────────────────────────────────────────────────────────────────
# 3-9. JS unificado
# ──────────────────────────────────────────────────────────────────────────
JS_BUNDLE = r"""
/* AEVO19 — Sistema dinamico de edicao de relatorios */
(function(){
  'use strict';

  // ─── Utilitarios ─────────────────────────────────────────────────────
  function round(v, d) {
    d = d || 0;
    var m = Math.pow(10, d);
    return Math.round(v * m) / m;
  }
  function fmtN(v, d) {
    if (v === null || v === undefined || isNaN(v)) return '---';
    var s = Number(v).toFixed(d || 0);
    var parts = s.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return parts.join(',');
  }
  function fmtP(v, d) {
    if (v === null || v === undefined || isNaN(v)) return '---';
    return Number(v).toFixed(d == null ? 1 : d).replace('.', ',') + '%';
  }
  function fmtRS(v) {
    return 'R$ ' + fmtN(v, 2);
  }
  function uniqId(prefix) { return prefix + '_' + Math.random().toString(36).slice(2, 8); }

  // ─── CALCULO (puro, sem efeitos colaterais) ─────────────────────────
  function categoriaDoResponsavel(label, vocab) {
    if (!label) return null;
    var r = (vocab.responsaveis || []).find(function(x){ return x.label === label; });
    return r ? r.categoria : null;
  }

  function getInverters(state) {
    var excl = new Set(state.inversores_excluidos || []);
    return window.__RAW_DATA.inverters.filter(function(inv){ return !excl.has(inv.nome); });
  }

  function getParadas(state) {
    var excl = new Set(state.inversores_excluidos || []);
    var edits = state.paradas_editadas || {};
    return window.__RAW_DATA.paradas
      .filter(function(p){ return !excl.has(p.inversor); })
      .map(function(p){
        var edit = edits[p.id];
        return edit ? Object.assign({}, p, edit) : p;
      });
  }

  function calcularKPIs(state) {
    var inverters = getInverters(state);
    var paradas = getParadas(state);
    var raw = window.__RAW_DATA;
    var vocab = state.vocab || window.__VOCAB_DEFAULT;
    var kwp = raw.plant.kwp || 0;
    var dias_mes = raw.plant.dias_mes;
    var n_inv = inverters.length;

    var energia_real = 0;
    var dias_set = new Set();
    var energia_por_inv = {};
    var dias_com_dado_por_inv = {};
    inverters.forEach(function(inv){
      var soma = 0;
      var keys = Object.keys(inv.energias_diarias);
      keys.forEach(function(d){
        soma += inv.energias_diarias[d];
        dias_set.add(d);
      });
      energia_por_inv[inv.nome] = soma;
      dias_com_dado_por_inv[inv.nome] = keys.length;
      energia_real += soma;
    });
    var energia_dia = {};
    inverters.forEach(function(inv){
      Object.keys(inv.energias_diarias).forEach(function(d){
        energia_dia[d] = (energia_dia[d] || 0) + inv.energias_diarias[d];
      });
    });

    var ee = raw.pvsyst.e_grid || 0;
    var pr_e = raw.pvsyst.pr || 0;
    var glob_inc = raw.pvsyst.glob_inc || 0;
    var poa = state.poa_kwh_m2 || 0;
    var tarifa = state.tarifa_rs_kwh || 0;
    var pr_real = (poa > 0 && kwp > 0) ? (energia_real / (poa * kwp)) : 0;
    var esp_kwp = kwp ? (energia_real / kwp) : 0;
    var at = ee ? round(energia_real / ee * 100, 1) : 0;
    var var_poa = (poa > 0 && glob_inc > 0) ? round((poa - glob_inc) / glob_inc * 100, 1) : 0;
    var dias_com_dado = dias_set.size;
    var cob_pct = dias_mes ? round(dias_com_dado / dias_mes * 100, 1) : 0;
    var disp_ger_cobertura = 0;
    if (n_inv > 0) {
      var soma_disp = 0;
      inverters.forEach(function(inv){
        var pct = (dias_com_dado_por_inv[inv.nome] || 0) / dias_mes * 100;
        soma_disp += round(pct, 1);
      });
      disp_ger_cobertura = soma_disp / n_inv;
    }
    var receita = energia_real * tarifa;

    // 5 estados (subtracao das perdas do inversor excluido)
    var orig = raw.kpis_originais || {};
    var HORAS_SOLARES_POR_DIA = 11.5;
    var horas_solares_por_inv = dias_mes * HORAS_SOLARES_POR_DIA;
    var n_inv_orig = window.__RAW_DATA.inverters.length;
    var H_TOTAL_ORIG = n_inv_orig * horas_solares_por_inv;
    var excl = new Set(state.inversores_excluidos || []);

    var h_conc_excl = 0, h_om_excl = 0, h_outro_excl = 0;
    raw.paradas.forEach(function(p){
      if (!excl.has(p.inversor)) return;
      var edit = (state.paradas_editadas || {})[p.id];
      var pp = edit ? Object.assign({}, p, edit) : p;
      var cat = categoriaDoResponsavel(pp.responsavel, vocab);
      var h = pp.duracao_h || 0;
      if (cat === "concessionaria") h_conc_excl += h;
      else if (cat === "om") h_om_excl += h;
      else if (cat === "outro") h_outro_excl += h;
    });
    var h_conc_orig = (orig.pct_conc || 0) * H_TOTAL_ORIG / 100;
    var h_om_orig   = (orig.pct_om   || 0) * H_TOTAL_ORIG / 100;
    var h_irr_orig  = (orig.pct_irr  || 0) * H_TOTAL_ORIG / 100;
    var n_excl = excl.size;
    var n_inv_atual = Math.max(0, n_inv_orig - n_excl);
    var H_TOTAL_NOVO = n_inv_atual * horas_solares_por_inv;
    var h_conc_novo  = Math.max(0, h_conc_orig - h_conc_excl);
    var h_om_novo    = Math.max(0, h_om_orig   - h_om_excl);
    var fracao_excluida = n_inv_orig > 0 ? (n_excl / n_inv_orig) : 0;
    var h_irr_novo   = h_irr_orig * (1 - fracao_excluida);
    var pct_conc  = H_TOTAL_NOVO > 0 ? round(h_conc_novo  / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_om    = H_TOTAL_NOVO > 0 ? round(h_om_novo    / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_outro = 0;
    var pct_irr   = H_TOTAL_NOVO > 0 ? round(h_irr_novo   / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_ger_pure = round(Math.max(0, 100 - pct_irr - pct_conc - pct_om - pct_outro), 2);
    var pct_geracao = round(pct_ger_pure + pct_irr, 2);

    var total_h_off = 0;
    var h_por_categoria = { concessionaria: 0, om: 0, outro: 0 };
    var n_ev_categoria = { concessionaria: 0, om: 0, outro: 0 };
    var horas_por_causa = {};
    paradas.forEach(function(p){
      var h = p.duracao_h || 0;
      total_h_off += h;
      var cat = categoriaDoResponsavel(p.responsavel, vocab);
      if (cat && h_por_categoria.hasOwnProperty(cat)) {
        h_por_categoria[cat] += h;
        n_ev_categoria[cat] += 1;
      }
      if (p.causa) horas_por_causa[p.causa] = (horas_por_causa[p.causa] || 0) + h;
    });

    var df_inv = inverters.map(function(inv){
      var en = energia_por_inv[inv.nome] || 0;
      return {
        inversor: inv.nome, modelo: inv.modelo,
        energia_kwh: round(en, 2),
        pct: energia_real ? round(en / energia_real * 100, 1) : 0,
        esp_kwh_kwp: (kwp && n_inv) ? round(en / (kwp / n_inv), 2) : 0,
        dias_com_dado: dias_com_dado_por_inv[inv.nome] || 0,
        disp_ger_pct: dias_mes ? round((dias_com_dado_por_inv[inv.nome] || 0) / dias_mes * 100, 1) : 0,
        disp_op_pct: inv.disp_op_pct || 0,
        horas_off: inv.horas_off || 0,
      };
    });
    df_inv.sort(function(a, b){ return b.energia_kwh - a.energia_kwh; });
    // Calcular desvios (vs media e vs melhor)
    var med_e = df_inv.length ? df_inv.reduce(function(s,x){return s+x.energia_kwh;},0) / df_inv.length : 0;
    var mel_e = df_inv.length ? Math.max.apply(null, df_inv.map(function(x){return x.energia_kwh;})) : 0;
    df_inv.forEach(function(x){
      x.desvio_media = med_e ? round((x.energia_kwh - med_e) / med_e * 100, 1) : 0;
      x.desvio_melhor = mel_e ? round((x.energia_kwh - mel_e) / mel_e * 100, 1) : 0;
    });

    var tier = orig.tier || 2;
    var disp_ger = (tier === 1) ? pct_geracao : disp_ger_cobertura;
    return {
      energia_real: round(energia_real, 2),
      ee: ee, at: at,
      pr_real: round(pr_real, 4), pr_e: pr_e, esp_kwp: round(esp_kwp, 2),
      poa: poa, var_poa: var_poa, glob_inc: glob_inc,
      dias_com_dado: dias_com_dado, cob_pct: cob_pct,
      disp_ger: disp_ger, disp_ger_cobertura: disp_ger_cobertura,
      receita: round(receita, 2), tarifa: tarifa,
      pct_geracao: pct_geracao, pct_ger_pure: pct_ger_pure,
      pct_irr: pct_irr, pct_conc: pct_conc, pct_om: pct_om, pct_outro: pct_outro,
      n_inv: n_inv,
      n_inv_orig: n_inv_orig,
      total_ev: paradas.length,
      total_h_off: round(total_h_off, 2),
      h_por_categoria: h_por_categoria,
      n_ev_categoria: n_ev_categoria,
      horas_por_causa: horas_por_causa,
      df_inv: df_inv,
      energia_dia: energia_dia,
      paradas: paradas,
    };
  }

  window.__CALC = {
    calcularKPIs: calcularKPIs,
    getInverters: getInverters,
    getParadas: getParadas,
    categoriaDoResponsavel: categoriaDoResponsavel,
  };

  // ─── Sistema reativo ──────────────────────────────────────────────────
  window.__CHARTS = {};
  window.__INITIAL_STATE = null;

  function setState(updates) {
    Object.assign(window.__STATE, updates);
    redraw();
  }

  function redraw() {
    var kpis = calcularKPIs(window.__STATE);
    atualizarKPICards(kpis);
    atualizarTabelaInversores(kpis);
    atualizarTabelaOcorrencias(kpis);
    atualizarCharts(kpis);
    atualizarHeatmap(kpis);
    atualizarBarrasHoras(kpis);
    atualizarRankingEquipamentos(kpis);
  }

  function atualizarKPICards(kpis) {
    document.querySelectorAll('[data-kpi]').forEach(function(el){
      var k = el.getAttribute('data-kpi');
      var fmt = el.getAttribute('data-fmt') || '';
      var v = kpis[k];
      if (v === undefined || v === null) return;
      if (fmt === 'n0') el.textContent = fmtN(v, 0);
      else if (fmt === 'n2') el.textContent = fmtN(v, 2);
      else if (fmt === 'p1') el.textContent = fmtP(v, 1);
      else if (fmt === 'p2') el.textContent = fmtP(v, 2);
      else if (fmt === 'p4') el.textContent = Number(v).toFixed(4).replace('.', ',');
      else if (fmt === 'p1_signed') el.textContent = (v > 0 ? '+' : '') + fmtP(v, 1);
      else if (fmt === 'pr4') el.textContent = (v === 0 ? '---' : Number(v).toFixed(4).replace('.', ','));
      else if (fmt === 'rs') el.textContent = (v === 0 ? '---' : fmtRS(v));
      else if (fmt === 'h2') el.textContent = fmtN(v, 2) + ' h';
      else if (fmt === 'poa_kwh') el.textContent = (v === 0 ? '---' : fmtN(v, 2) + ' kWh/m²');
      else if (fmt === 'tar_rs') el.textContent = (v === 0 ? '---' : 'R$ ' + fmtN(v, 2) + '/kWh');
      else el.textContent = String(v);
    });
    // Atualizar formula PR (string composta)
    document.querySelectorAll('[data-tech="pr_formula"]').forEach(function(el){
      var raw = window.__RAW_DATA;
      var en = kpis.energia_real || 0;
      var poa = kpis.poa || 0;
      var kwp = raw.plant.kwp || 0;
      if (poa > 0 && kwp > 0) {
        el.textContent = fmtN(en, 0) + ' / (' + fmtN(poa, 2) + ' x ' + fmtN(kwp, 0) + ') = ' +
                         (kpis.pr_real ? Number(kpis.pr_real).toFixed(4).replace('.', ',') : '---');
      } else {
        el.textContent = '---';
      }
    });
  }

  function atualizarTabelaInversores(kpis) {
    var tbody = document.querySelector('tbody[data-tbl="inversores"]');
    if (!tbody) return;
    var medals = ['🥇','🥈','🥉'];
    var html = '';
    kpis.df_inv.forEach(function(inv, i){
      var medal = i < 3 ? medals[i] : '';
      var chip_cls = inv.disp_op_pct >= 99 ? 'ok' : 'warn';
      var dm_cls = inv.desvio_media >= -5 ? 'cval-ok' : 'cval-bad';
      var db_cls = inv.desvio_melhor >= -5 ? 'cval-ok' : 'cval-bad';
      var row_cls = inv.desvio_media < -10 ? ' class="alrt"' : '';
      var sign_dm = (inv.desvio_media > 0 ? '+' : '') + Number(inv.desvio_media).toFixed(1).replace('.', ',') + '%';
      var sign_db = (inv.desvio_melhor > 0 ? '+' : '') + Number(inv.desvio_melhor).toFixed(1).replace('.', ',') + '%';
      html += '<tr' + row_cls + '><td>' + medal + '<span>' + inv.inversor + '</span></td>' +
              '<td>' + (inv.modelo || '') + '</td>' +
              '<td style="text-align:right">' + fmtN(inv.energia_kwh, 2) + '</td>' +
              '<td style="text-align:right">' + fmtN(inv.esp_kwh_kwp, 2) + '</td>' +
              '<td style="text-align:right">' + fmtP(inv.pct, 1) + '</td>' +
              '<td style="text-align:right">' + fmtP(inv.disp_ger_pct, 1) + '</td>' +
              '<td style="text-align:right"><span class="chip ' + chip_cls + '">' + fmtP(inv.disp_op_pct, 2) + '</span></td>' +
              '<td style="text-align:right">' + fmtN(inv.horas_off, 2) + 'h</td>' +
              '<td style="text-align:right" class="' + dm_cls + '">' + sign_dm + '</td>' +
              '<td style="text-align:right" class="' + db_cls + '">' + sign_db + '</td></tr>';
    });
    tbody.innerHTML = html;
  }

  function atualizarTabelaOcorrencias(kpis) {
    // Atualiza TODAS as tbodies da tabela de ocorrencias (a tabela pode ser
    // paginada em multiplas paginas se houver muitas paradas).
    var tbodies = document.querySelectorAll('tbody[data-tbl="ocorrencias"]');
    if (tbodies.length === 0) return;
    var raw = window.__RAW_DATA;
    var orig = raw.kpis_originais || {};
    var is_tier1 = (orig.tier || 2) === 1;

    function _faixa(inicio) {
      // dd/MM/yyyy HH:mm → faixa do dia
      try {
        var hm = parseInt(inicio.substr(11,2));
        if (hm >= 6 && hm < 8)  return ['Partida', '#E6F1FB', '#185FA5'];
        if (hm >= 8 && hm < 12) return ['Pico M',  '#FAEEDA', '#854F0B'];
        if (hm >= 12 && hm < 17)return ['Pico T',  '#FAEEDA', '#854F0B'];
        if (hm >= 17 && hm < 19)return ['Declinio','#E1F5EE', '#0F6E56'];
        return ['Fora solar', '#F1EFE8', '#5F5E5A'];
      } catch(e) { return ['—', '#F1EFE8', '#5F5E5A']; }
    }

    // Linhas geradas (mesmas para todas as tbodies — paginacao eh visual,
    // distribuimos pelo numero de linhas em cada tbody)
    var allRows = [];
    if (kpis.paradas.length === 0) {
      var cols = is_tier1 ? 9 : 7;
      allRows.push('<tr><td colspan="' + cols + '" style="text-align:center;color:#888;padding:12px">Nenhuma ocorrencia no periodo</td></tr>');
    } else {
      kpis.paradas.forEach(function(p){
        var faixa = _faixa(p.inicio);
        var faixa_html = '<span style="display:inline-block;font-size:7px;padding:1px 5px;border-radius:3px;font-weight:500;background:' + faixa[1] + ';color:' + faixa[2] + '">' + faixa[0] + '</span>';
        var row = '<tr><td><span class="chip warn">Parada Parcial</span></td>' +
                  '<td>' + p.inversor + '</td>' +
                  '<td>' + p.inicio + '</td>' +
                  '<td>' + p.fim + '</td>' +
                  '<td style="text-align:right">' + fmtN(p.duracao_h, 2) + ' h</td>' +
                  '<td>' + faixa_html + '</td>';
        if (is_tier1) {
          row += '<td>' + (p.causa || '---') + '</td>' +
                 '<td>' + (p.responsavel || '---') + '</td>';
        }
        row += '<td><span class="dot closed"></span><span>Fechado</span></td></tr>';
        allRows.push(row);
      });
    }

    // Distribui rows entre tbodies (35 por pagina, como no Python)
    var ROWS_PER_PAGE = 35;
    tbodies.forEach(function(tb, i){
      var start = i * ROWS_PER_PAGE;
      var end = start + ROWS_PER_PAGE;
      var slice = allRows.slice(start, end);
      // Se nao ha tbody dedicada (so 1 tbody = pagina 5 inicial), poe todas
      if (tbodies.length === 1) slice = allRows;
      tb.innerHTML = slice.length ? slice.join('') : '';
    });
  }

  function atualizarCharts(kpis) {
    var raw = window.__RAW_DATA;
    // ch_inv — barras por inversor
    if (window.__CHARTS.ch_inv) {
      var c = window.__CHARTS.ch_inv;
      var labels = kpis.df_inv.map(function(x){ return x.inversor; });
      var data = kpis.df_inv.map(function(x){ return x.energia_kwh; });
      var media = data.length ? data.reduce(function(s,v){return s+v;},0) / data.length : 0;
      c.data.labels = labels;
      c.data.datasets[0].data = data;
      c.data.datasets[0].backgroundColor = data.map(function(v){
        return v < media*0.85 ? "rgba(228,92,84,.82)" : "rgba(15,158,213,.78)";
      });
      c.data.datasets[1].data = labels.map(function(){ return Math.round(media); });
      c.update();
    }
    // ch_donut — distribuicao de responsabilidade
    if (window.__CHARTS.ch_donut) {
      var c = window.__CHARTS.ch_donut;
      c.data.datasets[0].data = [kpis.pct_ger_pure, kpis.pct_irr, kpis.pct_conc, kpis.pct_om];
      // Atualiza tambem o texto central
      c.options.plugins.ct_text = fmtP(kpis.disp_ger, 2);
      c.update();
    }
    // ch_hora5 — distribuicao horaria por responsavel (atualizado via atualizarBarrasHoras)
    // ch_dev e ch_disp nao precisam atualizar quase nada — manter como esta
  }

  function atualizarHeatmap(kpis) {
    var c = document.getElementById('ch_heat5');
    if (!c) return;
    if (!window.__heatmap_redraw) return;
    window.__heatmap_redraw(kpis);
  }

  function atualizarBarrasHoras(kpis) {
    // Atualiza a barra de "Horas OFF por causa" (Tier 1 pag 5)
    var cont = document.querySelector('[data-section="horas-causa"]');
    if (cont) {
      var causas = [
        {label:"Sobretensao CA", color:"#0F9ED5", tc:"#0b6e96"},
        {label:"Subtensao CA", color:"#7E57C2", tc:"#534AB7"},
        {label:"OFF (rede/coletivo)", color:"#378ADD", tc:"#185FA5"},
        {label:"Desconexao total", color:"#E45C54", tc:"#A32D2D"},
        {label:"OFF (equipamento/trip)", color:"#E45C54", tc:"#A32D2D"},
        {label:"Baixa irradiacao", color:"#A8D8B9", tc:"#4A8C6B"},
      ];
      // Tambem incluir causas customizadas
      var vocab = window.__STATE.vocab || window.__VOCAB_DEFAULT;
      (vocab.causas || []).forEach(function(c){
        if (!causas.find(function(x){return x.label===c.label;})) {
          causas.push({label:c.label, color:"#888", tc:"#555"});
        }
      });
      var max_h = 1;
      causas.forEach(function(c){ var h=kpis.horas_por_causa[c.label]||0; if (h>max_h) max_h=h; });
      var html = '';
      causas.forEach(function(c){
        var h = kpis.horas_por_causa[c.label] || 0;
        var pw = max_h > 0 ? Math.round(h/max_h*100) : 0;
        html += "<div class='bh'><div class='bh-lbl' style='width:76px;font-size:7px'>"+c.label+"</div>" +
                "<div class='bh-track' style='height:9px'><div class='bh-fill' style='width:"+pw+"%;background:"+c.color+"'></div></div>" +
                "<div class='bh-val' style='width:44px;font-size:7px;color:"+c.tc+"'>"+fmtN(h,2)+" h</div></div>";
      });
      cont.innerHTML = html;
    }
    // Atualiza ch_hora5 (distrib horaria) se existir
    if (window.__CHARTS.ch_hora5) {
      // Simplificacao: recontagem usando agora as horas das categorias × faixas horarias
      // Como nao temos faixas detalhadas por intervalo no JS, mantemos o existente
      // mas atualizamos com proporcoes das categorias atuais
      var c = window.__CHARTS.ch_hora5;
      var n_conc = kpis.n_ev_categoria.concessionaria || 0;
      var n_om = kpis.n_ev_categoria.om || 0;
      // Distribuicao em 4 faixas (Partida/PicoM/PicoT/Declinio) — proporcao constante
      // Como nao recalculamos a faixa horaria, mantem os datasets originais escalonados
      c.update();
    }
  }

  function atualizarRankingEquipamentos(kpis) {
    var cont = document.querySelector('[data-section="rank-equipamentos"]');
    if (!cont) return;
    var counts = {};
    kpis.paradas.forEach(function(p){
      counts[p.inversor] = (counts[p.inversor] || 0) + 1;
    });
    var arr = Object.keys(counts).map(function(k){ return [k, counts[k]]; });
    arr.sort(function(a,b){ return b[1]-a[1]; });
    var top = arr.slice(0, 5);
    var max_n = top.length ? top[0][1] : 1;
    var html = '';
    if (top.length === 0) {
      html = "<div style='font-size:8px;color:#6B7C8F'>Nenhuma ocorrencia detectada</div>";
    } else {
      top.forEach(function(t){
        var eq=t[0], cnt=t[1];
        var pw = Math.round(cnt/max_n*100);
        var col = cnt===max_n ? "#E97132" : (cnt>=max_n*0.5 ? "#F2B134" : "#D9E3EC");
        html += "<div class='bh'><div class='bh-lbl sm' contenteditable='true'>"+eq+"</div>" +
                "<div class='bh-track' style='height:10px'><div class='bh-fill' style='width:"+pw+"%;background:"+col+"'></div></div>" +
                "<div class='bh-val sm' contenteditable='true'>"+cnt+" ev.</div></div>";
      });
    }
    cont.innerHTML = html;
  }

  // ─── UI: drawer + abas ──────────────────────────────────────────────
  var UI = {
    abrir: function() {
      document.getElementById('dyn-drawer-bg').classList.add('open');
      if (!UI._current_tab) UI._current_tab = 'inversores';
      UI.tab(UI._current_tab);
    },
    fechar: function() {
      document.getElementById('dyn-drawer-bg').classList.remove('open');
    },
    tab: function(name) {
      UI._current_tab = name;
      document.querySelectorAll('.dyn-tab').forEach(function(t){
        t.classList.toggle('active', t.getAttribute('data-tab') === name);
      });
      var body = document.getElementById('dyn-body');
      if (name === 'inversores') body.innerHTML = renderAbaInversores();
      else if (name === 'tarifa') body.innerHTML = renderAbaTarifa();
      else if (name === 'ocorrencias') body.innerHTML = renderAbaOcorrencias();
      else if (name === 'param') body.innerHTML = renderAbaParam();
      attachAbaHandlers(name);
    },
    resetar: function() {
      if (!confirm('Resetar todas as edicoes? Isso volta ao estado original.')) return;
      window.__STATE = JSON.parse(JSON.stringify(window.__INITIAL_STATE));
      redraw();
      UI.tab(UI._current_tab || 'inversores');
    },
    exportarHTML: function() {
      // Captura o DOM atual + injeta STATE atual como dados iniciais
      var clone = document.documentElement.cloneNode(true);
      var rawScript = clone.querySelector('#__raw_data__');
      var stateScript = clone.ownerDocument && clone.querySelector('#__raw_data__') || clone.querySelectorAll('script')[0];
      // Adiciona script com STATE persistido
      var s = document.createElement('script');
      s.id = '__state_persisted__';
      s.type = 'application/json';
      s.textContent = JSON.stringify(window.__STATE);
      clone.querySelector('head').appendChild(s);
      var html = '<!doctype html>\n' + clone.outerHTML;
      var blob = new Blob([html], {type: 'text/html;charset=utf-8'});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = (window.__RAW_DATA.plant.name || 'relatorio') + '_editado.html';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(url); }, 0);
    },
  };
  window.__UI = UI;

  // ─── Aba: Inversores ──────────────────────────────────────────────
  function renderAbaInversores() {
    var raw = window.__RAW_DATA;
    var excl = new Set(window.__STATE.inversores_excluidos || []);
    var html = '<div class="dyn-feedback">Desmarque inversores para exclui-los do relatorio. ' +
               'KPIs e graficos recalculam ao aplicar.</div>';
    html += '<div>';
    raw.inverters.forEach(function(inv){
      var checked = excl.has(inv.nome) ? '' : 'checked';
      html += '<div class="dyn-row">' +
              '<input type="checkbox" data-inv="' + inv.nome + '" ' + checked + '/>' +
              '<div class="dyn-label">' + inv.nome +
              '<div class="dyn-sub">' + (inv.modelo || '') + ' &middot; ' + fmtN(inv.energia_total_kwh, 0) + ' kWh</div></div>' +
              '</div>';
    });
    html += '</div>';
    var n_excl = excl.size;
    html += '<div class="dyn-feedback ok" id="dyn-inv-status">' +
            (raw.inverters.length - n_excl) + ' inversores ativos · ' + n_excl + ' excluidos</div>';
    return html;
  }

  // ─── Aba: Tarifa & POA ─────────────────────────────────────────────
  function renderAbaTarifa() {
    var s = window.__STATE;
    var raw = window.__RAW_DATA;
    var kpis = calcularKPIs(s);
    var html = '<div class="dyn-feedback">Tarifa e POA atualizam Receita e PR em tempo real.</div>';
    html += '<div class="dyn-row" style="flex-direction:column;align-items:stretch">' +
            '<label>Tarifa (R$/kWh)</label>' +
            '<input class="dyn-input" type="number" step="0.0001" min="0" data-input="tarifa" value="' + s.tarifa_rs_kwh + '"/></div>';
    html += '<div class="dyn-row" style="flex-direction:column;align-items:stretch">' +
            '<label>POA medido (kWh/m²)</label>' +
            '<input class="dyn-input" type="number" step="0.01" min="0" data-input="poa" value="' + s.poa_kwh_m2 + '"/>' +
            '<div class="dyn-sub" style="margin-top:4px">PVsyst esperado: ' + fmtN(raw.pvsyst.glob_inc, 2) + ' kWh/m²</div></div>';
    html += '<div class="dyn-feedback ok" id="dyn-tarifa-preview">' +
            'Receita estimada: <b>' + (kpis.receita ? fmtRS(kpis.receita) : '---') + '</b><br/>' +
            'PR Real: <b>' + (kpis.pr_real ? Number(kpis.pr_real).toFixed(4).replace('.',',') : '---') + '</b> · Variação POA vs PVsyst: <b>' + (kpis.poa ? fmtP(kpis.var_poa) : '---') + '</b></div>';
    return html;
  }

  // ─── Aba: Ocorrencias ────────────────────────────────────────────
  function renderAbaOcorrencias() {
    var raw = window.__RAW_DATA;
    var s = window.__STATE;
    var vocab = s.vocab || window.__VOCAB_DEFAULT;
    var excl = new Set(s.inversores_excluidos || []);
    var paradas_visiveis = raw.paradas.filter(function(p){ return !excl.has(p.inversor); });
    if (paradas_visiveis.length === 0) {
      return '<div class="dyn-feedback">Nenhuma ocorrencia para editar (todas inversores excluidos ou periodo sem paradas).</div>';
    }
    var html = '<div class="dyn-feedback">Edite causa e responsavel. Donut e tabelas atualizam ao alterar.</div>';
    html += '<table class="dyn-tbl"><thead><tr>' +
            '<th>Inversor</th><th>Início</th><th>Duração</th><th>Causa</th><th>Responsável</th>' +
            '</tr></thead><tbody>';
    paradas_visiveis.forEach(function(p){
      var edit = (s.paradas_editadas || {})[p.id] || {};
      var causa_atual = edit.causa !== undefined ? edit.causa : p.causa;
      var resp_atual = edit.responsavel !== undefined ? edit.responsavel : p.responsavel;
      html += '<tr><td>' + p.inversor + '</td>' +
              '<td>' + p.inicio + '</td>' +
              '<td>' + fmtN(p.duracao_h, 2) + 'h</td>' +
              '<td><select data-pid="' + p.id + '" data-field="causa">';
      html += '<option value="">---</option>';
      (vocab.causas || []).forEach(function(c){
        html += '<option value="' + c.label + '"' + (c.label === causa_atual ? ' selected' : '') + '>' + c.label + '</option>';
      });
      html += '</select></td>';
      html += '<td><select data-pid="' + p.id + '" data-field="responsavel">';
      html += '<option value="">---</option>';
      (vocab.responsaveis || []).forEach(function(r){
        html += '<option value="' + r.label + '"' + (r.label === resp_atual ? ' selected' : '') + '>' + r.label + '</option>';
      });
      html += '</select></td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  // ─── Aba: Parametrizacao ───────────────────────────────────────────
  function renderAbaParam() {
    var s = window.__STATE;
    var vocab = s.vocab || window.__VOCAB_DEFAULT;
    var paradas = (s.paradas_editadas) ? [] : [];
    // Conta uso por causa/responsavel a partir das paradas atuais
    var em_uso_causa = {}, em_uso_resp = {};
    window.__RAW_DATA.paradas.forEach(function(p){
      var edit = (s.paradas_editadas || {})[p.id] || {};
      var c = edit.causa !== undefined ? edit.causa : p.causa;
      var r = edit.responsavel !== undefined ? edit.responsavel : p.responsavel;
      em_uso_causa[c] = (em_uso_causa[c] || 0) + 1;
      em_uso_resp[r] = (em_uso_resp[r] || 0) + 1;
    });

    var html = '<div class="dyn-feedback">Gerencie causas e responsaveis. Remocao bloqueada se em uso.</div>';

    // Causas
    html += '<h4 style="margin:14px 0 6px;font-size:13px">Causas</h4>';
    html += '<table class="dyn-tbl"><thead><tr><th>Label</th><th>Em uso</th><th></th></tr></thead><tbody>';
    (vocab.causas || []).forEach(function(c, idx){
      var n = em_uso_causa[c.label] || 0;
      html += '<tr><td><input class="dyn-input" data-vocab="causa" data-idx="' + idx + '" data-key="label" value="' + c.label + '"/></td>' +
              '<td>' + n + '</td>' +
              '<td><button class="dyn-btn tiny danger" data-vocab-del="causa" data-idx="' + idx + '"' +
              (n>0 ? ' disabled title="Em uso em ' + n + ' ocorrencias"' : '') + '>🗑</button></td></tr>';
    });
    html += '<tr><td colspan="3"><button class="dyn-btn tiny" data-vocab-add="causa">+ Adicionar causa</button></td></tr>';
    html += '</tbody></table>';

    // Responsaveis
    html += '<h4 style="margin:14px 0 6px;font-size:13px">Responsáveis</h4>';
    html += '<table class="dyn-tbl"><thead><tr><th>Label</th><th>Categoria</th><th>Cor</th><th>Em uso</th><th></th></tr></thead><tbody>';
    (vocab.responsaveis || []).forEach(function(r, idx){
      var n = em_uso_resp[r.label] || 0;
      html += '<tr>' +
              '<td><input class="dyn-input" data-vocab="resp" data-idx="' + idx + '" data-key="label" value="' + r.label + '"/></td>' +
              '<td><select data-vocab="resp" data-idx="' + idx + '" data-key="categoria">' +
                '<option value="concessionaria"' + (r.categoria==='concessionaria'?' selected':'') + '>Concessionária</option>' +
                '<option value="om"' + (r.categoria==='om'?' selected':'') + '>O&M</option>' +
                '<option value="outro"' + (r.categoria==='outro'?' selected':'') + '>Outro</option>' +
              '</select></td>' +
              '<td><input type="color" data-vocab="resp" data-idx="' + idx + '" data-key="cor" value="' + (r.cor||'#888') + '"/></td>' +
              '<td>' + n + '</td>' +
              '<td><button class="dyn-btn tiny danger" data-vocab-del="resp" data-idx="' + idx + '"' +
              (n>0 ? ' disabled title="Em uso em ' + n + ' ocorrencias"' : '') + '>🗑</button></td></tr>';
    });
    html += '<tr><td colspan="5"><button class="dyn-btn tiny" data-vocab-add="resp">+ Adicionar responsável</button></td></tr>';
    html += '</tbody></table>';

    return html;
  }

  // ─── Handlers por aba ────────────────────────────────────────────
  function attachAbaHandlers(name) {
    if (name === 'inversores') {
      document.querySelectorAll('[data-inv]').forEach(function(el){
        el.addEventListener('change', function(){
          var nome = el.getAttribute('data-inv');
          var excl = new Set(window.__STATE.inversores_excluidos || []);
          if (el.checked) excl.delete(nome); else excl.add(nome);
          window.__STATE.inversores_excluidos = Array.from(excl);
          redraw();
          // atualizar status sem repintar aba inteira
          var st = document.getElementById('dyn-inv-status');
          if (st) st.textContent = (window.__RAW_DATA.inverters.length - excl.size) + ' inversores ativos · ' + excl.size + ' excluidos';
        });
      });
    }
    else if (name === 'tarifa') {
      document.querySelectorAll('[data-input]').forEach(function(el){
        el.addEventListener('input', function(){
          var k = el.getAttribute('data-input');
          var v = parseFloat(el.value) || 0;
          if (k === 'tarifa') window.__STATE.tarifa_rs_kwh = v;
          if (k === 'poa') window.__STATE.poa_kwh_m2 = v;
          redraw();
          // atualizar preview
          var kpis = calcularKPIs(window.__STATE);
          var prev = document.getElementById('dyn-tarifa-preview');
          if (prev) {
            prev.innerHTML = 'Receita estimada: <b>' + (kpis.receita ? fmtRS(kpis.receita) : '---') + '</b><br/>' +
                             'PR Real: <b>' + (kpis.pr_real ? Number(kpis.pr_real).toFixed(4).replace('.',',') : '---') + '</b> · Variação POA vs PVsyst: <b>' + (kpis.poa ? fmtP(kpis.var_poa) : '---') + '</b>';
          }
        });
      });
    }
    else if (name === 'ocorrencias') {
      document.querySelectorAll('[data-pid][data-field]').forEach(function(el){
        el.addEventListener('change', function(){
          var pid = el.getAttribute('data-pid');
          var field = el.getAttribute('data-field');
          var v = el.value;
          window.__STATE.paradas_editadas = window.__STATE.paradas_editadas || {};
          window.__STATE.paradas_editadas[pid] = window.__STATE.paradas_editadas[pid] || {};
          window.__STATE.paradas_editadas[pid][field] = v;
          redraw();
        });
      });
    }
    else if (name === 'param') {
      document.querySelectorAll('[data-vocab]').forEach(function(el){
        el.addEventListener('change', function(){
          var grp = el.getAttribute('data-vocab');
          var idx = parseInt(el.getAttribute('data-idx'));
          var key = el.getAttribute('data-key');
          var v = el.value;
          var arr = grp === 'causa' ? window.__STATE.vocab.causas : window.__STATE.vocab.responsaveis;
          if (!arr[idx]) return;
          // Se mudou label, ATUALIZA as paradas (causa/resp) que usavam o label antigo
          if (key === 'label') {
            var antigo = arr[idx].label;
            var novo = v;
            if (antigo !== novo) {
              window.__RAW_DATA.paradas.forEach(function(p){
                var edit = (window.__STATE.paradas_editadas || {})[p.id] || {};
                var atual_c = edit.causa !== undefined ? edit.causa : p.causa;
                var atual_r = edit.responsavel !== undefined ? edit.responsavel : p.responsavel;
                if (grp === 'causa' && atual_c === antigo) {
                  window.__STATE.paradas_editadas = window.__STATE.paradas_editadas || {};
                  window.__STATE.paradas_editadas[p.id] = window.__STATE.paradas_editadas[p.id] || {};
                  window.__STATE.paradas_editadas[p.id].causa = novo;
                }
                if (grp === 'resp' && atual_r === antigo) {
                  window.__STATE.paradas_editadas = window.__STATE.paradas_editadas || {};
                  window.__STATE.paradas_editadas[p.id] = window.__STATE.paradas_editadas[p.id] || {};
                  window.__STATE.paradas_editadas[p.id].responsavel = novo;
                }
              });
            }
          }
          arr[idx][key] = v;
          redraw();
        });
      });
      document.querySelectorAll('[data-vocab-del]').forEach(function(el){
        el.addEventListener('click', function(){
          if (el.disabled) return;
          var grp = el.getAttribute('data-vocab-del');
          var idx = parseInt(el.getAttribute('data-idx'));
          var arr = grp === 'causa' ? window.__STATE.vocab.causas : window.__STATE.vocab.responsaveis;
          arr.splice(idx, 1);
          UI.tab('param');
          redraw();
        });
      });
      document.querySelectorAll('[data-vocab-add]').forEach(function(el){
        el.addEventListener('click', function(){
          var grp = el.getAttribute('data-vocab-add');
          if (grp === 'causa') {
            var label = prompt('Nome da nova causa:');
            if (!label) return;
            window.__STATE.vocab.causas.push({id: uniqId('cs'), label: label});
          } else {
            var label = prompt('Nome do novo responsavel:');
            if (!label) return;
            window.__STATE.vocab.responsaveis.push({id: uniqId('rp'), label: label, categoria: 'outro', cor: '#888888'});
          }
          UI.tab('param');
          redraw();
        });
      });
    }
  }

  // ─── Bootstrap ────────────────────────────────────────────────────
  function bootstrap() {
    window.__INITIAL_STATE = JSON.parse(JSON.stringify(window.__STATE));
    // Restaura estado persistido se existir
    var persisted = document.getElementById('__state_persisted__');
    if (persisted) {
      try {
        window.__STATE = JSON.parse(persisted.textContent);
      } catch(e) {}
    }
    // Aguarda Chart.js terminar de criar instances
    setTimeout(function(){
      // Captura referencias aos charts via Chart.getChart
      ['ch_inv','ch_dev','ch_disp','ch_poa','ch_donut','ch_hora5','ch_heat5'].forEach(function(id){
        var c = (typeof Chart !== 'undefined' && Chart.getChart) ? Chart.getChart(id) : null;
        if (c) window.__CHARTS[id] = c;
      });
      // Se ha estado persistido, aplica
      var hasEdits = (window.__STATE.inversores_excluidos.length > 0) ||
                     (window.__STATE.tarifa_rs_kwh !== window.__INITIAL_STATE.tarifa_rs_kwh) ||
                     (window.__STATE.poa_kwh_m2 !== window.__INITIAL_STATE.poa_kwh_m2) ||
                     (Object.keys(window.__STATE.paradas_editadas || {}).length > 0);
      if (hasEdits) {
        redraw();
      }
    }, 2500);
  }

  // Espera load
  if (document.readyState === 'complete') bootstrap();
  else window.addEventListener('load', bootstrap);

  // Expose redraw/setState para debug
  window.__redraw = redraw;
  window.__setState = setState;
})();
"""


def render_dinamico_css():
    return CSS

def render_dinamico_drawer_html():
    return DRAWER_HTML

def render_dinamico_js():
    return JS_BUNDLE
