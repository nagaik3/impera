#!/bin/bash
# Setup Cron Jobs para Relatórios IMPERA
# Executa este script uma vez para configurar toda a automação

set -e

echo "🔧 Configurando Cron Jobs para IMPERA..."
echo ""

# Função para adicionar job ao crontab
add_cron_job() {
    local cmd="$1"
    local schedule="$2"
    local description="$3"

    # Verificar se job já existe
    if crontab -l 2>/dev/null | grep -q "$cmd"; then
        echo "✓ $description (já configurado)"
    else
        # Adicionar job novo
        (crontab -l 2>/dev/null || true; echo "$schedule $cmd") | crontab -
        echo "✓ $description (adicionado)"
    fi
}

# Home do usuário
HOME_DIR=$(eval echo ~)
SCRIPTS_DIR="$HOME_DIR/Scripts"

# Certificar que variáveis de ambiente estão setadas
if ! grep -q "CLICKUP_API_TOKEN" ~/.zshrc ~/.bashrc 2>/dev/null; then
    echo ""
    echo "⚠️  AVISO: Variáveis de ambiente não encontradas em ~/.zshrc"
    echo "   Certifique-se que CLICKUP_API_TOKEN e REDTRACK_API_KEY estão setadas."
    echo ""
fi

echo ""
echo "📋 Jobs configurados:"
echo ""

# 1. Rebuild Registry (a cada 4 horas)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 impera_ad_registry.py --rebuild >> $SCRIPTS_DIR/logs/registry_rebuild.log 2>&1" \
    "37 */4 * * *" \
    "1. Registry rebuild (a cada 4 horas, às :37)"

# 2. Monitor de Confiança (uma vez por dia, 01:00)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 impera_confidence_monitor.py --period 7 --auto >> $SCRIPTS_DIR/logs/confidence_monitor.log 2>&1" \
    "0 1 * * *" \
    "2. Monitor de Confiança (diariamente às 01:00)"

# 3. Relatório Copy (Domingo 23:00)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 relatorio_copy_semanal.py >> $SCRIPTS_DIR/logs/relatorio_copy.log 2>&1" \
    "0 23 * * 0" \
    "3. Relatório Copy (Domingo 23:00)"

# 4. Relatório Edição (Domingo 23:15)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 relatorio_edicao_semanal.py >> $SCRIPTS_DIR/logs/relatorio_edicao.log 2>&1" \
    "15 23 * * 0" \
    "4. Relatório Edição (Domingo 23:15)"

# 5. Relatório Tráfego (Domingo 23:30)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 relatorio_trafego_semanal.py >> $SCRIPTS_DIR/logs/relatorio_trafego.log 2>&1" \
    "30 23 * * 0" \
    "5. Relatório Tráfego (Domingo 23:30)"

# 6. Relatório GPDR (Domingo 23:45)
add_cron_job \
    "cd $SCRIPTS_DIR && python3 relatorio_gpdr_executiva.py >> $SCRIPTS_DIR/logs/relatorio_gpdr.log 2>&1" \
    "45 23 * * 0" \
    "6. Relatório GPDR (Domingo 23:45)"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Setup completo!"
echo ""
echo "📊 Cronograma de Execução:"
echo "  - Registry rebuild: A cada 4 horas (37 min da hora)"
echo "  - Monitor de Confiança: Diariamente às 01:00"
echo "  - Relatórios semanais: Domingo 23:00-23:45"
echo ""
echo "📁 Logs em: $SCRIPTS_DIR/logs/"
echo ""
echo "Para verificar jobs agendados:"
echo "  crontab -l"
echo ""
echo "Para editar jobs manualmente:"
echo "  crontab -e"
echo "═══════════════════════════════════════════════════════════════"
