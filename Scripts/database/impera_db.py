"""
IMPERA Data Lake — Modulo de integracao PostgreSQL
Substitui exportacao .docx/.pdf por INSERT direto no banco.

Uso nos scripts existentes:
    # ANTES:
    # df.to_excel('Relatorio.xlsx')
    # gerar_docx(dados, 'Relatorio.docx')

    # DEPOIS:
    from database.impera_db import inserir_dados, get_engine
    inserir_dados(df, 'fact_performance_redtrack')

Credenciais via env var DATABASE_URL (nunca hardcoded).
Formato: postgresql://user:pass@host:5432/impera_db

GPDR - Iago Almeida, assistido por Claude
12/Mai/2026
"""

import os
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# ============================================================
# CONEXAO
# ============================================================

_engine = None


def get_engine():
    """Retorna engine singleton. Le DATABASE_URL do ambiente."""
    global _engine
    if _engine is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise EnvironmentError(
                'DATABASE_URL nao definida. '
                'Adicione em ~/.zshrc: export DATABASE_URL="postgresql://..."'
            )
        # Render usa postgres:// mas SQLAlchemy exige postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        _engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # reconecta automaticamente
        )
    return _engine


# ============================================================
# FUNCAO PRINCIPAL: inserir_dados
# ============================================================

def inserir_dados(df: pd.DataFrame, nome_tabela: str, schema: str = 'impera') -> int:
    """
    Insere DataFrame no PostgreSQL.

    Args:
        df: DataFrame com colunas correspondentes a tabela destino.
        nome_tabela: Nome da tabela (ex: 'fact_performance_redtrack').
        schema: Schema do banco (default: 'impera').

    Returns:
        Numero de linhas inseridas.

    Raises:
        EnvironmentError: Se DATABASE_URL nao estiver definida.
        ValueError: Se DataFrame estiver vazio.
    """
    if df.empty:
        logger.warning(f'DataFrame vazio, nada inserido em {schema}.{nome_tabela}')
        return 0

    engine = get_engine()
    linhas_antes = len(df)

    try:
        df.to_sql(
            name=nome_tabela,
            con=engine,
            schema=schema,
            if_exists='append',   # adiciona sem apagar dados existentes
            index=False,          # nao insere indice do pandas
            method='multi',       # batch insert (mais rapido)
            chunksize=500,        # evita payload gigante
        )
        logger.info(f'{linhas_antes} linhas inseridas em {schema}.{nome_tabela}')
        return linhas_antes

    except IntegrityError as e:
        # Duplicatas (UNIQUE constraint) — esperado em re-runs
        logger.warning(f'Duplicatas ignoradas em {schema}.{nome_tabela}: {e}')
        return _inserir_ignorando_duplicatas(df, nome_tabela, schema, engine)


def _inserir_ignorando_duplicatas(
    df: pd.DataFrame, nome_tabela: str, schema: str, engine
) -> int:
    """Fallback: insere linha a linha ignorando duplicatas."""
    inseridas = 0
    for _, row in df.iterrows():
        try:
            row.to_frame().T.to_sql(
                name=nome_tabela,
                con=engine,
                schema=schema,
                if_exists='append',
                index=False,
            )
            inseridas += 1
        except IntegrityError:
            continue
    logger.info(f'{inseridas}/{len(df)} linhas inseridas (duplicatas ignoradas)')
    return inseridas


# ============================================================
# FUNCOES AUXILIARES POR TABELA
# ============================================================

def inserir_performance_rt(df_rt: pd.DataFrame, gestor: str, data: str) -> int:
    """
    Insere dados de performance do RedTrack.

    Exemplo de uso no relatorio_redtrack_impera.py:
        # Onde antes fazia:
        #   gerar_docx_redtrack(dados, f'Relatorio_RedTrack_{data}.docx')
        # Agora faz:
        from database.impera_db import inserir_performance_rt
        inserir_performance_rt(df, gestor='LUCAS', data='2026-05-12')

    Args:
        df_rt: DataFrame com colunas: nome_ad_rt, custo, fat_front, vendas
        gestor: Nome do gestor (ex: 'LUCAS')
        data: Data no formato 'YYYY-MM-DD'
    """
    df = df_rt.copy()
    df['gestor'] = gestor
    df['data_registro'] = pd.to_datetime(data).date()

    # Garante apenas colunas validas
    colunas_validas = [
        'data_registro', 'gestor', 'nome_ad_rt',
        'custo', 'fat_front', 'vendas'
    ]
    df = df[[c for c in colunas_validas if c in df.columns]]

    return inserir_dados(df, 'fact_performance_redtrack')


