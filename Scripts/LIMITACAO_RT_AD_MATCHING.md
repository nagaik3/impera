# ⚠️ LIMITAÇÃO: rt_ad Matching (RedTrack → ClickUp)

**Data**: 2026-05-24  
**Status**: Identificado, documentado, próximos passos claros

---

## O Problema

Nos relatórios setorizados, especialmente no **Relatório Copy** (Top 10 ADs) e potencialmente no **Relatório Tráfego** (Performance por Gestor), não estamos conseguindo fazer o matching entre:

- **RedTrack campaigns** (ex: `[FB] - BR - VSL 03 - MEMORIALMM`)
- **ClickUp tasks** (ex: `[MM][BR][OF01][FB][AD116][V1]`)

Resultado: Campos como "Copywriter" e "Gestor" aparecem como **"Desconhecido"** nos relatórios.

---

## Raiz do Problema

### O que temos disponível:

**API do RedTrack** (`group=campaign`):
```
{
  "campaign": "[FB] - BR - VSL 03 - MEMORIALMM",
  "cost": 509131,
  "revenuetype2": 905670,
  "convtype1": 7781
}
```
❌ **Problema**: Não contém o `rt_ad` (individual ad ID)

### O que precisamos:

**CSV Export do RedTrack** (via interface web):
```
campaign | rt_ad | cost | revenue | conversions
[FB]..   | AD116 | 509K | 905K    | 7781
[FB]..   | AD117 | ...  | ...     | ...
```
✅ **Solução**: CSV export traz `rt_ad`

---

## Por que Precisamos de rt_ad?

```
RedTrack rt_ad (AD116) ↓
                        → ClickUp task [MM][BR][OF01][FB][AD116][V1]
                        → custom field "Copywritter" = ELIAS
                        ↓
                        Faturamento atribuído a Elias
```

Sem o `rt_ad`, não há como conectar:
- Qual criativo (AD###) gerou qual faturamento
- Qual copywriter é responsável por qual performance
- Qual gestor está rodando qual oferta

---

## Solução: Playwright CSV Export

### Implementação necessária:

1. **Criar script**: `playwright_redtrack_export.py`
   - Login no RedTrack (credenciais em `~/.zshrc`)
   - Export CSV por data range
   - Parse CSV para extrair `rt_ad`

2. **Guardar dados**: `redtrack_export_latest.json`
   - Cache local do último export
   - Atualizar 1x por semana (Domingo)

3. **Integrar**: Nos relatórios
   - `fetch_redtrack_with_copywriter()` → usa `redtrack_export_latest.json`
   - Match `rt_ad` → ClickUp → copywriter

### Referências:

- **Sessão 17-Mai-2026.md**: Documentação completa do Playwright
- **Scripts/playwright_redtrack_export**: Esboço do script (status: aguardando credenciais)
- **Observação**: Cloudflare bypass + anti-detection flags já foram testados ✅

---

## Status Atual

| Componente | Status | Bloqueador |
|-----------|--------|-----------|
| API RedTrack campaigns | ✅ Funciona | rt_ad não disponível |
| ClickUp tasks | ✅ Funciona | — |
| CSV export via Playwright | ⏳ Pronto | Credenciais do RT |
| rt_ad → copywriter matching | ❌ Não implementado | Aguarda CSV export |
| Relatórios (sem matching) | ✅ Funciona | Campos "Desconhecido" |

---

## Impacto nos Relatórios

### 📊 COPY — Relatório Semanal
- ✅ Volume total: correto
- ✅ Novo vs Variação: correto
- ✅ Faturamento por copywriter: ❌ zerado (sem matching)
- ✅ Assertividade Copy: ✅ correto (não depende de rt_ad)
- ⚠️ Top 10 ADs: copywriter = "Desconhecido"

### 📈 TRÁFEGO — Relatório Semanal
- ✅ Faturamento Front: correto
- ✅ ROAS: correto
- ⚠️ Performance por Gestor: gestor = "Sem gestor" (não temos matching)
- ✅ Ofertas em Escala: correto
- ✅ Status de Nichos: correto

### 📊 GPDR — Visão Executiva
- ✅ Não depende de rt_ad (consolidado de outros relatórios)
- ✅ Score de Saúde: correto mesmo sem matching

---

## Próximos Passos

### Curto Prazo (Imediato)
1. ✅ Documentar limitação (este arquivo)
2. ✅ Deixar campos como "Desconhecido" (já feito)
3. ✅ Alertar usuario da limitação

### Médio Prazo (Esta Semana)
1. Testar credenciais Playwright no RedTrack
2. Implementar `playwright_redtrack_export.py`
3. Criar cache `redtrack_export_latest.json`
4. Integrar nos relatórios

### Longo Prazo
1. Automação: export semanal (Domingo 20:00, antes dos relatórios)
2. Alertas: se export falhar, usar cache anterior
3. Validação: comparar match rate vs baseline 94%

---

## Conclusão

**Não é um bug**, é uma **limitação de dados**. A API do RedTrack não expõe o `rt_ad` necessário para matching. A solução é bem conhecida (Playwright CSV export) e já foi planejada anteriormente.

**Para os relatórios continuarem funcionando**:
- Copy: volume e assertividade corretos, faturamento por CW virá depois
- Tráfego: todos os KPIs funcionam, gestor virá depois
- GPDR: 100% funcional agora

---

*Iago: Quando as credenciais do Playwright estiverem prontas, podemos implementar o CSV export e resolver isso completamente em ~1-2 horas.*
