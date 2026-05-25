#!/bin/bash
# Ativar Agente IMPERA — Carrega contexto completo e inicia sessão

set -e

IMPERA_DIR="$HOME/Scripts/data"
AGENTE_PROMPT="$HOME/Scripts/AGENTE_IMPERA_PROMPT.md"
CLAUDE_CONFIG="$HOME/.claude-impera"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   🤖 AGENTE IMPERA                             ║"
echo "║          Especialista em Gestão de Dados IMPERA               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Verificar se arquivo de prompt existe
if [ ! -f "$AGENTE_PROMPT" ]; then
    echo "❌ Erro: Arquivo de prompt não encontrado"
    echo "   Esperado: $AGENTE_PROMPT"
    exit 1
fi

# Verificar se diretório existe
if [ ! -d "$IMPERA_DIR" ]; then
    echo "❌ Erro: Diretório IMPERA não encontrado"
    echo "   Esperado: $IMPERA_DIR"
    exit 1
fi

# Criar arquivo de configuração de contexto
cat > "$CLAUDE_CONFIG" << EOF
# Configuração do Agente IMPERA
# Carregado em: $(date)

export IMPERA_MODE="true"
export IMPERA_AGENT="true"
export IMPERA_DIR="$IMPERA_DIR"
export AGENTE_PROMPT="$AGENTE_PROMPT"

# Aliases para agente
alias ls-data="ls -lht $IMPERA_DIR/*.{md,json,txt} 2>/dev/null | head -15"
alias view-completo="cat $IMPERA_DIR/SESSAO_GESTORES_2026_05_21_COMPLETA.md"
alias view-rapido="cat $IMPERA_DIR/GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md"
alias view-indice="cat $IMPERA_DIR/INDICE_SESSAO_2026_05_21.md"

echo "✅ Agente IMPERA ativado"
EOF

echo "✅ Configuração carregada:"
echo "   📁 Diretório: $IMPERA_DIR"
echo "   📄 Prompt: $AGENTE_PROMPT"
echo ""

echo "📚 Documentação disponível:"
echo "   1. Documentação completa (19.2 KB)"
echo "      → ~/Scripts/data/SESSAO_GESTORES_2026_05_21_COMPLETA.md"
echo ""
echo "   2. Guia de referência rápida (2.1 KB)"
echo "      → ~/Scripts/data/GUIA_RAPIDO_NOMENCLATURA_CONTAGEM.md"
echo ""
echo "   3. Índice e navegação"
echo "      → ~/Scripts/data/INDICE_SESSAO_2026_05_21.md"
echo ""
echo "   4. Como Claude trabalha em IMPERA"
echo "      → ~/Scripts/data/COMO_USAR_IMPERA_CONTEXT.md"
echo ""

echo "🤖 System Prompt do Agente:"
echo "   → ~/Scripts/AGENTE_IMPERA_PROMPT.md"
echo ""

echo "🎯 Você está pronto para trabalhar com IMPERA!"
echo ""
echo "Comandos úteis (nesta sessão):"
echo "   ls-data             → Ver arquivos IMPERA"
echo "   view-completo       → Documentação completa"
echo "   view-rapido         → Guia rápido"
echo "   view-indice         → Índice"
echo ""

# Source a configuração
source "$CLAUDE_CONFIG"

echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Abrir documentação se disponível
if command -v less &> /dev/null; then
    read -p "Deseja visualizar o prompt do agente? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        less "$AGENTE_PROMPT"
    fi
fi

echo ""
echo "🚀 Agente IMPERA pronto para uso!"
echo ""
