-- ============================================================
-- IMPERA Dashboard — Star Schema
-- PostgreSQL 15+
-- ============================================================

-- Dimensões
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_tempo (
    data DATE PRIMARY KEY,
    dia_semana SMALLINT,       -- 0=seg, 6=dom
    dia_semana_nome VARCHAR(10),
    semana_num SMALLINT,
    mes SMALLINT,
    mes_nome VARCHAR(15),
    ano SMALLINT,
    trimestre SMALLINT
);

CREATE TABLE IF NOT EXISTS dim_nicho (
    nicho_id VARCHAR(4) PRIMARY KEY,  -- DA, DB, ED, EM, ME, MM, NE, PT, ZB
    nome VARCHAR(50),
    mercado VARCHAR(5) DEFAULT 'BR'   -- BR ou EUA
);

CREATE TABLE IF NOT EXISTS dim_oferta (
    oferta_id SERIAL PRIMARY KEY,
    codigo VARCHAR(20),         -- OF01, OF03, VSL 01, etc
    nome VARCHAR(100),
    nicho_id VARCHAR(4) REFERENCES dim_nicho(nicho_id),
    tipo VARCHAR(10)            -- front, BO, upsell
);

CREATE TABLE IF NOT EXISTS dim_fonte (
    fonte_id VARCHAR(4) PRIMARY KEY,  -- FB, KW, TT, YT, TB, NTV
    nome VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS dim_gestor (
    gestor_id SERIAL PRIMARY KEY,
    nome VARCHAR(50),
    fonte_principal VARCHAR(4) REFERENCES dim_fonte(fonte_id)
);

CREATE TABLE IF NOT EXISTS dim_pessoa (
    pessoa_id SERIAL PRIMARY KEY,
    nome VARCHAR(50),
    role VARCHAR(10),           -- copy, editor
    alias VARCHAR(50),          -- REAPER -> CASSIO
    clickup_id BIGINT
);

CREATE TABLE IF NOT EXISTS dim_criativo (
    criativo_id SERIAL PRIMARY KEY,
    nome_completo VARCHAR(200),
    base_id VARCHAR(30),        -- AD76, C71, CE08
    versao VARCHAR(10),         -- V1, V10, NULL
    copywriter_id INTEGER REFERENCES dim_pessoa(pessoa_id),
    editor_id INTEGER REFERENCES dim_pessoa(pessoa_id),
    nicho_id VARCHAR(4) REFERENCES dim_nicho(nicho_id),
    oferta_id INTEGER REFERENCES dim_oferta(oferta_id),
    tipo VARCHAR(10),           -- video, img
    eh_variacao BOOLEAN DEFAULT FALSE,
    criativo_pai_id INTEGER REFERENCES dim_criativo(criativo_id),
    clickup_task_id VARCHAR(20),
    data_criacao DATE,
    UNIQUE(base_id, versao, nicho_id)
);

-- Fatos
-- ============================================================

CREATE TABLE IF NOT EXISTS fato_performance (
    id SERIAL PRIMARY KEY,
    data DATE REFERENCES dim_tempo(data),
    nicho_id VARCHAR(4) REFERENCES dim_nicho(nicho_id),
    oferta_id INTEGER REFERENCES dim_oferta(oferta_id),
    gestor_id INTEGER REFERENCES dim_gestor(gestor_id),
    fonte_id VARCHAR(4) REFERENCES dim_fonte(fonte_id),
    criativo_id INTEGER REFERENCES dim_criativo(criativo_id),
    -- Métricas financeiras
    cost NUMERIC(12,2) DEFAULT 0,
    revenue_front NUMERIC(12,2) DEFAULT 0,    -- revenuetype2 + revenuetype3
    revenue_total NUMERIC(12,2) DEFAULT 0,    -- revenue (total)
    vendas_total INTEGER DEFAULT 0,            -- convtype1
    vendas_cc INTEGER DEFAULT 0,               -- convtype4
    mc_br NUMERIC(12,2) DEFAULT 0,            -- (front*0.70)-(cost*1.10)
    roas_front NUMERIC(6,2) DEFAULT 0,
    roas_total NUMERIC(6,2) DEFAULT 0,
    cpa NUMERIC(10,2) DEFAULT 0,
    -- Métricas de tráfego
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    lp_clicks INTEGER DEFAULT 0,
    -- Metadata
    campaign_name VARCHAR(300),
    adgroup_name VARCHAR(200),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(data, gestor_id, fonte_id, criativo_id, campaign_name)
);

CREATE TABLE IF NOT EXISTS fato_producao (
    id SERIAL PRIMARY KEY,
    clickup_task_id VARCHAR(20) UNIQUE,
    nome_tarefa VARCHAR(300),
    nicho_id VARCHAR(4) REFERENCES dim_nicho(nicho_id),
    oferta_id INTEGER REFERENCES dim_oferta(oferta_id),
    copywriter_id INTEGER REFERENCES dim_pessoa(pessoa_id),
    editor_id INTEGER REFERENCES dim_pessoa(pessoa_id),
    tipo VARCHAR(15),            -- vid_novo, vid_otim, img_novo, img_otim, lead, microlead
    qtd_criativos INTEGER DEFAULT 1,
    eh_ripagem BOOLEAN DEFAULT FALSE,
    status_atual VARCHAR(50),
    data_criacao TIMESTAMP,
    data_done TIMESTAMP,
    sla_dias INTEGER,
    sla_cumprido BOOLEAN,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fato_lifecycle (
    id SERIAL PRIMARY KEY,
    criativo_id INTEGER REFERENCES dim_criativo(criativo_id),
    clickup_task_id VARCHAR(20),
    data_evento DATE REFERENCES dim_tempo(data),
    status_de VARCHAR(50),
    status_para VARCHAR(50),
    dias_no_status INTEGER,
    -- Classificação no momento
    classificacao VARCHAR(30),   -- em_teste, pre_validado, validado, top, em_risco, negativo
    vendas_acumuladas INTEGER,
    roas_momento NUMERIC(6,2),
    cpa_momento NUMERIC(10,2),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_perf_data ON fato_performance(data);
CREATE INDEX IF NOT EXISTS idx_perf_nicho ON fato_performance(nicho_id);
CREATE INDEX IF NOT EXISTS idx_perf_gestor ON fato_performance(gestor_id);
CREATE INDEX IF NOT EXISTS idx_perf_criativo ON fato_performance(criativo_id);
CREATE INDEX IF NOT EXISTS idx_perf_data_nicho ON fato_performance(data, nicho_id);
CREATE INDEX IF NOT EXISTS idx_prod_status ON fato_producao(status_atual);
CREATE INDEX IF NOT EXISTS idx_prod_copy ON fato_producao(copywriter_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_criativo ON fato_lifecycle(criativo_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_data ON fato_lifecycle(data_evento);

-- Views materializadas (atualizar no ETL)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_performance_diaria AS
SELECT
    p.data,
    t.dia_semana_nome,
    t.semana_num,
    n.nome AS nicho,
    g.nome AS gestor,
    f.nome AS fonte,
    SUM(p.cost) AS cost,
    SUM(p.revenue_front) AS revenue_front,
    SUM(p.revenue_total) AS revenue_total,
    SUM(p.vendas_total) AS vendas_total,
    SUM(p.vendas_cc) AS vendas_cc,
    SUM(p.mc_br) AS mc_br,
    CASE WHEN SUM(p.cost) > 0 THEN SUM(p.revenue_front) / SUM(p.cost) ELSE 0 END AS roas_front,
    CASE WHEN SUM(p.vendas_total) > 0 THEN SUM(p.cost) / SUM(p.vendas_total) ELSE 0 END AS cpa
FROM fato_performance p
JOIN dim_tempo t ON p.data = t.data
LEFT JOIN dim_nicho n ON p.nicho_id = n.nicho_id
LEFT JOIN dim_gestor g ON p.gestor_id = g.gestor_id
LEFT JOIN dim_fonte f ON p.fonte_id = f.fonte_id
GROUP BY p.data, t.dia_semana_nome, t.semana_num, n.nome, g.nome, f.nome;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_producao_semanal AS
SELECT
    DATE_TRUNC('week', fp.data_done) AS semana,
    n.nome AS nicho,
    pc.nome AS copywriter,
    pe.nome AS editor,
    fp.tipo,
    COUNT(*) AS tarefas,
    SUM(fp.qtd_criativos) AS criativos_total
FROM fato_producao fp
LEFT JOIN dim_nicho n ON fp.nicho_id = n.nicho_id
LEFT JOIN dim_pessoa pc ON fp.copywriter_id = pc.pessoa_id
LEFT JOIN dim_pessoa pe ON fp.editor_id = pe.pessoa_id
WHERE fp.data_done IS NOT NULL
GROUP BY semana, n.nome, pc.nome, pe.nome, fp.tipo;

-- Seed dados estáticos
-- ============================================================

INSERT INTO dim_nicho (nicho_id, nome, mercado) VALUES
    ('DA', 'Diabetes', 'BR'),
    ('DB', 'Diabetes', 'BR'),
    ('ED', 'Emagrecimento/Disfunção', 'BR'),
    ('EM', 'Emagrecimento', 'BR'),
    ('ME', 'Memória', 'BR'),
    ('MM', 'Massa Muscular', 'BR'),
    ('NE', 'Nervo/Dor', 'BR'),
    ('PT', 'Próstata', 'BR'),
    ('ZB', 'Zumbido', 'BR')
ON CONFLICT (nicho_id) DO NOTHING;

INSERT INTO dim_fonte (fonte_id, nome) VALUES
    ('FB', 'Facebook'),
    ('KW', 'Kwai'),
    ('TT', 'TikTok'),
    ('YT', 'YouTube'),
    ('TB', 'Taboola'),
    ('NTV', 'Nativo')
ON CONFLICT (fonte_id) DO NOTHING;

-- Preencher dim_tempo (2 anos: 2025-2027)
INSERT INTO dim_tempo (data, dia_semana, dia_semana_nome, semana_num, mes, mes_nome, ano, trimestre)
SELECT
    d::date,
    EXTRACT(DOW FROM d)::smallint,
    TO_CHAR(d, 'Dy'),
    EXTRACT(WEEK FROM d)::smallint,
    EXTRACT(MONTH FROM d)::smallint,
    TO_CHAR(d, 'Mon'),
    EXTRACT(YEAR FROM d)::smallint,
    EXTRACT(QUARTER FROM d)::smallint
FROM generate_series('2025-01-01'::date, '2027-12-31'::date, '1 day') AS d
ON CONFLICT (data) DO NOTHING;


-- ============================================================
-- Tabelas extras: Vturb, Lifecycle v2, Esteira, Health
-- ============================================================

-- Vturb VSL Analytics
CREATE TABLE IF NOT EXISTS fato_vturb (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(50),
    player_name VARCHAR(200),
    nicho_id VARCHAR(4) REFERENCES dim_nicho(nicho_id),
    views_unicas INTEGER DEFAULT 0,
    plays_unicos INTEGER DEFAULT 0,
    play_rate NUMERIC(5,2) DEFAULT 0,
    engajamento NUMERIC(5,2) DEFAULT 0,
    duracao_segundos INTEGER DEFAULT 0,
    data_coleta DATE DEFAULT CURRENT_DATE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_id, data_coleta)
);

-- Creative Lifecycle v2 (classificador state)
CREATE TABLE IF NOT EXISTS fato_lifecycle_v2 (
    id SERIAL PRIMARY KEY,
    clickup_task_id VARCHAR(20),
    criativo_nome VARCHAR(200),
    nicho_id VARCHAR(4),
    classificacao VARCHAR(30),
    vendas_acumuladas INTEGER DEFAULT 0,
    roas_momento NUMERIC(6,2) DEFAULT 0,
    cpa_momento NUMERIC(10,2) DEFAULT 0,
    custo_acumulado NUMERIC(12,2) DEFAULT 0,
    data_classificacao TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Esteira Pipeline SLA
CREATE TABLE IF NOT EXISTS fato_esteira (
    id SERIAL PRIMARY KEY,
    clickup_task_id VARCHAR(20),
    nome_tarefa VARCHAR(300),
    status_atual VARCHAR(50),
    responsavel VARCHAR(50),
    tipo VARCHAR(20),
    data_entrada_status TIMESTAMP,
    horas_no_status NUMERIC(8,1) DEFAULT 0,
    sla_limite_horas NUMERIC(8,1),
    sla_estourado BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clickup_task_id)
);

-- System Health
CREATE TABLE IF NOT EXISTS fato_health (
    id SERIAL PRIMARY KEY,
    script_name VARCHAR(100),
    status VARCHAR(20),
    last_run TIMESTAMP,
    last_error TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(script_name)
);

CREATE INDEX IF NOT EXISTS idx_vturb_nicho ON fato_vturb(nicho_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_v2_class ON fato_lifecycle_v2(classificacao);
CREATE INDEX IF NOT EXISTS idx_esteira_status ON fato_esteira(status_atual);
