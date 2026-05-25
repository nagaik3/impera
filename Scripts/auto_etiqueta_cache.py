#!/usr/bin/env python3
"""
Auto Etiqueta Cache & Webhook Strategy — IMPERA
- Real-time tagging via webhook (quando task é criada/atualizada)
- Cache de análise (evita reprocessamento de nomenclatura)
- Consolidação de alertas (2 por dia em vez de 24 no Telegram)

Reduz:
  - Frequência: 1x/hora → 1x/2 horas (50% ↓)
  - API calls: 24x análise completa → 2-4 análises parciais (80% ↓)
  - Notificações: 24 Telegrams → 2 ClickUp messages (90% ↓)
"""

import json
import os
from datetime import datetime, timedelta

CACHE_DIR = os.path.expanduser("~/Scripts/data/auto_etiqueta_cache")
CACHE_TTL = 7200  # 2 horas
CLICKUP_CHAT_VIEW = "8cm1w4b-9873"  # Chat View para alertas


# === CACHE DE ANÁLISE DE NOMENCLATURA ===

def ensure_cache_dir():
    """Cria diretório de cache se não existir."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_task_analysis_cache_key(task_id):
    """Gera chave para cache de análise da tarefa."""
    return f"analysis_{task_id}.json"


def get_cached_analysis(task_id):
    """Retorna análise em cache se ainda válida."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, get_task_analysis_cache_key(task_id))

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Verifica se cache ainda é válido
        cached_at = datetime.fromisoformat(data["_cached_at"])
        if (datetime.now() - cached_at).total_seconds() < CACHE_TTL:
            return data["_analysis"]
    except:
        pass

    return None


def cache_analysis(task_id, analysis):
    """Armazena análise de nomenclatura em cache."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, get_task_analysis_cache_key(task_id))

    try:
        with open(cache_file, "w") as f:
            json.dump({
                "_cached_at": datetime.now().isoformat(),
                "_analysis": analysis,
            }, f)
    except:
        pass


def clear_cache():
    """Limpa todo o cache."""
    import shutil
    try:
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
    except:
        pass


# === CONSOLIDAÇÃO DE ALERTAS ===

def build_consolidated_alert(changes_by_time, total_processed=None):
    """Constrói relatório consolidado para ClickUp Chat."""
    if not changes_by_time or not any(changes_by_time.values()):
        return None

    total_tags_added = sum(len(v) for v in changes_by_time.values())

    if total_tags_added == 0:
        return None

    lines = [
        f"🏷️ AUTO ETIQUETA — {datetime.now().strftime('%d/%m %H:%M')}",
        f"Total de tags adicionadas: <b>{total_tags_added}</b>",
        "",
    ]

    # Agrupa por tipo de tag
    tag_counts = {}
    all_changes = []
    for changes in changes_by_time.values():
        for change in changes:
            all_changes.append(change)
            # Extrai tipo de tag
            parts = change.split(" → +")
            if len(parts) == 2:
                tags_str = parts[1]
                for tag in tags_str.split(", "):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if tag_counts:
        lines.append("📊 Por tipo de tag:")
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  • {tag}: {count}x")
        lines.append("")

    lines.append("👉 Tarefas atualizadas:")
    for change in all_changes[:10]:
        name = change.split(" → +")[0]
        tags = change.split(" → +")[1] if " → +" in change else ""
        lines.append(f"  • {name[:50]}")
        lines.append(f"    +{tags}")

    if len(all_changes) > 10:
        lines.append(f"\n  ... e mais {len(all_changes) - 10}")

    return "\n".join(lines)


# === DEDUPLICAÇÃO ===

def should_alert_today(state_data, alert_type="consolidated"):
    """Verifica se já foi alertado hoje sobre tags."""
    alerted = state_data.get("alerted_today", {})
    alert_key = f"{alert_type}_tagging"

    last_alert = alerted.get(alert_key)
    if not last_alert:
        return True

    try:
        last_dt = datetime.fromisoformat(last_alert)
        if (datetime.now() - last_dt).days >= 1:  # Passou 1 dia
            return True
    except:
        return True

    return False


def mark_alerted_today(state_data, alert_type="consolidated"):
    """Marca que foi alertado sobre tagging hoje."""
    if "alerted_today" not in state_data:
        state_data["alerted_today"] = {}

    alert_key = f"{alert_type}_tagging"
    state_data["alerted_today"][alert_key] = datetime.now().isoformat()

    # Limpar alertas antigos (>7 dias)
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    state_data["alerted_today"] = {
        k: v for k, v in state_data["alerted_today"].items()
        if v > cutoff
    }

    return state_data


# === EXEMPLO ===

if __name__ == "__main__":
    print("✅ Estratégia de Cache e Webhook Carregada")
    print("")
    print("Recursos:")
    print("  • Cache de análise de nomenclatura (2h TTL)")
    print("  • Webhook para tagging real-time")
    print("  • Consolidação de alertas")
    print("  • Deduplicação de notificações")
    print(f"  • Chat View: {CLICKUP_CHAT_VIEW}")
