-- ============================================================
-- QUERIES DASHBOARD IMPERA — Metabase
-- Copiar cada query como "New Question > Native Query"
-- ============================================================

-- ============================================================
-- PÁGINA 1: EXECUTIVE SUMMARY
-- ============================================================

-- [CARD] Faturamento Front (últimos 7 dias)
SELECT ROUND(SUM(revenue_front)::numeric, 0) AS faturamento_front
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [CARD] MC BR (últimos 7 dias)
SELECT ROUND(SUM(mc_br)::numeric, 0) AS mc_br
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [CARD] ROAS Front Médio (últimos 7 dias)
SELECT ROUND((SUM(revenue_front) / NULLIF(SUM(cost), 0))::numeric, 2) AS roas_front
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [CARD] Vendas Totais (últimos 7 dias)
SELECT SUM(vendas_total) AS vendas
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [CARD] CPA Médio (últimos 7 dias)
SELECT ROUND((SUM(cost) / NULLIF(SUM(vendas_total), 0))::numeric, 2) AS cpa
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [CARD] Investimento Total (últimos 7 dias)
SELECT ROUND(SUM(cost)::numeric, 0) AS investimento
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days';

-- [GRÁFICO LINHA] Tendência 30 dias — Faturamento diário
SELECT
    data,
    ROUND(SUM(revenue_front)::numeric, 0) AS faturamento_front,
    ROUND(SUM(cost)::numeric, 0) AS investimento,
    ROUND(SUM(mc_br)::numeric, 0) AS mc_br
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY data
ORDER BY data;

-- [TABELA] Ranking Nichos por Faturamento
SELECT
    n.nome AS nicho,
    ROUND(SUM(p.revenue_front)::numeric, 0) AS faturamento,
    ROUND(SUM(p.cost)::numeric, 0) AS investimento,
    ROUND(SUM(p.mc_br)::numeric, 0) AS mc_br,
    ROUND((SUM(p.revenue_front) / NULLIF(SUM(p.cost), 0))::numeric, 2) AS roas,
    SUM(p.vendas_total) AS vendas,
    ROUND((SUM(p.cost) / NULLIF(SUM(p.vendas_total), 0))::numeric, 2) AS cpa
FROM fato_performance p
JOIN dim_nicho n ON p.nicho_id = n.nicho_id
WHERE p.data >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY n.nome
ORDER BY SUM(p.revenue_front) DESC;


-- ============================================================
-- PÁGINA 2: GESTORES
-- ============================================================

-- [TABELA] Ranking Gestores por Faturamento
SELECT
    g.nome AS gestor,
    ROUND(SUM(p.revenue_front)::numeric, 0) AS faturamento,
    ROUND(SUM(p.cost)::numeric, 0) AS investimento,
    ROUND(SUM(p.mc_br)::numeric, 0) AS mc_br,
    ROUND((SUM(p.revenue_front) / NULLIF(SUM(p.cost), 0))::numeric, 2) AS roas,
    SUM(p.vendas_total) AS vendas,
    COUNT(DISTINCT p.campaign_name) AS campanhas
FROM fato_performance p
JOIN dim_gestor g ON p.gestor_id = g.gestor_id
WHERE p.data >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY g.nome
ORDER BY SUM(p.revenue_front) DESC;

-- [GRÁFICO BARRAS] Comparativo Semana Atual vs Anterior (por gestor)
SELECT
    g.nome AS gestor,
    ROUND(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '7 days'
              THEN p.revenue_front ELSE 0 END)::numeric, 0) AS semana_atual,
    ROUND(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '14 days'
                    AND p.data < CURRENT_DATE - INTERVAL '7 days'
              THEN p.revenue_front ELSE 0 END)::numeric, 0) AS semana_anterior
FROM fato_performance p
JOIN dim_gestor g ON p.gestor_id = g.gestor_id
WHERE p.data >= CURRENT_DATE - INTERVAL '14 days'
GROUP BY g.nome
ORDER BY SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '7 days'
             THEN p.revenue_front ELSE 0 END) DESC;

