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
    // dias_com_dado: count de linhas no df (Python groupby + count NAO filtra v>0)
    // Critico para disp_ger casar com Python ao 100%.
    var energia_real = 0;
    var dias_set = new Set();
    var energia_por_inv = {};
    var dias_com_dado_por_inv = {};
    inverters.forEach(function(inv){
      var soma = 0;
      var keys = Object.keys(inv.energias_diarias);
      keys.forEach(function(d){
        soma += inv.energias_diarias[d];
        dias_set.add(d);  // dias_com_dado global = nunique() das datas (todas)
      });
      energia_por_inv[inv.nome] = soma;
      dias_com_dado_por_inv[inv.nome] = keys.length;  // count() = todas as linhas
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
    // disp_ger_cobertura: replica exatamente o Python calc_kpis (tier 2 usa esse):
    //   df_inv["disp_ger_pct"] = (dias/dias_mes*100).round(1)  <- por inversor, round 1 casa
    //   disp_ger = float(df_inv["disp_ger_pct"].mean())         <- mean(), sem round
    var disp_ger_cobertura = 0;
    if (n_inv > 0) {
      var soma_disp = 0;
      inverters.forEach(function(inv){
        var pct = (dias_com_dado_por_inv[inv.nome] || 0) / dias_mes * 100;
        soma_disp += round(pct, 1);
      });
      disp_ger_cobertura = soma_disp / n_inv;
    }
    // disp_ger exibido: tier 1 usa pct_geracao (calculado abaixo), tier 2 usa cobertura
    // Calculado depois do bloco 5-estados.
    var receita = energia_real * tarifa;

    // ── 5 estados ──
    // pct_geracao do tier 1 vem de classificacao 5min do ISC. Recalcular fielmente
    // no client exigiria embedar todos os intervalos. Estrategia:
    //
    // 1. Sem exclusoes: usa o valor original do Python (match exato)
    // 2. Exclusao de inversor: subtrai as PERDAS DAQUELE INVERSOR especifico
    //    - h_om do inv X = soma das paradas O&M do inv X
    //    - novo denominador = (n_inv - 1) * dias_mes * HORAS_SOLARES_POR_INV
    //    - pct_om_novo = (h_om_total_orig - h_om_inv_X) / novo_denominador * 100
    //
    // Esta abordagem reflete fielmente "tira as perdas daquele inversor",
    // ao contrario de uma reducao proporcional via fator energia.
    var orig = raw.kpis_originais || {};
    var HORAS_SOLARES_POR_DIA = 11.5;  // 06:30-18:00, mesmo intervalo do Python isc_5estados_mensal
    var horas_solares_por_inv = dias_mes * HORAS_SOLARES_POR_DIA;
    // n_inv_orig = total no dataset (inclui excluidos do calculo, mas nao fantasmas filtrados pelo ETL)
    var n_inv_orig = window.__RAW_DATA.inverters.length;
    var H_TOTAL_ORIG = n_inv_orig * horas_solares_por_inv;

    // Calcula horas off por inversor por categoria (apenas paradas FILTRADAS — ja respeitam exclusao)
    var h_por_inv_categoria = {};  // {nome_inv: {concessionaria, om, outro}}
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
      if (!h_por_inv_categoria[p.inversor]) {
        h_por_inv_categoria[p.inversor] = { concessionaria: 0, om: 0, outro: 0, all: 0 };
      }
      h_por_inv_categoria[p.inversor].all += h;
      if (cat) h_por_inv_categoria[p.inversor][cat] += h;
    });

    // ── pct_X usando subtracao das horas off dos inversores excluidos ──
    // Calcula h off dos EXCLUIDOS (com base na lista original de paradas, nao filtradas)
    var excl = new Set(state.inversores_excluidos || []);
    var h_conc_excl = 0, h_om_excl = 0, h_outro_excl = 0;
    raw.paradas.forEach(function(p){
      if (!excl.has(p.inversor)) return;
      // Aplica edicoes de causa/responsavel tambem nas paradas dos excluidos
      var edit = (state.paradas_editadas || {})[p.id];
      var pp = edit ? Object.assign({}, p, edit) : p;
      var cat = categoriaDoResponsavel(pp.responsavel, vocab);
      var h = pp.duracao_h || 0;
      if (cat === "concessionaria") h_conc_excl += h;
      else if (cat === "om") h_om_excl += h;
      else if (cat === "outro") h_outro_excl += h;
    });

    // Horas off totais ORIGINAIS (sabido via pct_X * H_TOTAL_ORIG / 100)
    var h_conc_orig  = (orig.pct_conc || 0) * H_TOTAL_ORIG / 100;
    var h_om_orig    = (orig.pct_om   || 0) * H_TOTAL_ORIG / 100;
    var h_irr_orig   = (orig.pct_irr  || 0) * H_TOTAL_ORIG / 100;
    var h_ger_orig   = (orig.pct_ger_pure || 0) * H_TOTAL_ORIG / 100;

    // Novo denominador (apenas inversores nao excluidos)
    var n_excl = excl.size;
    var n_inv_atual = Math.max(0, n_inv_orig - n_excl);
    var H_TOTAL_NOVO = n_inv_atual * horas_solares_por_inv;

    // Calcular novas horas absolutas (subtraindo o que o excluido contribuia)
    // Para conc/om/outro: usa as horas de paradas dos excluidos
    var h_conc_novo  = Math.max(0, h_conc_orig - h_conc_excl);
    var h_om_novo    = Math.max(0, h_om_orig   - h_om_excl);
    var h_outro_novo = Math.max(0, 0 - h_outro_excl);  // outro nao existe no orig (Python so tem conc/om/irr)
    // Sem h_outro_excl conhecido no original (Python so classificava conc/om), comeca em 0
    if (h_outro_novo < 0) h_outro_novo = 0;
    h_outro_novo = h_outro_excl >= 0 ? 0 : h_outro_novo;  // outro nao tem origem no Python — comeca 0

    // irr: nao da pra atribuir a inversores individuais (vem do classificador 5min).
    // Aproximacao: assume distribuido uniformemente (cada inv contribui 1/n_orig).
    var fracao_excluida = n_inv_orig > 0 ? (n_excl / n_inv_orig) : 0;
    var h_irr_novo   = h_irr_orig * (1 - fracao_excluida);

    // Percentuais novos — conc/om/outro/irr usam horas subtraidas explicitamente
    var pct_conc  = H_TOTAL_NOVO > 0 ? round(h_conc_novo  / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_om    = H_TOTAL_NOVO > 0 ? round(h_om_novo    / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_outro = H_TOTAL_NOVO > 0 ? round(h_outro_novo / H_TOTAL_NOVO * 100, 2) : 0;
    var pct_irr   = H_TOTAL_NOVO > 0 ? round(h_irr_novo   / H_TOTAL_NOVO * 100, 2) : 0;
    // pct_ger_pure = complemento (garante soma = 100% e respeita "tira as perdas do inv")
    var pct_ger_pure = round(Math.max(0, 100 - pct_irr - pct_conc - pct_om - pct_outro), 2);
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
    // disp_ger: tier 1 usa pct_geracao (recalculado), tier 2 usa cobertura (df_inv mean)
    var tier = orig.tier || 2;
    var disp_ger = (tier === 1) ? pct_geracao : disp_ger_cobertura;
    return {
      // KPIs principais
      energia_real: round(energia_real, 2),
      ee: ee, at: at,
      pr_real: round(pr_real, 4), pr_e: pr_e, esp_kwp: round(esp_kwp, 2),
      poa: poa, var_poa: var_poa, glob_inc: glob_inc,
      dias_com_dado: dias_com_dado, cob_pct: cob_pct,
      disp_ger: disp_ger,
      disp_ger_cobertura: disp_ger_cobertura,
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
