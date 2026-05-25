# 🔗 IMPLEMENTAÇÃO: Gerador de URLs Trackable

**Data**: 2026-05-25  
**Status**: ✅ Função Pronta, Plano Definido  
**Objetivo**: Gerar e salvar URLs com utm_content nas tarefas do ClickUp

---

## 🎯 O Que Faz

Quando o dashboard cria uma tarefa:
```
[EM][BR][OF02][FB][AD116][V1]
```

Agora pode gerar automaticamente:
```
https://seu-dominio.com/?utm_source=facebook&utm_medium=cpc&utm_campaign=EM_OF02&utm_content=AD116_V1
```

**Resultado**: RedTrack recebe `sub5="AD116_V1"` ✅ (antes recebia `sub5="0"` ❌)

---

## ✅ Função Pronta

**Local**: `/Users/iagoalmeida/Scripts/gerar_tracking_url.py`

**Funções principais**:
- `parse_nomenclatura(task_name)` — Extrai componentes de [EM][BR][OF02][FB][AD116][V1]
- `gerar_tracking_url(task_name)` — Gera URL trackable com utm_params
- `atualizar_custom_field_clickup(task_id, url_data)` — Salva no ClickUp (⏳ implementação completa)

**Teste**:
```bash
python3 gerar_tracking_url.py "[EM][BR][OF02][FB][AD116][V1]"

✅ URL Completa:
https://seu-dominio.com/?utm_source=facebook&utm_medium=cpc&utm_campaign=EM_OF02&utm_content=AD116_V1
```

---

## 🔧 3 Passos para Implementação

### Passo 1️⃣: Criar Custom Field no ClickUp

**Onde**: GESTÃO DE TRÁFEGO (lista 901324476398)  
**O que criar**: Custom field "🔗 URL Trackable"

**Via UI do ClickUp**:
1. Ir em Settings da lista GESTÃO DE TRÁFEGO
2. Custom fields → Add field
3. Nome: `🔗 URL Trackable`
4. Tipo: `URL` ou `Text`
5. Salvar

**Obter o ID do campo**:
```bash
python3 << 'EOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_cu_tasks

tasks = cached_cu_tasks("901324476398", include_closed=False)
if tasks:
    for cf in tasks[0].get("custom_fields", []):
        if "trackable" in cf.get("name", "").lower() or "url" in cf.get("name", "").lower():
            print(f"ID: {cf['id']} | Nome: {cf['name']}")
EOF
```

Copiar o ID e adicionar em `gerar_tracking_url.py` na função `atualizar_custom_field_clickup()`.

---

### Passo 2️⃣: Integrar no Dashboard

**Se dashboard está em `/atribuidor-impera.onrender.com`**:

Quando o dashboard cria uma tarefa, chamar:

```javascript
// JavaScript no dashboard
const taskName = "[EM][BR][OF02][FB][AD116][V1]";

// Chamar endpoint de geração de URL
const response = await fetch("/api/gerar-tracking-url", {
  method: "POST",
  body: JSON.stringify({ task_name: taskName })
});

const { tracking_url } = await response.json();

// Salvar na tarefa ClickUp criada
// (via API do ClickUp ou webhook)
```

**OU integrar no script Python do dashboard**:

```python
from gerar_tracking_url import gerar_tracking_url

# Após criar tarefa no ClickUp
task_name = "[EM][BR][OF02][FB][AD116][V1]"
result = gerar_tracking_url(task_name)

# Atualizar custom field
update_task_custom_field(
    task_id=newly_created_task_id,
    field_id="tracking_url_field_id",
    value=result["url_completa"]
)
```

---

### Passo 3️⃣: Avisar Gestor

Após salvar a URL no ClickUp, adicionar na descrição da tarefa:

```markdown
---
🔗 **URL TRACKABLE GERADA AUTOMATICAMENTE**

[Cole esta URL ao criar a campanha no Facebook]

**utm_source**: facebook
**utm_medium**: cpc
**utm_campaign**: EM_OF02
**utm_content**: AD116_V1

**URL Completa**:
https://seu-dominio.com/?utm_source=facebook&utm_medium=cpc&utm_campaign=EM_OF02&utm_content=AD116_V1
---
```