-- [GRÁFICO] Breakdown por Fonte
SELECT
    f.nome AS fonte,
    ROUND(SUM(p.revenue_front)::numeric, 0) AS faturamento,
    ROUND(SUM(p.cost)::numeric, 0) AS investimento,
    ROUND((SUM(p.revenue_front) / NULLIF(SUM(p.cost), 0))::numeric, 2) AS roas
FROM fato_performance p
JOIN dim_fonte f ON p.fonte_id = f.fonte_id
WHERE p.data >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY f.nome
ORDER BY SUM(p.revenue_front) DESC;


-- ============================================================
-- PÁGINA 3: NICHOS & OFERTAS
-- ============================================================

-- [TREEMAP/PIE] Distribuição de Faturamento por Nicho
SELECT
    n.nome AS nicho,
    ROUND(SUM(p.revenue_front)::numeric, 0) AS faturamento,
    ROUND(100.0 * SUM(p.revenue_front) / NULLIF(SUM(SUM(p.revenue_front)) OVER(), 0), 1) AS pct
FROM fato_performance p
JOIN dim_nicho n ON p.nicho_id = n.nicho_id
WHERE p.data >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY n.nome
ORDER BY SUM(p.revenue_front) DESC;

-- [GRÁFICO LINHA] Evolução por Nicho (30 dias)
SELECT
    p.data,
    n.nome AS nicho,
    ROUND(SUM(p.revenue_front)::numeric, 0) AS faturamento
FROM fato_performance p
JOIN dim_nicho n ON p.nicho_id = n.nicho_id
WHERE p.data >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.data, n.nome
ORDER BY p.data, n.nome;

-- [TABELA] Saturação (custo subindo, ROAS caindo — alerta escala)
WITH semanas AS (
    SELECT
        n.nome AS nicho,
        ROUND(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '7 days'
                  THEN p.cost ELSE 0 END)::numeric, 0) AS cost_atual,
        ROUND(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '14 days'
                        AND p.data < CURRENT_DATE - INTERVAL '7 days'
                  THEN p.cost ELSE 0 END)::numeric, 0) AS cost_anterior,
        ROUND((SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '7 days'
                   THEN p.revenue_front ELSE 0 END) /
               NULLIF(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '7 days'
                          THEN p.cost ELSE 0 END), 0))::numeric, 2) AS roas_atual,
        ROUND((SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '14 days'
                        AND p.data < CURRENT_DATE - INTERVAL '7 days'
                   THEN p.revenue_front ELSE 0 END) /
               NULLIF(SUM(CASE WHEN p.data >= CURRENT_DATE - INTERVAL '14 days'
                                AND p.data < CURRENT_DATE - INTERVAL '7 days'
                          THEN p.cost ELSE 0 END), 0))::numeric, 2) AS roas_anterior
    FROM fato_performance p
    JOIN dim_nicho n ON p.nicho_id = n.nicho_id
    WHERE p.data >= CURRENT_DATE - INTERVAL '14 days'
    GROUP BY n.nome
)
SELECT
    nicho,
    cost_atual,
    cost_anterior,
    ROUND(((cost_atual - cost_anterior)::numeric / NULLIF(cost_anterior, 0)) * 100, 1) AS var_cost_pct,
    roas_atual,
    roas_anterior,
    ROUND(((roas_atual - roas_anterior)::numeric / NULLIF(roas_anterior, 0)) * 100, 1) AS var_roas_pct
FROM semanas
WHERE cost_atual > 0
ORDER BY cost_atual DESC;


-- ============================================================
-- PÁGINA 4: CRIATIVOS / LIFECYCLE
-- ============================================================

-- [FUNNEL] Pipeline de Status (Tráfego)
SELECT
    status_atual,
    COUNT(*) AS tarefas
FROM fato_producao
WHERE status_atual NOT IN ('arquivo morto')
GROUP BY status_atual
ORDER BY COUNT(*) DESC;

-- [CARD] Taxa de Validação (criativos validados / total testados)
-- Nota: requer fato_lifecycle populado. Placeholder:
SELECT
    COUNT(CASE WHEN status_atual IN ('validado', 'escala') THEN 1 END) AS validados,
    COUNT(CASE WHEN status_atual NOT IN ('backlog copy', 'arquivo morto') THEN 1 END) AS total_testados,
    ROUND(100.0 * COUNT(CASE WHEN status_atual IN ('validado', 'escala') THEN 1 END) /
          NULLIF(COUNT(CASE WHEN status_atual NOT IN ('backlog copy', 'arquivo morto') THEN 1 END), 0), 1) AS taxa_validacao_pct
