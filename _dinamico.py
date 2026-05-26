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
    // ATENCAO: pct_geracao do tier 1 vem de classificacao 5min do ISC (~10k intervalos).
    // Recalcular fielmente no client exigiria embedar todos os intervalos no HTML.
    // Estrategia: usar valores ORIGINAIS do Python como baseline.
    // - Edicao de causa/responsavel afeta apenas tabela/histograma de horas por causa
    //   (pct_geracao NAO muda — o tempo em estado GER nao depende de como classificamos
    //    a causa de uma parada).
    // - Exclusao de inversor: ajusta pct_geracao proporcionalmente pela energia.
    var orig = raw.kpis_originais || {};
    var energia_orig = 0;
    window.__RAW_DATA.inverters.forEach(function(inv){
      Object.keys(inv.energias_diarias).forEach(function(d){
        energia_orig += inv.energias_diarias[d];
      });
    });
    // Fator de ajuste por exclusao de inversor
    var fator_inv = energia_orig > 0 ? (energia_real / energia_orig) : 1;
    // pct_geracao ajustado pela exclusao (proporcional)
    // Sem exclusoes: fator_inv = 1, pct_geracao = original (match exato)
    var pct_geracao = round((orig.pct_ger_pure || 0) + (orig.pct_irr || 0), 2);
    var pct_ger_pure = round((orig.pct_ger_pure || 0) * fator_inv +
                              ((orig.pct_ger_pure || 0) * (1 - fator_inv)), 2);
    // Simplificacao: quando NAO ha exclusao, mantem original; quando ha, reduz proporcional
    if (fator_inv < 0.9999) {
      // Reduz disp em proporcional a fracao de energia perdida
      pct_geracao = round(((orig.pct_ger_pure || 0) + (orig.pct_irr || 0)) * fator_inv +
                          (100 - 100*fator_inv), 2);
      // 100*(1-fator_inv) eh adicionado ao "outro" (perda por exclusao)
    }
    var pct_irr   = round(orig.pct_irr || 0, 2);
    var pct_conc  = round((orig.pct_conc || 0) * fator_inv, 2);
    var pct_om    = round((orig.pct_om || 0) * fator_inv, 2);
    var pct_outro = round(Math.max(0, 100 - pct_geracao - pct_conc - pct_om), 2);
    pct_ger_pure = round(pct_geracao - pct_irr, 2);

    // Contagem de paradas por categoria (afeta tabela/histograma, NAO o donut principal)
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
