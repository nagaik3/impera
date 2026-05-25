# 🎨 ANÁLISE DETALHADA — Design System (Resumo Entrevista Pablo)

## ESTRUTURA VISUAL IDENTIFICADA

### 1. CABEÇALHO PRINCIPAL
```
┌─────────────────────────────────────────────────────────────┐
│ [Fundo: Preto/Escuro #1a1a1a]                              │
│                                                               │
│ 📊 RELATÓRIO SEMANAL — TIME DE COPY                         │
│ (Branco, 28pt, Bold, Helvetica)                            │
│                                                               │
│ Grupo Impera · Período de Produção                         │
│ (Cinza, 11pt, Regular)                                      │
│                                        [COMPARATIVO SEMANAL] │
│                                        (Badge Roxo)          │
└─────────────────────────────────────────────────────────────┘
```

**Características**:
- Fundo preto contrasta com texto branco
- Badge em cor roxa/destaque no canto superior direito
- Sem imagem, apenas tipografia
- Padding generoso (1cm top/bottom)

---

### 2. SEÇÃO DE IDENTIFICAÇÃO (PESSOA)
```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│ Yan                                                          │
│ (Preto, 20pt, Bold)                                         │
│                                                               │
│ Copywriter Senior · Semana 17-23 de Maio                   │
│ (Cinza, 10pt, Regular)                                      │
│                                                               │
│ [12 ads] [R$ 38.420] [ROAS 2,34] [MC BR ↑16,2%]          │
│ (Tags coloridas, 9pt, Bold)                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Características dos Badges**:
- Fundo: Cores suaves (azul claro, verde claro, etc.)
- Texto: Cor escura (preto ou cor complementar)
- Padding: 6px horizontal, 3px vertical
- Espaçamento entre tags: 8px
- Border-radius: 4px (discreto)

---

### 3. CARD DE RECOMENDAÇÃO/INSIGHT PRINCIPAL
```
┌─────────────────────────────────────────────────────────────┐
│ [Fundo: Verde #10b981 ou similar]                          │
│                                                               │
│ ✅ PERFORMANCE EM ALTA                                      │
│ (Branco, 16pt, Bold)                                        │
│                                                               │
│ Faturamento ↑ +12,3% vs semana anterior | ROAS estável    │
│ (Branco, 11pt, Regular)                                     │
│                                                               │
│ Produção mais estratégica. Taxa de assertividade: 85%      │
│ (Cinza claro, 10pt, Regular)                               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Características**:
- Ícone emoji à esquerda (✅, 🔴, ⚠️)
- Título em branco bold
- 2 linhas de descrição
- Fundo com cor (verde=sucesso, vermelho=alerta, amarelo=atenção)
- Padding: 1cm
- Border-radius: 6px

---

### 4. SEÇÕES DE CONTEÚDO (2-3 COLUNAS)
```
COLUNA ESQUERDA:                COLUNA DIREITA:
┌──────────────────────────┐   ┌──────────────────────────┐
│ 📈 PERFORMANCE           │   │ 📊 PRODUÇÃO              │
│ (Heading, 12pt Bold)     │   │ (Heading, 12pt Bold)     │
│                          │   │                          │
│ • Faturamento: R$ 38.420 │   │ • Ads: 12 (↓ -1)        │
│ • MC BR: R$ 18.200       │   │ • Demandas: 12          │
│ • ROAS: 2,34 ↑           │   │ • Cumpridas: 11 (92%)   │
│ • Front: 2,01 ↑          │   │ • Enviadas: 11          │
│                          │   │ • Esteira: 1            │
│ ✓ Crescimento: +16,2%   │   │                          │
│                          │   │ 🎯 TESTES & ASSERTIVIDADE│
└──────────────────────────┘   │ (Heading, 11pt Bold)     │
                               │                          │
                               │ Novos: 4                 │
                               │ Validados: 4/4 (100%)   │
                               │                          │
                               │ ✅ Excelente             │
                               │                          │
                               └──────────────────────────┘
```

**Características**:
- Colunas com largura fixa (1/3 ou 1/2)
- Ícones emoji nos títulos
- Bullet points com símbolo (•)
- Cores sutis: verde para crescimento, laranja para alerta
- Sem bordas; apenas espaçamento
- Fundo branco ou branco com linha sutil acima

---

### 5. TABELA SIMPLES
```
┌─────────────────────────────────────────────────────────────┐
│ Copywriter | Ads | Faturamento | ROAS | Demandas | Testes │
├─────────────────────────────────────────────────────────────┤
│ Yan        │ 12  │ R$ 38.420   │ 2,34 │ 11/12    │ 4/4    │
│ Crispim    │ 14  │ R$ 42.850   │ 2,08 │ 14/14    │ 4/5    │
│ ...        │     │             │      │          │        │
│ TOTAL      │ 47  │ R$ 145.320  │ 2,15 │ 44/47    │ 13/13  │
└─────────────────────────────────────────────────────────────┘
```

**Características**:
- Cabeçalho: Preto, texto branco, 9pt bold
- Linhas alternadas: Branco e cinza muito claro (#f9fafb)
- Bordas: Linhas cinza muito sutis
- Linhas de destaque: Negrito (TOTAL)
- Alinhamento: Center para números, Left para nomes
- Fontsize: 8pt (compacto, legível)

---

### 6. CARDS DE PONTOS POSITIVOS/ATENÇÃO
```
POSITIVO:                       ATENÇÃO:
┌────────────────────────┐     ┌────────────────────────┐
│ ✓ After Effects forte  │     │ ✗ Volume conservador   │
│ (Verde claro #dcfce7)  │     │ (Laranja claro #fed7aa)│
│                        │     │                        │
│ Diferencial raro na    │     │ 12/dia confortável;    │
│ equipe atual.          │     │ pico de 25 = queda QC  │
│                        │     │                        │
└────────────────────────┘     └────────────────────────┘
```

**Características**:
- Ícone à esquerda (✓ ou ✗)
- Fundo suave (verde #dcfce7 para positivo, laranja #fed7aa para alerta)
- Texto preto
- Padding: 12px
- Border-radius: 4px
- Sem borda, apenas cor de fundo

---

### 7. CARD DESTACADO (RECOMENDAÇÃO/LEITURA FINAL)
```
┌─────────────────────────────────────────────────────────────┐
│ [Fundo: Roxo claro #ede9fe]                                │
│ [Borda esquerda: Roxo escuro #7c3aed, 3px]                │
│                                                               │
│ 🎯 RECOMENDAÇÃO                                             │
│ (Roxo escuro, 13pt, Bold)                                   │
│                                                               │
│ Yan mantém excelência. Aumentar volume em 1-2 criativos    │
│ extras. Perfil de referência para assertividade.           │
│ (Preto, 10pt, Regular)                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Características**:
- Fundo roxo muito claro (#ede9fe)
- Borda esquerda em roxo escuro (3px width)
- Título em roxo escuro
- Conteúdo em preto
- Padding: 1cm
- Border-radius: 4px

---

### 8. PRÓXIMOS PASSOS (3 CARDS NUMERADOS)
```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│       1        │    │       2        │    │       3        │
│  (Roxo fundo)  │    │  (Roxo fundo)  │    │  (Roxo fundo)  │
│                │    │                │    │                │
│ Validar com    │    │ Revisar Top 5  │    │ Próximo        │
│ gestor de      │    │ para padrão    │    │ Relatório      │
│ tráfego        │    │ min ROAS       │    │ (Edição)       │
│                │    │                │    │                │
│ (Descrição     │    │ (Descrição     │    │ (Descrição     │
│  resumida)     │    │  resumida)     │    │  resumida)     │
└────────────────┘    └────────────────┘    └────────────────┘
```

**Características**:
- Número em círculo (fundo roxo #7c3aed, branco)
- Card com borda leve cinza
- Título em bold
- Descrição pequena (9pt)
- Espaçamento entre cards: 1cm
- Border-radius: 6px

---

### 9. CORES SISTEMA

| Elemento | Cor | Hex | Uso |
|----------|-----|-----|-----|
| Primária | Roxo | #7c3aed | Headings, destaque principal |
| Sucesso | Verde | #10b981 | Cards positivos, checkmarks |
| Alerta | Amarelo | #f59e0b | Atenções moderadas |
| Erro | Vermelho | #ef4444 | Quedas, alertas críticos |
| Fundo Cards Positivos | Verde claro | #dcfce7 | Background pontos fortes |
| Fundo Cards Alerta | Laranja claro | #fed7aa | Background pontos atenção |
| Fundo Cards Roxo | Roxo claro | #ede9fe | Background recomendações |
| Fundo Tabelas Alt | Cinza claro | #f9fafb | Linhas alternadas |
| Texto Principal | Preto | #1f2937 | Body text |
| Texto Secundário | Cinza | #6b7280 | Descrições |
| Bordas | Cinza claro | #d1d5db | Grid, separadores |
| Cabeçalho | Preto | #1a1a1a | Top section background |

---

### 10. TIPOGRAFIA

| Elemento | Fonte | Tamanho | Peso | Cor |
|----------|-------|---------|------|-----|
| Título Principal | Helvetica | 28pt | Bold | Branco (sobre preto) |
| Subtítulo | Helvetica | 11pt | Regular | Cinza (#6b7280) |
| Nome Pessoa | Helvetica | 20pt | Bold | Preto (#1f2937) |
| Heading Seção | Helvetica | 13pt | Bold | Roxo (#7c3aed) |
| Subheading | Helvetica | 11pt | Bold | Preto (#1f2937) |
| Body Text | Helvetica | 10pt | Regular | Preto (#1f2937) |
| Small Text | Helvetica | 9pt | Regular | Cinza (#6b7280) |
| Tabelas | Helvetica | 8pt | Regular | Preto |

---

### 11. ESPAÇAMENTO & LAYOUT

- **Margem Página**: 1.5cm (esquerda/direita), 1cm (topo/rodapé)
- **Entre Seções**: 0.8cm
- **Entre Subsecções**: 0.4cm
- **Dentro de Cards**: 1cm padding
- **Entre Badges**: 0.8cm
- **Entre Colunas**: 1.2cm
- **Altura linha tabela**: 0.4cm

---

### 12. ESTRUTURA DO DOCUMENTO (ORDEM)

1. Cabeçalho preto (com badge COMPARATIVO SEMANAL)
2. Seção de Identificação (Nome + Badges de KPIs)
3. Card de Insight/Recomendação (cor de sucesso)
4. Quadro-Resumo do Time (tabela)
5. [PAGE BREAK]
6. Análise Individual (2-3 colunas por pessoa)
   - Performance | Produção | Testes
   - Pontos Fortes (cards verdes)
   - Pontos Atenção (cards laranja)
7. [PAGE BREAK]
8. Top 10 ADS (tabela simples)
9. Card de Recomendação Final (roxo)
10. Próximos Passos (3 cards numerados)
11. Rodapé com metadata

---

## 🎯 APLICAR EXATAMENTE ASSIM NO RELATÓRIO COPY
