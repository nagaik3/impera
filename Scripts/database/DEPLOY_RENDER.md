# Deploy PostgreSQL no Render — IMPERA Data Lake
> GPDR - Iago Almeida, assistido por Claude | 12/Mai/2026

---

## Passo 1: Provisionar PostgreSQL no Render

1. Acessar https://dashboard.render.com
2. Clicar **New** → **PostgreSQL**
3. Configurar:
   - **Name:** `impera-datalake`
   - **Database:** `impera_db`
   - **User:** `impera_user`
   - **Region:** Oregon (us-west) — mesmo do atribuidor-impera
   - **Plan:** Free (90 dias) ou Starter ($7/mes para persistencia)
4. Clicar **Create Database**
5. Aguardar status "Available" (~2 min)
6. Copiar a **Internal Database URL** (para servicos no mesmo Render)
   e a **External Database URL** (para acesso local/crontab)

---

## Passo 2: Configurar Environment Variables no Render

### No servico atribuidor-impera (e qualquer outro servico web):

1. Ir em https://dashboard.render.com → servico `atribuidor-impera`
2. Aba **Environment** → **Add Environment Variable**
3. Adicionar:

| Key | Value | Origem |
|-----|-------|--------|
| `DATABASE_URL` | `postgresql://impera_user:SENHA@HOST:5432/impera_db?sslmode=require` | Internal URL do PostgreSQL |
| `CLICKUP_API_TOKEN` | (seu token) | MOVER do codigo para ca |
| `REDTRACK_API_KEY` | (sua key) | MOVER do codigo para ca |

**CRITICO (P0):** O `?sslmode=require` no final da URL forca encriptacao TLS.
Nunca usar `sslmode=disable` em producao.

4. Clicar **Save Changes** → servico reinicia automaticamente

### Na maquina local (crontab):

Adicionar no `~/.zshrc`:

```bash
# === IMPERA Data Lake ===
export DATABASE_URL="postgresql://impera_user:SENHA@HOST:5432/impera_db?sslmode=require"
```

Recarregar: `source ~/.zshrc`

**Nota:** Usar a External Database URL (com hostname publico) na maquina local.
Usar a Internal Database URL (com hostname interno) nos servicos Render.

---

## Passo 3: Criar o Schema

Apos configurar DATABASE_URL, executar:

```bash
cd ~/Scripts
python3 -m database.impera_db
```

Saida esperada: `Schema impera criado/atualizado.`

Verificar que as tabelas existem:

```bash
psql "$DATABASE_URL" -c "\dt impera.*"
```

Saida esperada:
```
 Schema |          Name              | Type  |    Owner
--------+----------------------------+-------+------------
 impera | dim_criativos_clickup      | table | impera_user
 impera | fact_performance_redtrack  | table | impera_user
 impera | fact_slas_esteira           | table | impera_user
```

---

## Passo 4: Conectar ao servico web existente

No `atribuidor-impera`, o DATABASE_URL ja esta como env var.
Para usar no codigo do dashboard:

```python
import os
from sqlalchemy import create_engine

engine = create_engine(os.getenv('DATABASE_URL'))
```

---

## Passo 5: Verificacao de seguranca (P0/P1)

### Checklist P0:
- [ ] Tokens NUNCA hardcoded nos scripts (so env vars)
- [ ] DATABASE_URL com `sslmode=require`
- [ ] Senha do PostgreSQL com 20+ caracteres
- [ ] Tokens removidos de qualquer .py commitado no GitHub

### Checklist P1:
- [ ] HTTPS forcado no Render (Settings → Redirect HTTP to HTTPS)
- [ ] Rate limiting no FastAPI (slowapi ou similar)
- [ ] Backups diarios do PostgreSQL (Render faz automatico no plano pago)

### Verificar HTTPS nos servicos:
1. `atribuidor-impera` → Settings → **Force HTTPS**: ON
2. `nova-tarefa-impera` → Settings → **Force HTTPS**: ON

---

## Passo 6: Atualizar crontab

Os scripts que agora inserem no banco precisam de DATABASE_URL.
O crontab ja tem CLICKUP_API_TOKEN e REDTRACK_API_KEY.
Adicionar:

```bash
crontab -e
```

No topo, junto das outras env vars:
```
DATABASE_URL=postgresql://impera_user:SENHA@HOST:5432/impera_db?sslmode=require
```

---

## Manutencao

### Plano Free — limitacoes:
- 256 MB storage
- Banco expira em 90 dias (precisa recriar)
- Sem backups automaticos

### Recomendacao: Starter ($7/mes)
- 1 GB storage
- Sem expiracao
- Backups diarios automaticos
- Point-in-time recovery

Para migrar: Dashboard → PostgreSQL → Upgrade Plan

---

*GPDR - Iago Almeida, assistido por Claude*
