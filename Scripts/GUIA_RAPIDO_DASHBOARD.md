# 🚀 Guia Rápido — Dashboard de Tráfego + Relatórios

## Uso Imediato

### 1. Ver Dashboard de Todos os Criativos em Teste
```bash
python3 ~/Scripts/dashboard_trafego_status.py
```
Exibe tabela com:
- **Total de criativos**: 1391 (por status)
- **Status**: aguardando teste, em teste, testes concluídos, pré-escala, validado, escala, etc.
- **Copywriter responsável**: ANA, CAROL, CASSIO, CRISPIM, ELIAS, YAN
- **Dias no status**: quanto tempo está nesse status

### 2. Filtrar por Status Específico
```bash
# Ver apenas criativos "em teste"
python3 ~/Scripts/dashboard_trafego_status.py --status="em teste"

# Ver apenas criativos em escala (sucesso)
python3 ~/Scripts/dashboard_trafego_status.py --status="escala"

# Ver criativos para descarte
python3 ~/Scripts/dashboard_trafego_status.py --status="cemitério"
```

### 3. Exportar para JSON
```bash
python3 ~/Scripts/dashboard_trafego_status.py --json
# Salva em: ~/Documents/dashboard_trafego.json
```

---

## Relatório Mensal de Copywriters

### Gerar Relatório
```bash
# Relatório do mês anterior (automático)
python3 ~/Scripts/relatorio_mensal_copywriters_testes.py
# Salva em: ~/Documents/Relatorio_Mensal_CW_Testes_MM_YYYY.docx

# Mês específico
python3 ~/Scripts/relatorio_mensal_copywriters_testes.py --mes=4 --ano=2026
# Abril de 2026

python3 ~/Scripts/relatorio_mensal_copywriters_testes.py --mes=12 --ano=2025
# Dezembro de 2025
```

### O que o Relatório Mostra
| Métrica | Significado |
|---------|------------|
| Criados | Total de criativos criados no mês |
| Em Teste | Quantos foram para testes |
| Aprovados | Quantos chegaram em pré-escala+ |
| Em Escala | Quantos estão gerando receita |
| Taxa Aprov. | % de aprovação (aprovados / em teste) |
| Taxa Escala | % em escala (em escala / criados) |
| Variações | Quantas V2, V3, etc. criou |

---

## Agente Especializado

### Fazer Perguntas sobre Workflow
```bash
# No Claude Code, usar skill:
query_corpus name="impera-ops" question="Qual é o fluxo completo de um criativo?"
```

### Exemplos de Perguntas
```
"Quantos copywriters temos?"
→ Resposta: 6 (ANA, CAROL, CASSIO, CRISPIM, ELIAS, YAN)

"Qual é a diferença entre pré-escala e validado?"
→ Resposta: Explicação do workflow de escala

"Quais transições podem ser automatizadas?"
→ Resposta: Matriz de automações com prioridades

"O que significa 'em risco'?"
→ Resposta: Performance caiu durante a escalação
```

---

## Fluxo Visual Completo

Abrir documento em Obsidian:
```
~/Obsidian/IMPERA/Fluxo de Testes de Criativos.md
```

Mostra:
- Diagrama ASCII do workflow
- 12 statuses com cores e significados
- 4 caminhos principais (sucesso, falha, risco, pausa)
- O que o gestor decide em cada ponto

---

## Automatizações (Próximas)

Ver documento:
```
~/Scripts/automacoes_trafego.md
```

Contém:
- Qual transições serão automáticas
- Quando vão disparar (timeout, ROI)
- Como receber notificações

---

## Dúvidas Comuns

**P: Quantos criativos estão em "em teste" agora?**
```bash
python3 ~/Scripts/dashboard_trafego_status.py --status="em teste"
# Mostra a quantidade na linha "EM TESTE (X criativos)"
```

**P: Qual copywriter criou mais criativos em abril?**
```bash
python3 ~/Scripts/relatorio_mensal_copywriters_testes.py --mes=4 --ano=2026
# Veja a coluna "Criados" na tabela do docx
```

**P: Quanto tempo um criativo leva em média em "em teste"?**
```bash
python3 ~/Scripts/dashboard_trafego_status.py --status="em teste"
# Veja a coluna "Dias" para cada criativo
```

**P: Qual é o fluxo se um criativo "falha"?**
```
~/Obsidian/IMPERA/Fluxo de Testes de Criativos.md
# Procure por "CAMINHO FALHA RÁPIDA" ou "FALHA NA ESCALA"
```

---

## Integrando no Seu Workflow

### Automatizar Relatório Mensal
Adicionar ao crontab (1º dia do mês, 09:10):
```bash
0 9 1 * * cd ~/Scripts && python3 relatorio_mensal_copywriters_testes.py >/dev/null 2>&1
```

### Ver Dashboard Diariamente
```bash
# Terminal: colar na barra de pesquisa Alfred/Spotlight
python3 ~/Scripts/dashboard_trafego_status.py | less
```

### Consultar Agente
No Claude Code:
```
query_corpus name="impera-ops" question="[SUA PERGUNTA AQUI]"
```

---

## Suporte Técnico

Se algo não funcionar:

1. **Dashboard retorna erro de API**
   → Verificar `CLICKUP_API_TOKEN` em `~/.zshrc`

2. **Relatório não gera docx**
   → Instalar: `pip3 install python-docx`

3. **Agente não responde**
   → Agente precisa estar primed (executado uma vez)

4. **Dados não batem**
   → Dashboard busca dados ao vivo (pode levar 30s)

---

**Versão:** 1.0  
**Última atualização:** 20 de maio de 2026  
**Próxima entrega:** Automações (5 de junho de 2026)
