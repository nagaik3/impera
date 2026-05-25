-- ============================================================
-- IMPERA PRODUTOS NATURAIS — Data Lake (Star Schema)
-- DDL Completo: 3 Tabelas + 2 Views + Indices
-- Substitui: relatorio_redtrack_impera.py, rastreador_esteira.py,
--            detectar_criativos_orfaos.py (outputs estaticos)
--
-- GPDR - Iago Almeida, assistido por Claude
-- 12/Mai/2026
-- ============================================================

-- Schema dedicado para isolar do public
CREATE SCHEMA IF NOT EXISTS impera;

-- ============================================================
-- TABELA DIMENSAO: dim_criativos_clickup
-- Fonte da verdade de todas as tarefas/criativos do ClickUp.
-- Alimentada por: clickup_criar_tarefa.py, sync scripts
-- ============================================================
CREATE TABLE IF NOT EXISTS impera.dim_criativos_clickup (
    id_criativo         VARCHAR(64)   PRIMARY KEY,          -- ex: 'AD180V1', 'CE15V6', 'LD02'
    task_id_clickup     VARCHAR(20)   NOT NULL,             -- ID da tarefa no ClickUp (ex: '86a1b2c3d')
    nome_nomenclatura   VARCHAR(256)  NOT NULL,             -- ex: '[EM][OF02][FB][AD180][V1]'
    nicho               VARCHAR(4)    NOT NULL,             -- ex: 'EM', 'DB', 'MM', 'ED'
    mercado             VARCHAR(4)    DEFAULT 'BR',         -- 'BR' ou 'EUA'
    oferta              VARCHAR(64),                        -- ex: 'GELATINA FIT', 'INSULVITA'
    fonte_trafego       VARCHAR(8),                         -- ex: 'FB', 'GG', 'KW', 'YT'
    tipo_tarefa         VARCHAR(32)   DEFAULT 'CRIATIVO',   -- 'CRIATIVO', 'LEAD', 'VSL', 'RIPAGEM'
    copywriter          VARCHAR(32),                        -- ex: 'YAN', 'ELIAS', 'REAPER'
    editor              VARCHAR(32),                        -- ex: 'MURYLLO', 'IGOR PAIVA'
    status_atual        VARCHAR(64),                        -- status corrente no ClickUp
    data_criacao        TIMESTAMP     DEFAULT NOW(),

    -- Evita duplicata de task_id (uma tarefa pode ter N criativos via subtarefas)
    CONSTRAINT uq_task_criativo UNIQUE (task_id_clickup, id_criativo)
);

COMMENT ON TABLE impera.dim_criativos_clickup IS
    'Dimensao de criativos. Fonte unica de verdade vinda do ClickUp.';

-- ============================================================
-- TABELA FATO 1: fact_performance_redtrack
-- Dados de performance diaria por criativo/ad vindos do RedTrack.
-- Substitui: Relatorio_Performance_RedTrack_DDMM.docx/.pdf
-- Alimentada por: relatorio_redtrack_impera.py (INSERT em vez de .docx)
-- ============================================================
CREATE TABLE IF NOT EXISTS impera.fact_performance_redtrack (
    id_registro     SERIAL        PRIMARY KEY,
    data_registro   DATE          NOT NULL,                 -- dia da metrica
    gestor          VARCHAR(32)   NOT NULL,                 -- ex: 'LUCAS', 'LUDSON', 'DOUGLAS'
    nome_ad_rt      VARCHAR(256)  NOT NULL,                 -- nome do ad no RedTrack (chave de cruzamento)
    custo           NUMERIC(12,2) NOT NULL DEFAULT 0,       -- investimento em R$
    fat_front       NUMERIC(12,2) NOT NULL DEFAULT 0,       -- revenuetype2 + revenuetype3
    vendas          INTEGER       NOT NULL DEFAULT 0,       -- convtype1 (Purchase total)

    -- Impede duplicata: mesmo ad no mesmo dia
    CONSTRAINT uq_perf_dia UNIQUE (data_registro, nome_ad_rt, gestor)
);

COMMENT ON TABLE impera.fact_performance_redtrack IS
    'Fato de performance diaria. fat_front = revenuetype2 + revenuetype3. vendas = convtype1.';

-- ============================================================
-- TABELA FATO 2: fact_slas_esteira
-- Tracking de tempo por fase da esteira de producao.
-- Substitui: ~/Scripts/data/esteira_tracking.json e esteira_log.jsonl
-- Alimentada por: rastreador_esteira.py (INSERT em vez de .json)
-- ============================================================
CREATE TABLE IF NOT EXISTS impera.fact_slas_esteira (
    id_sla              SERIAL        PRIMARY KEY,
    task_id_clickup     VARCHAR(20)   NOT NULL,             -- FK logica para dim_criativos_clickup
    setor_fase          VARCHAR(64)   NOT NULL,             -- ex: 'Escrevendo - Copy', 'Pre-Producao'
    data_entrada        TIMESTAMP     NOT NULL,             -- quando entrou na fase
    data_saida          TIMESTAMP,                          -- quando saiu (NULL = ainda na fase)
    tempo_gasto_horas   NUMERIC(8,2),                       -- calculado: (saida - entrada) em horas
    sla_estourado       BOOLEAN       DEFAULT FALSE,        -- TRUE se tempo > SLA da fase

    -- FK logica (nao enforced) — padrao Data Warehouse
    -- task_id_clickup referencia dim_criativos_clickup.task_id_clickup
    -- Integridade garantida no application layer (impera_db.py)
);