def inserir_criativo_clickup(
    id_criativo: str,
    task_id: str,
    nome_nomenclatura: str,
    nicho: str,
    mercado: str = 'BR',
    oferta: str = None,
    fonte_trafego: str = None,
    tipo_tarefa: str = 'CRIATIVO',
    copywriter: str = None,
    editor: str = None,
    status_atual: str = 'backlog copy',
) -> int:
    """
    Insere um criativo na dimensao.

    Uso no clickup_criar_tarefa.py:
        from database.impera_db import inserir_criativo_clickup
        inserir_criativo_clickup(
            id_criativo='AD180V1',
            task_id='86abc123',
            nome_nomenclatura='[EM][OF02][FB][AD180][V1]',
            nicho='EM',
            oferta='GELATINA FIT',
            fonte_trafego='FB',
            copywriter='YAN',
        )
    """
    df = pd.DataFrame([{
        'id_criativo': id_criativo,
        'task_id_clickup': task_id,
        'nome_nomenclatura': nome_nomenclatura,
        'nicho': nicho,
        'mercado': mercado,
        'oferta': oferta,
        'fonte_trafego': fonte_trafego,
        'tipo_tarefa': tipo_tarefa,
        'copywriter': copywriter,
        'editor': editor,
        'status_atual': status_atual,
        'data_criacao': datetime.now(),
    }])
    return inserir_dados(df, 'dim_criativos_clickup')


def inserir_transicao_esteira(
    task_id: str,
    setor_fase: str,
    data_entrada: datetime,
    data_saida: datetime = None,
    sla_horas: float = None,
) -> int:
    """
    Registra transicao de fase na esteira.

    Uso no rastreador_esteira.py:
        from database.impera_db import inserir_transicao_esteira
        inserir_transicao_esteira(
            task_id='86abc123',
            setor_fase='Escrevendo - Copy',
            data_entrada=datetime(2026, 5, 10, 9, 0),
            data_saida=datetime(2026, 5, 10, 18, 0),
            sla_horas=24,
        )
    """
    tempo_gasto = None
    sla_estourado = False

    if data_saida and data_entrada:
        delta = (data_saida - data_entrada).total_seconds() / 3600
        tempo_gasto = round(delta, 2)
        if sla_horas:
            sla_estourado = tempo_gasto > sla_horas

    df = pd.DataFrame([{
        'task_id_clickup': task_id,
        'setor_fase': setor_fase,
        'data_entrada': data_entrada,
        'data_saida': data_saida,
        'tempo_gasto_horas': tempo_gasto,
        'sla_estourado': sla_estourado,
    }])
    return inserir_dados(df, 'fact_slas_esteira')


# ============================================================
# QUERIES PRONTAS (para dashboards e bots)
# ============================================================

def query_performance(data_inicio: str, data_fim: str, gestor: str = None) -> pd.DataFrame:
    """
    Consulta view_performance_financeira.
    Retorna DataFrame pronto para tabela markdown ou dashboard.
    """
    engine = get_engine()
    sql = """
        SELECT *
        FROM impera.view_performance_financeira
        WHERE data_registro BETWEEN :inicio AND :fim
    """
    params = {'inicio': data_inicio, 'fim': data_fim}

    if gestor:
        sql += " AND gestor = :gestor"
        params['gestor'] = gestor

    sql += " ORDER BY fat_front DESC"

    return pd.read_sql(text(sql), engine, params=params)


def query_orfaos(limite: int = 50) -> pd.DataFrame:
    """Consulta view_criativos_orfaos. Top N por custo."""
    engine = get_engine()
    sql = """
        SELECT *
        FROM impera.view_criativos_orfaos
        LIMIT :limite
    """
    return pd.read_sql(text(sql), engine, params={'limite': limite})


def query_slas_atrasados() -> pd.DataFrame:
    """Tarefas com SLA estourado que ainda nao sairam da fase."""
    engine = get_engine()
    sql = """
        SELECT
            s.task_id_clickup,
            d.nome_nomenclatura,
            d.copywriter,
            d.editor,
            s.setor_fase,
            s.data_entrada,
            s.tempo_gasto_horas,
            s.sla_estourado
        FROM impera.fact_slas_esteira s
        JOIN impera.dim_criativos_clickup d
            ON s.task_id_clickup = d.task_id_clickup
        WHERE s.data_saida IS NULL
          AND s.sla_estourado = TRUE
        ORDER BY s.tempo_gasto_horas DESC
    """
    return pd.read_sql(text(sql), engine)


# ============================================================
# INICIALIZACAO DO SCHEMA
# ============================================================

def inicializar_schema():
    """Executa o DDL para criar schema + tabelas + views."""
    ddl_path = os.path.join(os.path.dirname(__file__), '001_schema_datalake.sql')
    engine = get_engine()

    with open(ddl_path, 'r') as f:
        ddl = f.read()

    with engine.begin() as conn:
        # Executa cada statement separadamente
        for statement in ddl.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                conn.execute(text(statement))

    logger.info('Schema impera inicializado com sucesso.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    inicializar_schema()
    print('Schema impera criado/atualizado.')
