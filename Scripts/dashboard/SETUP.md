# Dashboard IMPERA — Guia de Setup

## 1. PostgreSQL no Render (Gratuito)

1. Acesse https://render.com (mesmo login do bot)
2. **New** → **PostgreSQL**
3. Configurações:
   - Name: `impera-dashboard`
   - Database: `impera`
   - User: `impera_user`
   - Region: Oregon (mesmo dos outros serviços)
   - Plan: **Free** (1GB, suficiente para começar)
4. Após criar, copie a **External Database URL** (formato: `postgresql://user:pass@host/db`)
5. Adicione no `~/.zshrc`:
   ```bash
   export DASHBOARD_DATABASE_URL="postgresql://impera_user:SENHA@HOST:5432/impera"
   ```
6. Rode `source ~/.zshrc`

## 2. Inicializar Banco

```bash
# Instalar psycopg2 se não tiver
pip3 install psycopg2-binary

# Criar tabelas
python3 ~/Scripts/dashboard/etl_dashboard.py --init-schema

# Primeira carga (últimos 30 dias)
python3 ~/Scripts/dashboard/etl_dashboard.py --days 30
```

## 3. Crontab (2x/dia)

```bash
crontab -e
# Adicionar:
30 9 * * * cd ~/Scripts && /usr/bin/python3 dashboard/etl_dashboard.py --days 7 >> ~/Scripts/data/etl_dashboard.log 2>&1
30 17 * * * cd ~/Scripts && /usr/bin/python3 dashboard/etl_dashboard.py --days 3 >> ~/Scripts/data/etl_dashboard.log 2>&1
```

## 4. Metabase (Dashboard Visual)

### Opção A: Metabase Cloud (mais fácil)
1. Acesse https://www.metabase.com/start/
2. Plano Starter gratuito (até 5 users)
3. Conecte no PostgreSQL do Render (usar External URL)
4. Pronto — compartilhe link com liderança

### Opção B: Self-hosted no Render (Docker)
1. No Render: **New** → **Web Service**
2. Image: `metabase/metabase:latest`
3. Environment Variables:
   ```
   MB_DB_TYPE=postgres
   MB_DB_DBNAME=impera
   MB_DB_PORT=5432
   MB_DB_USER=impera_user
   MB_DB_PASS=SENHA
   MB_DB_HOST=HOST_INTERNO_RENDER
   ```
4. Plan: Free (512MB RAM, suficiente)
5. Acesse via URL do Render

## 5. Dashboards Sugeridos no Metabase

Após conectar, criar as seguintes perguntas/dashboards:

### Página 1 — Executive Summary
- Card: Faturamento Front (últimos 7 dias)
- Card: MC BR total
- Card: ROAS Front médio
- Card: Vendas totais
- Gráfico linha: Tendência 30 dias (revenue_front por dia)
- Tabela: Ranking nichos por faturamento

### Página 2 — Gestores
- Tabela: Ranking gestores (faturamento DESC)
- Gráfico barras: Comparativo semana atual vs anterior
- Breakdown por fonte (FB, KW, TT)

### Página 3 — Nichos & Ofertas
- Treemap: Faturamento por nicho
- Tabela: Ofertas por ROAS + vendas
- Gráfico: Saturação (custo crescendo, ROAS caindo)

### Página 4 — Criativos Lifecycle
- Funil: criado → teste → validado → top
- Card: Taxa de validação
- Tabela: Top 10 criativos por faturamento

### Página 5 — Produção
- Gráfico barras: Criativos por copywriter (semana)
- Tabela: SLA cumprimento por setor
- Linha: Throughput semanal

## 6. Cores (Dark Theme)

No Metabase: Admin → Appearance → aplicar tema escuro.
Cores custom nos gráficos:
- Positivo: #00D68F
- Alerta: #FFAA00  
- Negativo: #FF3D71
- Série 1: #3366FF
- Série 2: #8B5CF6