COMMENT ON TABLE impera.fact_slas_esteira IS
    'Fato de SLAs da esteira. Cada linha = uma transicao de fase de uma tarefa.';

-- ============================================================
-- INDICES para performance das queries e views
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_perf_data        ON impera.fact_performance_redtrack (data_registro);
CREATE INDEX IF NOT EXISTS idx_perf_gestor      ON impera.fact_performance_redtrack (gestor);
CREATE INDEX IF NOT EXISTS idx_perf_ad          ON impera.fact_performance_redtrack (nome_ad_rt);
CREATE INDEX IF NOT EXISTS idx_dim_nicho        ON impera.dim_criativos_clickup (nicho);
CREATE INDEX IF NOT EXISTS idx_dim_status       ON impera.dim_criativos_clickup (status_atual);
CREATE INDEX IF NOT EXISTS idx_dim_nomenclatura ON impera.dim_criativos_clickup (nome_nomenclatura);
CREATE INDEX IF NOT EXISTS idx_sla_task         ON impera.fact_slas_esteira (task_id_clickup);
CREATE INDEX IF NOT EXISTS idx_sla_fase         ON impera.fact_slas_esteira (setor_fase);

-- ============================================================
-- VIEW 1: view_performance_financeira
-- Substitui a logica espalhada em 4+ scripts de relatorio.
-- JOIN Performance (RT) x Criativos (CU) com metricas calculadas.
-- ============================================================
CREATE OR REPLACE VIEW impera.view_performance_financeira AS
SELECT
    p.data_registro,
    p.gestor,
    p.nome_ad_rt,

    -- Dados da dimensao (ClickUp)
    d.nicho,
    d.mercado,
    d.oferta,
    d.fonte_trafego,
    d.copywriter,
    d.tipo_tarefa,

    -- Metricas brutas
    p.custo,
    p.fat_front,
    p.vendas,

    -- ROAS Front: fat_front / custo (protegido contra divisao por zero)
    ROUND(p.fat_front / NULLIF(p.custo, 0), 2) AS roas_front,

    -- MC BR: formula oficial IMPERA
    -- (Front Revenue * 0.74) - (Custo * 1.12)
    ROUND((p.fat_front * 0.74) - (p.custo * 1.12), 2) AS mc_br,

    -- CPA: custo por venda
    ROUND(p.custo / NULLIF(p.vendas, 0), 2) AS cpa,

    -- Classificacao Super Cerebro V5
    CASE
        WHEN p.vendas >= 30 AND ROUND(p.fat_front / NULLIF(p.custo, 0), 2) >= 1.8
            THEN 'Escala'
        WHEN p.vendas >= 10 AND ROUND(p.fat_front / NULLIF(p.custo, 0), 2) >= 1.8
            THEN 'Validado/Tracao'
        WHEN p.vendas BETWEEN 3 AND 9
             AND ROUND(p.custo / NULLIF(p.vendas, 0), 2) <= 180
             AND ROUND(p.fat_front / NULLIF(p.custo, 0), 2) >= 1.8
            THEN 'Pre-validado'
        WHEN p.custo >= 500 AND ROUND(p.fat_front / NULLIF(p.custo, 0), 2) < 1.0 AND p.vendas = 0
            THEN 'Negativo'
        WHEN p.custo >= 200 AND ROUND(p.fat_front / NULLIF(p.custo, 0), 2) < 1.0 AND p.vendas <= 2
            THEN 'Em Risco'
        ELSE 'Em Teste'
    END AS status_escala

FROM impera.fact_performance_redtrack p
LEFT JOIN impera.dim_criativos_clickup d
    ON p.nome_ad_rt = d.nome_nomenclatura;

COMMENT ON VIEW impera.view_performance_financeira IS
    'Performance financeira com ROAS, MC BR e classificacao V5. '
    'ROAS nunca usa R$, sempre decimal. Ranking por faturamento, nao ROAS.';

-- ============================================================
-- VIEW 2: view_criativos_orfaos
-- Substitui: detectar_criativos_orfaos.py (output Telegram)
-- Criativos rodando no RedTrack SEM tarefa no ClickUp.
-- ============================================================
CREATE OR REPLACE VIEW impera.view_criativos_orfaos AS
SELECT
    p.nome_ad_rt,
    p.gestor,
    p.data_registro,
    p.custo,
    p.fat_front,
    p.vendas,
    ROUND(p.fat_front / NULLIF(p.custo, 0), 2) AS roas_front,
    ROUND((p.fat_front * 0.74) - (p.custo * 1.12), 2) AS mc_br

FROM impera.fact_performance_redtrack p
WHERE NOT EXISTS (
    SELECT 1
    FROM impera.dim_criativos_clickup d
    WHERE d.nome_nomenclatura = p.nome_ad_rt
)
ORDER BY p.custo DESC;

COMMENT ON VIEW impera.view_criativos_orfaos IS
    'Criativos orfaos: rodando no RT sem tarefa no CU. '
    'Ordenado por maior custo (investimento vazando).';

-- ============================================================
-- GRANTS (ajustar conforme usuarios do Render/Dashboard)
-- ============================================================
-- GRANT USAGE ON SCHEMA impera TO impera_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA impera TO impera_readonly;
