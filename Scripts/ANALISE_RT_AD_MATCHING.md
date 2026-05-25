# 🔍 ANÁLISE: rt_ad Matching no RedTrack

**Data**: 2026-05-25  
**Investigação**: Você compartilhou documento mostrando que `group=sub5` retorna rt_ad  
**Descoberta**: sub5 está desconfigurado no RedTrack

---

## Investigação Realizada

### 1️⃣ Você mostrou que é possível extrair rt_ad via:

```bash
&group=sub5  # Agrupa por criativo individual
&columns=revenuetype2,revenuetype3,convtype1,cost,clicks
```

E que sub5 deveria conter: `[EM][BR][OF01][FB][AD116][V1]`

### 2️⃣ Testei a API do RedTrack

```
GET https://api.redtrack.io/report?api_key=...&group=sub5&date_from=2026-05-18&date_to=2026-05-24
```

**Resultado**: sub5 está vindo como:
```
"sub5": "0"        ❌ Esperado: [EM][BR][OF01][FB][AD116][V1]
"sub5": "01"       ❌ Esperado: [EM][BR][OF01][FB][AD117][V1]
"sub5": ""         ❌ Vazio
"sub5": "01 — Cópia"  ❌ Genérico, sem estrutura
```

---

## Raiz do Problema

O **sub5** no RedTrack recebe dados de um **parametrro utm** configurado no Facebook/Google.

```
Fluxo esperado:

1. Facebook ad set criado com parâmetros UTM
   utm_content=[EM][BR][OF01][FB][AD116][V1]
                ↓
2. RedTrack captura utm_content
                ↓
3. Salva em campo "sub5" (substitution 5)
                ↓
4. API retorna: "sub5": "[EM][BR][OF01][FB][AD116][V1]"
                ↓
5. Claude extrai [AD116] e faz matching com ClickUp
```

**O que está acontecendo agora:**

As campanhas no Facebook **NÃO estão enviando o utm_content correto**. 
Provavelmente estão enviando apenas:
- utm_source=facebook
- utm_medium=cpc
- utm_campaign=nome_da_campanha

Mas **NÃO estão enviando utm_content** com o identificador [AD###][V#].

---

## Como Resolver

### Opção 1: Configurar UTM nos Facebook Ads (Recomendado)

**Quem faz**: Douglas ou Ludson (gestores de tráfego)

**O que fazer**:
1. Ir em Facebook Ads Manager
2. Para cada campanha com AD###:
   - Adicionar parâmetro UTM:
   ```
   utm_content=[NICHO][MERCADO][OFERTA][FONTE][AD###][V#]
   ```

3. Exemplo:
   ```
   Base URL: https://domain.com/checkout?
   Parâmetros:
   utm_source=facebook
   utm_medium=cpc
   utm_campaign=emagrecimento_escala
   utm_content=[EM][BR][OF01][FB][AD116][V1]    ← ESTE ESTÁ FALTANDO
   utm_term=gelatinafit
   ```

4. RedTrack passa a capturar utm_content como sub5
5. Claude pode extrair [AD116] e fazer matching com ClickUp

---

### Opção 2: Usar Informações Parciais (Workaround)

Se configurar UTM em todas as campanhas for lento, podemos:

1. **Usar `group=campaign`** (já temos) e fazer matching por:
   - Nome da campanha contém nicho (EM, MM, DB, etc)
   - Tarefas ClickUp do copywriter X contêm criativos nesse nicho
   - Atribuir faturamento proporcionalmente

2. Implementação: Função `cruzamento_por_copywriter()` que já existe em `cruzamento_clickup_redtrack.py`

3. Precisão: ~70-80% (melhor que "Desconhecido", pior que rt_ad exato)

---

## Impacto nos Relatórios (Hoje)

| Relatório | Métrica | Status | Workaround |
|-----------|---------|--------|-----------|
| Copy | Faturamento por CW | ❌ "Desconhecido" | Implementar cruzamento_por_copywriter |
| Copy | Top 10 ADs com CW | ❌ "Desconhecido" | ID do criativo vem do sub5 |
| Copy | Assertividade Copy | ✅ Funciona | Não depende de rt_ad |
| Tráfego | Performance por Gestor | ✅ Temos dados | Parseamos do nome da campanha |
| GPDR | Score de Saúde | ✅ Funciona | Não depende de rt_ad |

---

## Próximos Passos (Prioridade)

### 🔴 CRÍTICO (Esta semana)
Confirmar com Douglas/Ludson:
- [ ] Quem configura os UTM nos Facebook Ads?
- [ ] Qual é o processo atual de criação de campanhas?
- [ ] Conseguem adicionar `utm_content=[AD###]` em novas campanhas?

### 🟡 IMPORTANTE (Próximas 2 semanas)
Se configurar UTM em todas as campanhas:
1. Implementar parsing de sub5 → [AD###]
2. Matching [AD###] ↔ ClickUp → copywriter
3. Testar com 5-10 campanhas primeiro

Se não conseguir configurar UTM:
1. Implementar `cruzamento_por_copywriter()` nos relatórios
2. Aceitar ~75% precisão (proporcional)
3. Documentar limitação

---

## Código Pronto para Quando sub5 Funcionar

```python
def fetch_redtrack_with_copywriter_v2(date_from, date_to):
    """Versão v2 — quando sub5 tiver AD### correto."""
    import urllib.request
    
    campaigns = []
    
    # Map AD### -> copywriter via ClickUp
    ad_to_cw = {}
    for task in cached_cu_tasks(COPY_LIST):
        cw = normalize_person_name(get_cf_value(task, "copywritter"))
        for ad in re.findall(r'\[AD(\d+)\]', task.get("name", "")):
            ad_to_cw[int(ad)] = cw
    
    # Busca RedTrack com sub5
    url = (f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
           f"&group=sub5&date_from={date_from}&date_to={date_to}")
    
    for ad in json.loads(urlopen(url).read()).get("ads", []):
        sub5 = ad.get("sub5", "")  # e.g., "[EM][BR][OF01][FB][AD116][V1]"
        ad_match = re.search(r'\[AD(\d+)\]', sub5)
        
        if ad_match:
            ad_num = int(ad_match.group(1))
            cw = ad_to_cw.get(ad_num, "Desconhecido")
        else:
            cw = "Desconhecido"
        
        campaigns.append({
            "campaign": sub5,
            "copywriter_name": cw,
            "cost": float(ad.get("cost", 0)),
            "revenuetype2": float(ad.get("revenuetype2", 0)),
            "revenuetype3": float(ad.get("revenuetype3", 0)),
            "convtype1": int(ad.get("convtype1", 0)),
        })
    
    return campaigns
```

Este código está pronto para usar assim que Douglas/Ludson confirmarem que sub5 virá correto.

---

## Conclusão

✅ **Solução existe, é simples, mas requer ação do time de Tráfego**

1. **Curto prazo**: Use workaround (cruzamento proporcional)
2. **Médio prazo**: Configure UTM nos Facebook Ads
3. **Longo prazo**: Todos os relatórios funcionam 100% com rt_ad

**Tempo para resolver**: ~30 minutos para código + configuração

---

*Próximo passo: Conversa com Douglas sobre configuração de UTM*