FROM fato_producao;

-- [TABELA] Top 10 Criativos por Faturamento
SELECT
    adgroup_name AS criativo,
    campaign_name,
    ROUND(SUM(revenue_front)::numeric, 0) AS faturamento,
    ROUND(SUM(cost)::numeric, 0) AS investimento,
    ROUND((SUM(revenue_front) / NULLIF(SUM(cost), 0))::numeric, 2) AS roas,
    SUM(vendas_total) AS vendas
FROM fato_performance
WHERE data >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY adgroup_name, campaign_name
ORDER BY SUM(revenue_front) DESC
LIMIT 10;


-- ============================================================
-- PÁGINA 5: PRODUÇÃO
-- ============================================================

-- [GRÁFICO BARRAS] Criativos por Copywriter (mês atual)
SELECT
    p.nome AS copywriter,
    SUM(fp.qtd_criativos) AS criativos,
    COUNT(*) AS tarefas
FROM fato_producao fp
JOIN dim_pessoa p ON fp.copywriter_id = p.pessoa_id
WHERE fp.data_criacao >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY p.nome
ORDER BY SUM(fp.qtd_criativos) DESC;

-- [GRÁFICO BARRAS] Criativos por Editor
SELECT
    p.nome AS editor,
    COUNT(*) AS tarefas
FROM fato_producao fp
JOIN dim_pessoa p ON fp.editor_id = p.pessoa_id
WHERE fp.data_done >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY p.nome
ORDER BY COUNT(*) DESC;

-- [GRÁFICO LINHA] Throughput Semanal (criativos concluídos por semana)
SELECT
    DATE_TRUNC('week', data_done)::date AS semana,
    SUM(qtd_criativos) AS criativos_entregues,
    COUNT(*) AS tarefas_concluidas
FROM fato_producao
WHERE data_done >= CURRENT_DATE - INTERVAL '90 days'
  AND data_done IS NOT NULL
GROUP BY DATE_TRUNC('week', data_done)
ORDER BY semana;

-- [TABELA] SLA por Tipo
SELECT
    tipo,
    COUNT(*) AS total,
    ROUND(AVG(sla_dias)::numeric, 1) AS media_dias,
    ROUND(100.0 * COUNT(CASE WHEN sla_cumprido THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS pct_no_prazo
FROM fato_producao
WHERE data_done IS NOT NULL AND sla_dias IS NOT NULL
GROUP BY tipo
ORDER BY COUNT(*) DESC;

-- [TABELA] Produção por Nicho
SELECT
    n.nome AS nicho,
    SUM(fp.qtd_criativos) AS criativos,
    COUNT(*) AS tarefas,
    SUM(CASE WHEN fp.eh_ripagem THEN fp.qtd_criativos ELSE 0 END) AS ripagens
FROM fato_producao fp
JOIN dim_nicho n ON fp.nicho_id = n.nicho_id
GROUP BY n.nome
ORDER BY SUM(fp.qtd_criativos) DESC;


-- ============================================================
-- PÁGINA 6: DRILL-THROUGH (Detalhe)
-- ============================================================

-- [TABELA] Campanhas Detalhadas (com filtros)
SELECT
    p.data,
    n.nome AS nicho,
    g.nome AS gestor,
    f.nome AS fonte,
    p.campaign_name,
    p.adgroup_name AS criativo,
    p.revenue_front AS faturamento,
    p.cost AS investimento,
    p.mc_br,
    p.roas_front AS roas,
    p.vendas_total AS vendas,
    p.cpa
FROM fato_performance p
LEFT JOIN dim_nicho n ON p.nicho_id = n.nicho_id
LEFT JOIN dim_gestor g ON p.gestor_id = g.gestor_id
LEFT JOIN dim_fonte f ON p.fonte_id = f.fonte_id
WHERE p.data >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY p.revenue_front DESC
LIMIT 100;
