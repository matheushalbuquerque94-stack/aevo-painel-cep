"""Codigo JavaScript injetado nos HTMLs para tornar o relatorio dinamico.
Mantemos aqui o JS gigante pra nao poluir o app.py."""

# ── Funcoes JS de calculo (espelham calc_kpis e kpis_5est do Python) ───────
JS_CALC = r"""
/* Funcoes de calculo do relatorio dinamico AEVO19.
 * Espelham calc_kpis (Python) operando sobre window.__RAW_DATA filtrado por STATE.
 */

(function(){
  'use strict';

  /** Retorna lista de inversores aplicando exclusoes do STATE. */
  function getInverters(state) {
    var excl = new Set(state.inversores_excluidos || []);
    return window.__RAW_DATA.inverters.filter(function(inv){
      return !excl.has(inv.nome);
    });
  }

  /** Retorna lista de paradas aplicando exclusoes + edicoes de causa/responsavel. */
  function getParadas(state) {
    var excl = new Set(state.inversores_excluidos || []);
    var edits = state.paradas_editadas || {};
    return window.__RAW_DATA.paradas
      .filter(function(p){ return !excl.has(p.inversor); })
      .map(function(p){
        var edit = edits[p.id];
        if (edit) {
          return Object.assign({}, p, edit);
        }
        return p;
      });
  }

  /** Mapeia label de responsavel -> categoria (concessionaria/om/outro). */
  function categoriaDoResponsavel(label, vocab) {
    if (!label) return null;
    var r = (vocab.responsaveis || []).find(function(x){ return x.label === label; });
    return r ? r.categoria : null;
  }

  /** Calcula KPIs principais e os 5 estados. */
  function calcularKPIs(state) {
    var inverters = getInverters(state);
    var paradas = getParadas(state);
    var raw = window.__RAW_DATA;
    var vocab = state.vocab || window.__VOCAB_DEFAULT;
    var kwp = raw.plant.kwp || 0;
    var dias_mes = raw.plant.dias_mes;
    var n_inv = inverters.length;

    // Energia real = soma de tudo
    var energia_real = 0;
    var dias_set = new Set();
    var energia_por_inv = {};
    var dias_com_dado_por_inv = {};
    inverters.forEach(function(inv){
      var soma = 0;
      var n_dias = 0;
      Object.keys(inv.energias_diarias).forEach(function(d){
        var v = inv.energias_diarias[d];
        soma += v;
        if (v > 0) { dias_set.add(d); n_dias++; }
      });
      energia_por_inv[inv.nome] = soma;
      dias_com_dado_por_inv[inv.nome] = n_dias;
      energia_real += soma;
    });

    // Energia diaria (soma de inversores filtrados)
    var energia_dia = {};
    inverters.forEach(function(inv){
      Object.keys(inv.energias_diarias).forEach(function(d){
        energia_dia[d] = (energia_dia[d] || 0) + inv.energias_diarias[d];
      });
    });

    // KPIs basicos
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
    // Disp ger: media de (dias_com_dado / dias_mes * 100) por inversor
    var disp_ger = 0;
    if (n_inv > 0) {
      var soma_disp = 0;
      inverters.forEach(function(inv){
        soma_disp += (dias_com_dado_por_inv[inv.nome] || 0) / dias_mes * 100;
      });
      disp_ger = round(soma_disp / n_inv, 1);
    }
    var receita = energia_real * tarifa;

    // 5 estados — atualizado a partir das paradas (com categorias do vocab)
    // pct_irr, pct_conc, pct_om, pct_outro: fracao de paradas de cada categoria
    // pct_ger_pure = 100 - irr - conc - om - outro
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
      if (p.causa) {
        horas_por_causa[p.causa] = (horas_por_causa[p.causa] || 0) + h;
      }
    });
    // Horas solares totais aproximadas: 30 dias × 11h × n_inv = 330 × n_inv
    // Mas como o calculo do Python usa intervalos discretos, aproximamos com:
    // pct_X = h_categoria / (horas_solares_totais) * 100
    var horas_solares_totais = dias_mes * 11 * Math.max(n_inv, 1);
    var pct_conc  = horas_solares_totais ? round(h_por_categoria.concessionaria / horas_solares_totais * 100, 2) : 0;
    var pct_om    = horas_solares_totais ? round(h_por_categoria.om / horas_solares_totais * 100, 2) : 0;
    var pct_outro = horas_solares_totais ? round(h_por_categoria.outro / horas_solares_totais * 100, 2) : 0;
    var pct_irr   = round(raw.kpis_originais.pct_irr || 0, 2);  // irr nao muda com edicao de paradas
    var pct_ger_pure = round(100 - pct_irr - pct_conc - pct_om - pct_outro, 2);
    var pct_geracao = round(pct_ger_pure + pct_irr, 2);

    // Tabela de inversores
    var df_inv = inverters.map(function(inv){
      var en = energia_por_inv[inv.nome] || 0;
      return {
        inversor: inv.nome,
        modelo: inv.modelo,
        energia_kwh: round(en, 2),
        pct: energia_real ? round(en / energia_real * 100, 1) : 0,
        esp_kwh_kwp: (kwp && n_inv) ? round(en / (kwp / n_inv), 2) : 0,
        dias_com_dado: dias_com_dado_por_inv[inv.nome] || 0,
        disp_ger_pct: dias_mes ? round((dias_com_dado_por_inv[inv.nome] || 0) / dias_mes * 100, 1) : 0,
      };
    });
    df_inv.sort(function(a, b){ return b.energia_kwh - a.energia_kwh; });

    var total_ev = paradas.length;
    return {
      // KPIs principais
      energia_real: round(energia_real, 2),
      ee: ee, at: at,
      pr_real: round(pr_real, 4), pr_e: pr_e, esp_kwp: round(esp_kwp, 2),
      poa: poa, var_poa: var_poa, glob_inc: glob_inc,
      dias_com_dado: dias_com_dado, cob_pct: cob_pct,
      disp_ger: disp_ger,
      receita: round(receita, 2),
      tarifa: tarifa,
      // 5 estados
      pct_geracao: pct_geracao, pct_ger_pure: pct_ger_pure,
      pct_irr: pct_irr, pct_conc: pct_conc, pct_om: pct_om, pct_outro: pct_outro,
      // Auxiliares
      n_inv: n_inv,
      total_ev: total_ev,
      total_h_off: round(total_h_off, 2),
      h_por_categoria: h_por_categoria,
      n_ev_categoria: n_ev_categoria,
      horas_por_causa: horas_por_causa,
      df_inv: df_inv,
      energia_dia: energia_dia,
      paradas: paradas,
    };
  }

  function round(v, d) {
    d = d || 0;
    var m = Math.pow(10, d);
    return Math.round(v * m) / m;
  }

  /* Expose */
  window.__CALC = {
    calcularKPIs: calcularKPIs,
    getInverters: getInverters,
    getParadas: getParadas,
    categoriaDoResponsavel: categoriaDoResponsavel,
  };
})();
"""


def render_dinamico_js():
    """Retorna o JS completo a ser injetado no HTML.
    Por enquanto so o modulo de calculo. Sera estendido nas proximas etapas
    (sistema reativo, drawer de edicao)."""
    return JS_CALC
