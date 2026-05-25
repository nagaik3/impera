# 🎯 IMPERA Context — Como Usar

**Criado:** 2026-05-21  
**Versão:** 1.0

---

## 🚀 Quick Start

### Entrar no Contexto IMPERA

```bash
impera
```

Isso faz:
- ✅ Carrega variáveis de ambiente IMPERA
- ✅ Muda para `~/Scripts/data/` (análises)
- ✅ Define aliases rápidos
- ✅ Mostra documentação disponível

### Comandos Disponíveis

```bash
impera              # → IMPERA Data (padrão)
impera dev          # → Desenvolvimento (impera-core)
impera scripts      # → Scripts directory
impera docs         # → Documentação (Obsidian)
impera status       # → Mostrar status do sistema
impera help         # → Mostrar ajuda
```

---

## 📁 Diretórios Configurados

```
IMPERA_HOME      = ~/impera-core/           (Desenvolvimento)
IMPERA_DATA      = ~/Scripts/data/          (Análises e relatórios)
IMPERA_SCRIPTS   = ~/Scripts/               (Scripts utilitários)
IMPERA_DOCS      = ~/Obsidian/IMPERA/       (Documentação)
```

---

## ⚡ Aliases Rápidos (dentro do contexto)

```bash
c              # → cd ~/Scripts/data/
cdata          # → cd ~/Scripts/data/
cscripts       # → cd ~/Scripts/
cdocs          # → cd ~/Obsidian/IMPERA/
cdev           # → cd ~/impera-core/
```

---

## 📚 Documentação Rápida

```bash
impera-doc-completo    # Documentação completa (19.2 KB)
impera-guia-rapido     # Referência rápida (2.1 KB)
impera-indice          # Índice e mapa da sessão
```

---

## 🔍 Funções Úteis

### Ver arquivos IMPERA
```bash
ls-impera-data
```

Mostra os últimos 10 arquivos em `~/Scripts/data/`

### Buscar em documentação
```bash
impera-search "nomenclatura"
impera-search "Douglas"
impera-search "velocity"
```

---

## 📍 Estrutura Criada

```
~/Scripts/
├── impera                          ← Script principal (executável)
├── .impera-context                 ← Configuração de contexto
├── IMPERA_CONTEXT_README.md        ← Este arquivo
│
└── data/
    ├── SESSAO_GESTORES_2026_05_21_COMPLETA.md
    ├── GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md
    ├── INDICE_SESSAO_2026_05_21.md
    └── [análises futuras]

~/.zshrc
└── impera() { bash ~/Scripts/impera "$@" }  ← Função adicionada
```

---

## 🔧 Configuração em .zshrc

A seguinte função foi adicionada ao seu `.zshrc`:

```bash
# ===== IMPERA CONTEXT MANAGER =====
impera() {
    bash ~/Scripts/impera "$@"
}
```

Isso permite usar `impera` como comando em qualquer terminal.

---

## 💡 Exemplo de Uso

### Scenario 1: Trabalhar com dados IMPERA

```bash
$ impera                    # Entra no contexto

╔════════════════════════════════════════════════════════════════╗
║                    IMPERA CONTEXT                              ║
║              Grupo IMPERA Produtos Naturais                    ║
╚════════════════════════════════════════════════════════════════╝

✓ Entering IMPERA context: IMPERA Data Analysis
Directory: /Users/iagoalmeida/Scripts/data

📚 Documentation:
  Complete:   ~/Scripts/data/SESSAO_GESTORES_2026_05_21_COMPLETA.md
  Quick Ref:  ~/Scripts/data/GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md
  Index:      ~/Scripts/data/INDICE_SESSAO_2026_05_21.md

Ready to work with IMPERA!

$ c                         # Muda para ~/Scripts/data/ (alias)
$ ls-impera-data            # Lista arquivos
$ impera-search "Lucas"     # Busca por "Lucas" na documentação
```

### Scenario 2: Trabalhar com desenvolvimento

```bash
$ impera dev                # Entra no contexto de dev

✓ Entering IMPERA context: IMPERA Development
Directory: /Users/iagoalmeida/impera-core

$ cdev                      # Confirma que está no impera-core
$ git status                # Trabalhar normalmente
```

### Scenario 3: Verificar status do sistema

```bash
$ impera status

╔════════════════════════════════════════════════════════════════╗
║                    IMPERA CONTEXT                              ║
║              Grupo IMPERA Produtos Naturais                    ║
╚════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════
IMPERA SYSTEM STATUS
═══════════════════════════════════════════════════════════════════

📁 Directories:
  ✅ impera-core: ~/impera-core
  ✅ data: ~/Scripts/data
  ✅ scripts: ~/Scripts
  ✅ docs: ~/Obsidian/IMPERA

📊 Latest Analysis Files:
  • SESSAO_GESTORES_2026_05_21_COMPLETA.md
  • GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md
  • INDICE_SESSAO_2026_05_21.md

🔐 API Configuration:
  ✅ ClickUp API Token: pk_1764042...
  ✅ RedTrack API Key: SET
```

---

## 🎯 Casos de Uso

### Para Análise de Dados
```bash
impera                  # → IMPERA Data context
c                       # → cd ~/Scripts/data/
impera-guia-rapido      # → Ver referência rápida de nomenclatura
```

### Para Desenvolvimento
```bash
impera dev              # → IMPERA Development
git status              # → Trabalhar normalmente
```

### Para Documentação
```bash
impera docs             # → IMPERA Documentation
cdev                    # → Para voltar ao impera-core
```

### Para Pesquisa Rápida
```bash
impera-search "Douglas"        # Buscar por "Douglas" em docs
impera-search "velocity"       # Buscar por "velocity"
impera-search "nomenclatura"   # Buscar por "nomenclatura"
```

---

## 📝 Próximas Melhorias

Possíveis extensões:

- [ ] `impera new-analysis` — Criar nova análise com template
- [ ] `impera sync-docs` — Sincronizar documentação com Obsidian
- [ ] `impera api-test` — Testar conexões com APIs
- [ ] `impera dashboard` — Abrir dashboard em navegador
- [ ] `impera lint-names` — Validar nomenclatura de tarefas

---

## 🔗 Referências

- **Documentação Completa:** `~/Scripts/data/SESSAO_GESTORES_2026_05_21_COMPLETA.md`
- **Guia Rápido:** `~/Scripts/data/GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md`
- **Índice:** `~/Scripts/data/INDICE_SESSAO_2026_05_21.md`
- **Script IMPERA:** `~/Scripts/impera`
- **Configuração:** `~/.zshrc` (função `impera`)

---

**Criado por:** Claude (Senior Data Management)  
**Para:** Iago Almeida  
**Data:** 2026-05-21
