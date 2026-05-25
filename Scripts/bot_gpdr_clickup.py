#!/usr/bin/env python3
"""
Bot GPDR → ClickUp Chat View
Migração do Telegram bot para ClickUp.

Gera relatórios sob demanda e posta em ClickUp.

Modos:
  python3 bot_gpdr_clickup.py producao         # Relatório de produção
  python3 bot_gpdr_clickup.py performance      # Performance por criativo
  python3 bot_gpdr_clickup.py briefing         # Briefing diário
  python3 bot_gpdr_clickup.py auditoria        # Auditoria de nomenclatura

Posts para ClickUp Chat View: 8cm1w4b-9913

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9913"

LOG_DIR = os.path.expanduser("~/Scripts/logs")


def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    """Posta mensagem no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        log("✗ Sem mensagem ou chat view")
        return False

    try:
        import subprocess
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            log("✓ Mensagem postada em ClickUp")
            return True
        else:
            log(f"✗ Erro ao postar: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Erro: {e}")
        return False


def run_script(script_name, *args):
    """Executa script externo e retorna output."""
    try:
        script_path = os.path.expanduser(f"~/Scripts/{script_name}")
        cmd = ["/usr/bin/python3", script_path] + list(args)
        log(f"Executando: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log(f"Script falhou: {result.stderr[:500]}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        log("Timeout: script demorou muito")
        return None
    except Exception as e:
        log(f"Erro ao executar script: {e}")
        return None


def report_producao():
    """Relatório de produção semanal."""
    log("Gerando relatório de produção...")

    # Usar novo script otimizado
    output = run_script("relatorio_semanal_clickup.py")

    if output:
        # Extrair mensagem consolidada (já está formatada para ClickUp)
        # O script já posta automaticamente, então aqui retornamos sucesso
        log("✓ Relatório de produção gerado (já postado em ClickUp)")
        return True

    log("Nenhum output do script de produção")
    return False


def report_performance():
    """Relatório de performance por criativo."""
    log("Gerando relatório de performance...")

    # Usar período padrão: últimos 7 dias
    from datetime import datetime, timedelta
    yesterday = datetime.now() - timedelta(days=1)
    date_from = (yesterday - timedelta(days=7)).strftime("%d/%m/%Y")
    date_to = yesterday.strftime("%d/%m/%Y")

    output = run_script("relatorio_performance_criativos.py", date_from, date_to)

    if output:
        msg = f"📈 RELATÓRIO PERFORMANCE (últimos 7 dias)\n\n{output[:3500]}"
        if len(output) > 3500:
            msg += "\n\n... (resumido)"
        post_clickup(msg)
        return True

    log("Nenhum output do script de performance")
    return False


def report_briefing():
    """Briefing diário sob demanda."""
    log("Gerando briefing diário...")

    output = run_script("briefing_diario.py")

    if output:
        msg = f"📋 BRIEFING DIÁRIO\n\n{output[:3500]}"
        if len(output) > 3500:
            msg += "\n\n... (resumido)"
        post_clickup(msg)
        return True

    log("Nenhum output do briefing")
    return False


def report_auditoria():
    """Auditoria de nomenclatura."""
    log("Executando auditoria de nomenclatura...")

    output = run_script("auditoria_nomenclatura.py", "--report")

    if output:
        msg = f"🔍 AUDITORIA NOMENCLATURA\n\n{output[:3500]}"
        if len(output) > 3500:
            msg += "\n\n... (resumido)"
        post_clickup(msg)
        return True

    log("Nenhum output da auditoria")
    return False


# === MAIN ===

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "help"

    try:
        if cmd == "producao":
            report_producao()
        elif cmd == "performance":
            report_performance()
        elif cmd == "briefing":
            report_briefing()
        elif cmd == "auditoria":
            report_auditoria()
        else:
            print(__doc__)
            print("\nComandos disponíveis:")
            print("  producao     - Relatório de produção semanal")
            print("  performance  - Performance por criativo (últimos 7 dias)")
            print("  briefing     - Briefing diário")
            print("  auditoria    - Auditoria de nomenclatura")
    except Exception as e:
        log(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    log("✓ Concluído")