Ou usar o próprio custom field "URL Trackable" que será preenchido automaticamente.

---

## 📊 Mapeamento de Fontes

Função `gerar_tracking_url()` já trata:

| Fonte | utm_source | utm_medium |
|-------|-----------|-----------|
| FB | facebook | cpc |
| GG | google | cpc |
| YT | youtube | cpc |
| TT | tiktok | cpc |
| KW | kwai | cpc |
| TB | taboola | display |
| MG | mgid | display |
| VT | vturb | email |

Fácil adicionar outras fontes conforme necessário.

---

## 🧪 Teste Rápido

```bash
# Teste de geração
python3 gerar_tracking_url.py "[MM][BR][OF01][FB][AD088][V1]"

# Resultado esperado:
# utm_content=AD088_V1 ✅
```

---

## 🔄 Fluxo Completo (Após Implementação)

```
1. Dashboard cria tarefa:
   [EM][BR][OF02][FB][AD116][V1]
   ↓

2. Script chama gerar_tracking_url():
   Entrada: [EM][BR][OF02][FB][AD116][V1]
   Saída: https://seu-dominio.com/?utm_source=facebook&utm_medium=cpc&utm_campaign=EM_OF02&utm_content=AD116_V1
   ↓

3. URL salva em custom field:
   Task.custom_fields["URL Trackable"] = url_completa
   ↓

4. Gestor vê na tarefa ClickUp:
   "🔗 URL TRACKABLE: [link clicável]"
   ↓

5. Gestor copia → Cola no Facebook ao criar campanha
   ↓

6. Facebook envia utm_content para RedTrack
   ↓

7. RedTrack recebe:
   sub5="AD116_V1" ✅
   ↓

8. Claude extrai [AD116]:
   Matching ClickUp → Copywriter = ELIAS ✅
   ↓

9. Faturamento atribuído a ELIAS no relatório Copy ✅
```

---

## ✨ Benefícios

| Antes | Depois |
|-------|--------|
| sub5="0" | sub5="AD116_V1" |
| "Copywriter: Desconhecido" | "Copywriter: ELIAS" |
| Faturamento: "Desconhecido" | Faturamento: "R$6.434" |
| Relatório Copy sem dados | Relatório Copy com tudo preenchido |

---

## 🚀 Próximos Passos

### Hoje/Amanhã
- [ ] Passo 1: Criar custom field no ClickUp (5 min)
- [ ] Obter ID do campo e adicionar em `gerar_tracking_url.py` (2 min)

### Essa Semana
- [ ] Passo 2: Integrar função no dashboard ou em script de criação de tarefas
- [ ] Passo 3: Testar com 1-2 campanhas
- [ ] Validar que RedTrack recebe `sub5` correto

### Próxima Semana
- [ ] Integrar `sub5` parsing no `relatorio_copy_semanal.py`
- [ ] Testar matching completo [AD###] → ClickUp → Copywriter
- [ ] Validar assertividade e faturamento por copywriter

---

## 📝 Notas

- **DOMINIO_BASE**: Configurável via env var `DOMINIO_BASE` (default: "https://seu-dominio.com")
- **Campo customizado**: Uma vez criado, o ID nunca muda (reutilizável)
- **Função é agnóstica**: Pode ser chamada de qualquer lugar (dashboard, CLI, script)

---

## 🔗 Arquivos Relacionados

- `gerar_tracking_url.py` — ⭐ Função pronta para usar
- `relatorio_copy_semanal.py` — Aguardando sub5 correto para fazer matching
- `cruzamento_clickup_redtrack.py` — Já tem parsing de AD### pronto

---

**Status**: ✅ Pronto para próxima fase (integração)

*Um dia sem rt_ad, outro dia com rt_ad. Hoje é dia de resolver!* 🚀
